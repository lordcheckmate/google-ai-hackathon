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
from app.store import get_blocks, save_session

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="AI Meeting Assistant")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return PlainTextResponse("ok")


@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok"})


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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    sid = websocket.query_params.get("session_id") or "default_session"
    if websocket.query_params.get("fresh") == "1":
        for b in get_blocks(sid):
            delete_block(sid, b["id"])
    save_session(sid, title="Live Meeting")

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

    # Callback when transcript is produced by STT v2
    def on_transcript(text: str, is_final: bool):
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

        if is_final and text.strip():
            # Check for voice commands first (Section 8)
            cmd_name, cmd_args, stripped_text = extract_voice_command(sid, text)
            if cmd_name:
                logger.info(f"[Voice Command Detected] {cmd_name} with args {cmd_args}")
                handler = COMMANDS[cmd_name]
                asyncio.run_coroutine_threadsafe(handler(sid, cmd_args, send_ws), loop)

            # If session is paused, don't pass transcript to agent
            if is_session_paused(sid):
                logger.info(f"[Session Paused] ignoring transcript '{stripped_text}'")
                return

            if stripped_text:
                # Dispatch turn to ADK Agent
                asyncio.run_coroutine_threadsafe(
                    agent_session.process_turn(stripped_text),
                    loop
                )

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
                        on_transcript(text, is_final)

                    elif msg_type == "inspect":
                        # Section 6b clickable content inspect
                        await COMMANDS["inspect"](sid, data, send_ws)

                    elif msg_type == "toggle_item":
                        # Checklist item click
                        await COMMANDS["toggle_item"](sid, data, send_ws)

                    elif msg_type == "command":
                        cmd = data.get("name")
                        args = data.get("args", {})
                        if cmd in COMMANDS:
                            await COMMANDS[cmd](sid, args, send_ws)

                    elif msg_type == "tts_playing":
                        # Client audio playback state notification for echo suppression
                        playing = data.get("playing", False)
                        if playing:
                            tts_suppress_until[0] = time.time() + 2.0
                        else:
                            tts_suppress_until[0] = time.time() + 0.7

                except Exception as err:
                    logger.warning(f"Error handling WS JSON message: {err}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected ({sid})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        stt_session.stop()
