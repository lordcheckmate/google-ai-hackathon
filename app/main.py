"""
FastAPI application:
- WebSocket endpoint for bidirectional audio streaming, transcripts, and canvas updates
- Command endpoint (/command) for click/voice parity
- Image proxy endpoint (/img/{id}) for Nano Banana illustrations
- Static file server for vanilla HTML/CSS/JS frontend
"""

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.stt import STTSession
from app.agent import MeetingAgentSession
from app.commands import COMMANDS, extract_voice_command, is_session_paused
from app.images import get_image
from app.store import get_blocks, save_session, record_transcript, list_sessions, update_session_title, delete_session

from app.auth import (
    BasicAuthMiddleware,
    verify_auth_token,
    verify_basic_auth,
    verify_credentials,
    AUTH_USER,
    AUTH_PASS,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="AI Meeting Assistant")
app.add_middleware(BasicAuthMiddleware)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def on_startup():
    # Pre-warm pooled GenAI client in background so turns are immediate
    async def _prewarm():
        try:
            from app.blocks.generate import get_genai_client
            client = get_genai_client()
            if client:
                logger.info("Pooled GenAI client pre-warmed successfully")
        except Exception as e:
            logger.warning(f"Client pre-warm notice: {e}")
    asyncio.create_task(_prewarm())


@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        resp = FileResponse(str(index_file))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return PlainTextResponse("ok")


@app.get("/healthz")
@app.get("/health")
async def healthz():
    return JSONResponse({"status": "ok", "service": "aegis-meeting-copilot"})


@app.get("/img/{image_id}")
async def serve_image(image_id: str):
    """Proxy image bytes from Cloud Storage or local cache (Section 11)."""
    result = get_image(image_id)
    if result:
        data, mime = result
        return Response(content=data, media_type=mime)
    return Response(status_code=404, content="Image not found")


@app.post("/command")
async def execute_command(request: Request):
    """HTTP Click-path command dispatcher for parity (Section 8)."""
    try:
        body = await request.json()
        name = body.get("name")
        args = body.get("args", {})
        sid = body.get("sid", "default")

        if name not in COMMANDS:
            return JSONResponse({"status": "error", "message": f"Unknown command {name}"}, status_code=400)

        # Mock ws_sender for HTTP requests
        async def mock_ws_sender(payload):
            pass

        handler = COMMANDS[name]
        result = await handler(sid, args, mock_ws_sender)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error in /command: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/sessions")
async def get_sessions_endpoint(request: Request):
    """Retrieve list of private sessions for a given user_id."""
    user_id = request.query_params.get("user_id") or "guest_default"
    return JSONResponse(list_sessions(user_id))


@app.post("/api/sessions")
async def create_session_endpoint(request: Request):
    """Create a new private session for user_id."""
    import uuid
    try:
        body = await request.json()
    except Exception:
        body = {}
    user_id = body.get("user_id") or "guest_default"
    title = body.get("title") or "New Meeting"
    sid = f"sess_{uuid.uuid4().hex[:8]}"
    sess = save_session(sid, title=title, user_id=user_id)
    return JSONResponse(sess)


@app.patch("/api/sessions/{sid}")
async def patch_session_endpoint(sid: str, request: Request):
    """Update title for a session."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    title = body.get("title")
    if title:
        update_session_title(sid, title)
    return JSONResponse({"status": "ok"})


@app.delete("/api/sessions/{sid}")
async def delete_session_endpoint(sid: str, request: Request):
    """Delete a session."""
    user_id = request.query_params.get("user_id") or "guest_default"
    delete_session(sid, user_id)
    return JSONResponse({"status": "ok"})


@app.get("/api/sessions/{sid}/blocks")
async def get_session_blocks_endpoint(sid: str):
    """Retrieve all rendered blocks for a session."""
    from app.blocks import render_block
    blocks = get_blocks(sid)
    rendered = []
    for b in blocks:
        try:
            markup = render_block(b["kind"], b["json"])
            rendered.append({
                "id": b["id"],
                "kind": b["kind"],
                "title": b["json"].get("title", b["kind"]),
                "html": markup,
                "parent": b.get("parent"),
                "json": b["json"],
            })
        except Exception:
            pass
    return JSONResponse({"blocks": rendered})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Verify authentication for WebSocket handshake
    cookie_token = websocket.cookies.get("aegis_auth")
    auth_header = websocket.headers.get("authorization")
    q_token = websocket.query_params.get("auth")
    q_user = websocket.query_params.get("user")
    q_pass = websocket.query_params.get("pass")

    is_authenticated = (
        (cookie_token and verify_auth_token(cookie_token))
        or (auth_header and verify_basic_auth(auth_header))
        or (q_token and verify_auth_token(q_token))
        or (q_user and q_pass and verify_credentials(q_user, q_pass))
    )

    if not is_authenticated:
        logger.warning(f"Unauthorized WebSocket access attempt rejected from {websocket.client}")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    sid = websocket.query_params.get("session_id") or "default_session"
    user_id = websocket.query_params.get("user_id") or "guest_default"
    if websocket.query_params.get("fresh") == "1":
        from app.store import clear_session_blocks
        clear_session_blocks(sid)
    save_session(sid, title="New Meeting", user_id=user_id)

    logger.info(f"WebSocket client connected (session={sid})")
    loop = asyncio.get_running_loop()

    # Echo suppression state (Section 10)
    # While TTS audio is playing, and for 700 ms after it ends, discard incoming transcript.
    tts_suppress_until = [0.0]

    async def send_ws(payload: Dict[str, Any]):
        try:
            # If payload contains TTS audio, set echo suppression window
            if payload.get("type") in ("speak", "contradiction") and payload.get("audio"):
                # Approximate 3 seconds speaking duration + 700ms buffer
                tts_suppress_until[0] = time.time() + 3.7
            await websocket.send_json(payload)
        except Exception as e:
            logger.debug(f"WS send failed: {e}")

    # Initialize Agent session
    agent_session = MeetingAgentSession(sid=sid, ws_sender=send_ws, loop=loop)

    # Initial state push: send any existing blocks so reload preserves canvas
    existing_blocks = get_blocks(sid)
    for b in existing_blocks:
        from app.blocks import render_block
        try:
            markup = render_block(b["kind"], b["json"])
            await websocket.send_json({
                "type": "block_upsert",
                "block": {
                    "id": b["id"],
                    "kind": b["kind"],
                    "title": b["json"].get("title", b["kind"]),
                    "html": markup,
                    "parent": b.get("parent"),
                    "json": b["json"],
                }
            })
        except Exception as err:
            logger.warning(f"Error restoring block {b['id']}: {err}")

    # Per-connection transcript debouncer & turn accumulator
    # Rule: Only generate on speech stop (silence) OR every 10 seconds of continuous speech
    transcript_buffer: List[str] = []
    debounce_handle: List[Optional[asyncio.TimerHandle]] = [None]
    last_dispatched = ["", 0.0]  # [text, timestamp]
    speech_turn_start = [0.0]

    def flush_turn():
        if debounce_handle[0]:
            try:
                debounce_handle[0].cancel()
            except Exception:
                pass
            debounce_handle[0] = None

        speech_turn_start[0] = 0.0

        if not transcript_buffer:
            return

        full_text = " ".join(transcript_buffer).strip()
        transcript_buffer.clear()

        if not full_text:
            return

        # Deduplication against recently dispatched turn (within last 3.5s)
        now = time.time()
        if full_text.lower() == last_dispatched[0].lower() and (now - last_dispatched[1]) < 3.5:
            logger.debug(f"[Duplicate turn suppressed]: '{full_text}'")
            return

        # Filter out trivial noise phrases, filler sounds, or mic artifacts
        clean = full_text.lower().strip(" .!?,、。")
        filler_words = {
            "um", "uh", "yeah", "ok", "okay", "yes", "no", "mhm", "ah", "huh", "right", "testing", "test",
            "あ", "ええ", "はい", "うん", "そう", "まあ", "えーと", "あの", "その"
        }
        if clean in filler_words or len(clean) < 2:
            logger.debug(f"[Filler noise ignored]: '{full_text}'")
            return

        # Meeting greetings & small talk (English & Japanese)
        # SILENCE POLICY: NEVER speak aloud or play audio over meeting participants!
        greetings_en = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening", "how are you", "can you hear me"}
        greetings_ja = {"こんにちは", "おはよう", "おはようございます", "こんばんは", "はじめまして", "聞こえますか", "よろしく", "よろしくお願いします"}

        is_short_greeting = (
            len(clean) <= 25 and (
                clean in greetings_en
                or clean in greetings_ja
                or any(clean == f"hey {g}" or clean == f"hello {g}" for g in ["agent", "assistant", "aegis"])
                or any(clean.startswith(g) for g in ["こんにちは", "おはよう", "よろしく"])
            )
        )

        if is_short_greeting:
            logger.info(f"[Standalone greeting acknowledged silently - no audio]: '{full_text}'")
            # Update transcript on screen silently with zero audio
            asyncio.run_coroutine_threadsafe(
                send_ws({"type": "transcript", "text": full_text, "is_final": True}),
                loop
            )
            return



        last_dispatched[0] = full_text
        last_dispatched[1] = now

        record_transcript(sid, full_text)
        logger.info(f"[Turn Dispatched to Agent] session={sid}: '{full_text}'")
        asyncio.run_coroutine_threadsafe(
            agent_session.process_turn(full_text),
            loop
        )

    # Callback when transcript is produced by STT v2 or client WebSpeech
    def on_transcript(text: str, is_final: bool, immediate: bool = False):
        now = time.time()
        # Echo suppression check
        if now < tts_suppress_until[0]:
            logger.debug(f"[Echo Suppressed] '{text}'")
            return

        asyncio.run_coroutine_threadsafe(
            websocket.send_json({
                "type": "transcript",
                "text": text,
                "is_final": is_final,
            }),
            loop
        )

        if not is_final or not text.strip():
            return

        # Check for immediate voice commands first (Section 8)
        cmd_name, cmd_args, stripped_text = extract_voice_command(sid, text)
        if cmd_name:
            logger.info(f"[Voice Command Detected] {cmd_name} with args {cmd_args}")
            handler = COMMANDS[cmd_name]
            asyncio.run_coroutine_threadsafe(handler(sid, cmd_args, send_ws), loop)
            if not stripped_text:
                return

        # If session is paused, don't pass transcript to agent
        if is_session_paused(sid):
            logger.info(f"[Session Paused] ignoring transcript '{stripped_text}'")
            return

        if not stripped_text:
            return

        # Deduplicate chunk if identical to recent entry in buffer
        if transcript_buffer and stripped_text.lower() == transcript_buffer[-1].lower():
            return

        transcript_buffer.append(stripped_text)

        if immediate:
            flush_turn()
            return

        if speech_turn_start[0] == 0.0:
            speech_turn_start[0] = time.time()

        elapsed = time.time() - speech_turn_start[0]

        # Condition 1: 15 seconds of continuous speech elapsed -> flush turn
        if elapsed >= 15.0:
            logger.info(f"[15s Speech Interval Reached] Flushing accumulated speech turn to agent (elapsed={elapsed:.1f}s)")
            flush_turn()
            return

        # Condition 2: Wait for speech to stop (2.0s of silence after speech stops)
        if debounce_handle[0]:
            try:
                debounce_handle[0].cancel()
            except Exception:
                pass

        def on_speech_stopped():
            logger.info("[Speech Stop Detected (2s)] Flushing turn to agent")
            flush_turn()

        debounce_handle[0] = loop.call_later(2.0, on_speech_stopped)




    # Initialize STT session
    stt_session = STTSession(loop=loop, on_transcript=on_transcript)
    stt_session.start()

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    await websocket.send_json({
        "type": "status",
        "status": f"Active (Project: {project or 'Local ADC'})",
        "session_id": sid,
    })

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                # Stream raw 16kHz Int16 PCM chunk to STT v2
                stt_session.push_audio(message["bytes"])
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "transcript_event":
                        text = data.get("text", "")
                        is_final = data.get("is_final", False)
                        immediate = data.get("immediate", False)
                        on_transcript(text, is_final, immediate=immediate)

                    elif msg_type in COMMANDS:
                        await COMMANDS[msg_type](sid, data, send_ws)

                    elif msg_type == "command":
                        cmd = data.get("name")
                        args = data.get("args", {})
                        if cmd in COMMANDS:
                            await COMMANDS[cmd](sid, args, send_ws)

                    elif msg_type == "set_language":
                        lang = data.get("language", "en-US")
                        logger.info(f"Session {sid} language set to: {lang}")
                        stt_session.language_code = lang

                    elif msg_type == "tts_playing":
                        # Client audio playback state notification for echo suppression
                        playing = data.get("playing", False)
                        if playing:
                            tts_suppress_until[0] = time.time() + 2.5
                        else:
                            tts_suppress_until[0] = time.time() + 0.9

                except Exception as err:
                    logger.warning(f"Error handling WS JSON message: {err}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected ({sid})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if debounce_handle[0]:
            try:
                debounce_handle[0].cancel()
            except Exception:
                pass
        stt_session.stop()

