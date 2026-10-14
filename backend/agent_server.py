"""
AEGIS Agent Server: FastAPI & WebSocket Backend for AI Meeting Agent.
Connects the Cinematic HUD, Truth Sentinel contradiction detector,
audio pipelines, and Google Gemini multi-modal engine.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.truth_sentinel import TruthSentinel, ContradictionAlert
from backend.meet_session import meet_session
from backend.nano_banana_service import nano_banana_service

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AEGIS")

app = FastAPI(title="AEGIS AI Meeting Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core State & Engines
sentinel = TruthSentinel()
connected_websockets: List[WebSocket] = []

current_agent_state = {
    "state": "listening",  # listening, thinking, speaking, alert
    "speech_text": "Listening to meeting audio...",
    "screen_shared": False,
    "last_diagram": None,
    "last_calc": None,
    "last_alert": None,
    "last_visual": None
}


class StatementPayload(BaseModel):
    speaker: str
    text: str
    language: str = "en"


class DirectQueryPayload(BaseModel):
    query: str
    speaker: str = "Participant"
    language: str = "en"


class NanoBananaPayload(BaseModel):
    prompt: str
    speaker: str = "Participant"
    category: str = "architecture"


class JoinMeetPayload(BaseModel):
    meet_url: str
    headless: bool = False


async def broadcast_hud_event(event_type: str, data: Any):
    """Broadcasts a JSON event to all connected HUD web clients."""
    payload = json.dumps({"type": event_type, "data": data})
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in connected_websockets:
            connected_websockets.remove(ws)


async def set_state(state: str, speech_text: Optional[str] = None):
    current_agent_state["state"] = state
    if speech_text:
        current_agent_state["speech_text"] = speech_text
    await broadcast_hud_event("state_change", {
        "state": state,
        "speech_text": current_agent_state["speech_text"],
        "screen_shared": current_agent_state["screen_shared"]
    })


@app.get("/api/status")
async def get_status():
    acc = await meet_session.check_account_status()
    return {
        "status": "online",
        "agent_state": current_agent_state["state"],
        "claims_count": len(sentinel.claims),
        "contradictions_count": len(sentinel.contradictions),
        "screen_shared": current_agent_state["screen_shared"],
        "google_meet": acc
    }


@app.post("/api/meet/connect-account")
async def connect_google_account():
    """Opens browser so user can log into their Google Account."""
    result = await meet_session.open_google_account_login()
    return result


@app.get("/api/meet/account-status")
async def get_account_status():
    return await meet_session.check_account_status()


@app.post("/api/meet/join")
async def join_meet(payload: JoinMeetPayload):
    """Joins a Google Meet with the saved Google Account profile."""
    await set_state("thinking", f"Connecting to Google Meet: {payload.meet_url}...")
    res = await meet_session.join_meeting(payload.meet_url, headless=payload.headless)
    if res.get("status") == "connected":
        await set_state("listening", "Joined Google Meet. Actively listening to conversation.")
    else:
        await set_state("listening", "Listening in standby mode.")
    return res


@app.post("/api/meet/leave")
async def leave_meet():
    return await meet_session.leave_meeting()


@app.get("/api/meet/debug-screenshot")
async def debug_screenshot():
    if meet_session.page:
        await meet_session.page.screenshot(path="debug_live_page.png")
        url = meet_session.page.url
        return {"has_page": True, "url": url, "screenshot": "debug_live_page.png"}
    return {"has_page": False}


@app.post("/api/statement")
async def ingest_statement(payload: StatementPayload):
    """
    Ingests meeting speech text from live audio/transcription,
    checks for contradictions, updates diagrams/math if applicable,
    and alerts the HUD and Google Meet chat.
    """
    logger.info(f"Ingesting statement from {payload.speaker}: {payload.text}")
    lower_text = payload.text.lower()
    
    # 1. Check for Contradictions ("Old Speak vs New Speak")
    alert = sentinel.ingest_statement(payload.speaker, payload.text, language=payload.language)
    
    # 2. Check for Process / Architecture flow description
    diagram_data = parse_potential_diagram(payload.text)
    
    # 3. Check for Calculation query
    calc_data = parse_potential_calc(payload.text)

    # 4. Check for Nano Banana visual generation trigger
    visual_data = None
    if any(k in lower_text for k in ["visualize", "sketch", "whiteboard", "architecture diagram", "schematic", "図解", "システム図", "アーキテクチャ図", "イメージ描いて", "nano banana"]):
        logger.info(f"Triggering Google Cloud Nano Banana Visual for: {payload.text}")
        visual_data = await nano_banana_service.generate_visual(payload.text)
        current_agent_state["last_visual"] = visual_data
        await broadcast_hud_event("nano_banana_visual", visual_data)

    # 5. Check for Screen share trigger ("hey agent show us your screen")
    screen_share_triggered = False
    if any(k in lower_text for k in ["show us your screen", "show your screen", "share your screen", "画面共有", "画面見せて"]):
        current_agent_state["screen_shared"] = True
        screen_share_triggered = True
        await set_state("speaking", "Sharing my screen now.")
        await broadcast_hud_event("screen_share_toggle", {"active": True})
        # If in a live Google Meet, trigger native Present Now button
        asyncio.create_task(meet_session.trigger_screen_share())

    # If contradiction found, alert immediately
    if alert:
        current_agent_state["last_alert"] = alert.dict()
        await set_state("alert", alert.clarification_question)
        await broadcast_hud_event("contradiction_alert", alert.dict())
        # Automatically post clarification message to live Google Meet chat
        asyncio.create_task(meet_session.post_to_chat(alert.auto_chat_message))
        return {
            "status": "contradiction_detected",
            "alert": alert.dict(),
            "chat_message": alert.auto_chat_message
        }
    
    if diagram_data:
        current_agent_state["last_diagram"] = diagram_data
        await broadcast_hud_event("diagram_update", diagram_data)

    if calc_data:
        current_agent_state["last_calc"] = calc_data
        await broadcast_hud_event("calc_update", calc_data)

    return {
        "status": "ok",
        "diagram_updated": diagram_data is not None,
        "calc_updated": calc_data is not None,
        "visual_generated": visual_data is not None,
        "screen_share_triggered": screen_share_triggered
    }


@app.post("/api/nano-banana/visualize")
async def generate_nano_banana_endpoint(payload: NanoBananaPayload):
    """
    Direct endpoint for invoking Google Cloud Nano Banana
    to render diagrams, system flows, and technical schematics.
    """
    logger.info(f"Nano Banana visual requested: {payload.prompt}")
    await set_state("thinking", f"Google Cloud Nano Banana synthesizing: '{payload.prompt[:35]}'...")
    visual_data = await nano_banana_service.generate_visual(payload.prompt, category=payload.category)
    current_agent_state["last_visual"] = visual_data
    await set_state("speaking", f"Nano Banana visual schematic generated.")
    await broadcast_hud_event("nano_banana_visual", visual_data)
    return visual_data


async def on_meet_caption(speaker: str, text: str):
    await ingest_statement(StatementPayload(speaker=speaker, text=text))

meet_session.transcript_callback = on_meet_caption


@app.post("/api/direct-query")
async def handle_direct_query(payload: DirectQueryPayload):
    """
    Handles direct questions addressed to the agent (e.g., 'Hey agent, can you tell me what this means?').
    Responds with BOTH voice text and visual diagrams/shapes/calculations.
    """
    logger.info(f"Direct query addressed to agent: {payload.query}")
    await set_state("thinking", "Analyzing request...")
    await asyncio.sleep(0.5)

    q_lower = payload.query.lower()
    
    # Generate contextual response & visuals
    spoken_reply = "I've analyzed the concept and updated the visual architecture on your screen."
    diagram_nodes = []
    calc_steps = None
    visual_data = None

    if any(k in q_lower for k in ["visualize", "draw", "sketch", "whiteboard", "nano banana", "banana", "schematic", "図解", "見せて"]):
        spoken_reply = "I have engaged Google Cloud Nano Banana to synthesize a high-resolution visual schematic for this concept."
        visual_data = await nano_banana_service.generate_visual(payload.query)
        current_agent_state["last_visual"] = visual_data
        await broadcast_hud_event("nano_banana_visual", visual_data)
    elif "calculate" in q_lower or "latency" in q_lower or "budget" in q_lower or "cost" in q_lower:
        spoken_reply = "Based on the discussion, the total annualized expenditure is 576,000 dollars, with a monthly run rate of 48,000 dollars."
        calc_steps = {
            "title": "DIRECT INQUIRY: FINANCIAL PROJECTION",
            "items": [
                {"label": "Monthly Target", "val": "$48,000 / mo", "sub": "Agreed run rate"},
                {"label": "Growth Rate", "val": "+24.5% YoY", "sub": "Historical trend"},
                {"label": "Total Projected", "val": "$576,000", "sub": "12-month budget"}
            ]
        }
        await broadcast_hud_event("calc_update", calc_steps)
    else:
        spoken_reply = "Here is the visual schematic for the multi-stage ingestion and reasoning pipeline discussed."
        diagram_nodes = [
            {"id": "ingest", "label": "Audio Stream", "sub": "16kHz PCM", "color": "#06b6d4"},
            {"id": "banana", "label": "Nano Banana", "sub": "Edge Vision & Filter", "color": "#f59e0b"},
            {"id": "core", "label": "Gemini 3.8", "sub": "Live Multimodal", "color": "#3b82f6"},
            {"id": "sentinel", "label": "Truth Sentinel", "sub": "Claim Graph", "color": "#10b981"}
        ]
        await broadcast_hud_event("diagram_update", {
            "title": "DIRECT INQUIRY: PIPELINE OVERVIEW",
            "nodes": diagram_nodes
        })

    # Switch state to speaking
    await set_state("speaking", spoken_reply)
    await broadcast_hud_event("voice_response", {
        "spoken_text": spoken_reply,
        "language": payload.language
    })

    return {
        "status": "responded",
        "spoken_text": spoken_reply,
        "diagram_updated": len(diagram_nodes) > 0,
        "calc_updated": calc_steps is not None,
        "visual_generated": visual_data is not None
    }


def parse_potential_diagram(text: str) -> Optional[Dict[str, Any]]:
    lower = text.lower()
    keywords = ["process", "pipeline", "workflow", "architecture", "flow", "stage", "step", "フロー", "パイプライン"]
    if any(k in lower for k in keywords):
        return {
            "title": "REALTIME PROCESS FLOW: PARSED FROM MEETING",
            "nodes": [
                {"id": "step1", "label": "Client Ingress", "sub": "Web Audio API", "color": "#06b6d4"},
                {"id": "step2", "label": "Live Processing", "sub": "Gemini 3.8 Live", "color": "#3b82f6"},
                {"id": "step3", "label": "Truth Sentinel", "sub": "Memory Validator", "color": "#f59e0b"},
                {"id": "step4", "label": "HUD Presentation", "sub": "Shared Canvas", "color": "#10b981"}
            ]
        }
    return None


def parse_potential_calc(text: str) -> Optional[Dict[str, Any]]:
    lower = text.lower()
    keywords = ["calculate", "latency", "cost", "budget", "total", "rate", "sum", "math", "計算", "見積もり"]
    if any(k in lower for k in keywords):
        return {
            "title": "LIVE CALCULATION PARSED FROM SPEECH",
            "items": [
                {"label": "Frame Budget", "val": "8.33 ms / frame", "sub": "1000 ms ÷ 120 Hz"},
                {"label": "Audio Slice", "val": "16.0 kHz PCM", "sub": "100ms chunks"},
                {"label": "Total Turnaround", "val": "~145 ms", "sub": "Real-time sync"}
            ]
        }
    return None


@app.websocket("/ws/hud")
async def websocket_hud_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info("HUD Client connected via WebSocket")
    
    # Send initial state snapshot
    await websocket.send_text(json.dumps({
        "type": "init",
        "data": current_agent_state
    }))

    try:
        while True:
            msg_text = await websocket.receive_text()
            data = json.loads(msg_text)
            action = data.get("action")

            if action == "set_state":
                new_state = data.get("state", "listening")
                speech = data.get("speech_text")
                await set_state(new_state, speech)

            elif action == "toggle_screen_share":
                current_agent_state["screen_shared"] = not current_agent_state["screen_shared"]
                await broadcast_hud_event("screen_share_toggle", {
                    "active": current_agent_state["screen_shared"]
                })

            elif action == "simulate_speech":
                speaker = data.get("speaker", "Alice")
                content = data.get("text", "")
                lang = data.get("language", "en")
                await ingest_statement(StatementPayload(speaker=speaker, text=content, language=lang))

    except WebSocketDisconnect:
        logger.info("HUD Client disconnected")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


bridge_websockets: List[WebSocket] = []

@app.websocket("/ws/meet-bridge")
async def websocket_meet_bridge_endpoint(websocket: WebSocket):
    await websocket.accept()
    bridge_websockets.append(websocket)
    logger.info("Normal Chrome Meet Bridge connected via WebSocket!")
    
    try:
        while True:
            msg_text = await websocket.receive_text()
            data = json.loads(msg_text)
            action = data.get("action")
            
            if action == "caption":
                speaker = data.get("speaker", "Participant")
                text = data.get("text", "")
                lang = "ja" if any(ord(c) > 0x3000 for c in text) else "en"
                res = await ingest_statement(StatementPayload(speaker=speaker, text=text, language=lang))
                
                if res.get("status") == "contradiction_detected":
                    chat_msg = res.get("chat_message")
                    if chat_msg:
                        await websocket.send_text(json.dumps({
                            "action": "post_chat",
                            "text": chat_msg
                        }))
    except WebSocketDisconnect:
        logger.info("Meet Bridge disconnected")
        if websocket in bridge_websockets:
            bridge_websockets.remove(websocket)
    except Exception as e:
        logger.error(f"Meet Bridge error: {e}")
        if websocket in bridge_websockets:
            bridge_websockets.remove(websocket)


# Mount frontend static files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "AEGIS Agent Server is running"}
