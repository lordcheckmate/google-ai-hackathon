"""
ADK LlmAgent with tool loop and verbatim system instructions.
Enforces Section 5 (No model ever emits markup) and Section 7 (Agent & Tools).
"""

import os
import time
import json
import logging
import asyncio
import contextvars
from typing import List, Dict, Any, Optional, Callable

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.models import REASONING_MODEL
from app.blocks import render_block
from app.blocks.generate import generate_block_json
from app.store import get_block, save_block, delete_block, get_blocks, log_turn
from app.images import generate_step_image
from app.tts import synthesize_speech

logger = logging.getLogger("agent")

# Context vars for the active turn
_current_sid: contextvars.ContextVar[str] = contextvars.ContextVar("current_sid", default="default")
_current_ws_sender: contextvars.ContextVar[Optional[Callable[[Dict[str, Any]], Any]]] = contextvars.ContextVar("current_ws_sender", default=None)
_current_transcript: contextvars.ContextVar[str] = contextvars.ContextVar("current_transcript", default="")
_current_loop: contextvars.ContextVar[Optional[asyncio.AbstractEventLoop]] = contextvars.ContextVar("current_loop", default=None)


def _emit_ws(payload: Dict[str, Any]):
    """Emit a JSON payload to the active WebSocket client in a thread-safe manner."""
    sender = _current_ws_sender.get()
    loop = _current_loop.get()
    if sender:
        try:
            import inspect
            if inspect.iscoroutinefunction(sender):
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(sender(payload), loop)
                else:
                    try:
                        cur_loop = asyncio.get_running_loop()
                        cur_loop.create_task(sender(payload))
                    except RuntimeError:
                        logger.warning("No running loop to dispatch coroutine sender")
            else:
                sender(payload)
        except Exception as e:
            logger.warning(f"Failed to emit WS payload: {e}")


# =========================================================================
# Section 7 Tools (Exactly these six and no others)
# =========================================================================

def upsert_block(block_id: str, kind: str, instruction: str) -> dict:
    """
    block_id: reuse an existing id to UPDATE that block, or a new id to add one.
    instruction: one plain-language delta, e.g. 'add inspection after processing'
    or 'add Vendor C with the pricing they just gave'. NOT a full restatement.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: upsert_block] sid={sid}, block_id={block_id}, kind={kind}, instruction='{instruction}'")

    existing_record = get_block(sid, block_id)
    existing_json = existing_record.get("json") if existing_record else None
    parent = existing_record.get("parent") if existing_record else None

    # Step 1: Generate typed JSON via Gemini + Pydantic schema
    block_json = generate_block_json(kind, instruction, existing_json)

    # Step 2: Render pure Python deterministic markup (HTML or SVG)
    markup = render_block(kind, block_json)

    # Step 3: Persist block record
    record = save_block(sid, block_id, kind, block_json, parent=parent)

    # Step 4: Log turn audit trail (Section 9)
    latency_ms = (time.time() - t0) * 1000.0
    log_turn(
        sid=sid,
        transcript=transcript,
        tool="upsert_block",
        block_id=block_id,
        kind=kind,
        instruction=instruction,
        json_after=block_json,
        latency_ms=latency_ms,
    )

    # Step 5: Push update to the live canvas over WebSocket
    title = block_json.get("title") or block_json.get("question") or kind.capitalize()
    _emit_ws({
        "type": "block_upsert",
        "block": {
            "id": block_id,
            "kind": kind,
            "title": title,
            "html": markup,
            "parent": parent,
            "json": block_json,
        }
    })

    return {
        "status": "ok",
        "block_id": block_id,
        "kind": kind,
        "title": title,
    }


def remove_block(block_id: str) -> dict:
    """Remove a block from the canvas by block_id."""
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: remove_block] sid={sid}, block_id={block_id}")
    success = delete_block(sid, block_id)

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="remove_block",
        block_id=block_id,
        kind=None,
        instruction=None,
        json_after=None,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    _emit_ws({
        "type": "block_remove",
        "block_id": block_id,
    })

    return {"status": "ok", "removed": block_id, "found": success}


def highlight(block_id: str, labels: list[str]) -> dict:
    """
    Accepts one OR MORE labels. Clears previous highlights in that block.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: highlight] sid={sid}, block_id={block_id}, labels={labels}")
    record = get_block(sid, block_id)
    if not record:
        return {"status": "error", "message": f"Block {block_id} not found"}

    kind = record["kind"]
    block_json = record["json"]
    norm_labels = [l.strip().lower() for l in labels]

    if kind == "flow":
        for node in block_json.get("nodes", []):
            node_label = str(node.get("label", "")).strip().lower()
            node_id = str(node.get("id", "")).strip().lower()
            node["highlight"] = (node_label in norm_labels or node_id in norm_labels)
    elif kind == "checklist":
        for item in block_json.get("items", []):
            txt = str(item.get("text", "")).strip().lower()
            item["highlight"] = any(nl in txt for nl in norm_labels)

    markup = render_block(kind, block_json)
    save_block(sid, block_id, kind, block_json, parent=record.get("parent"))

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="highlight",
        block_id=block_id,
        kind=kind,
        instruction=f"highlight: {labels}",
        json_after=block_json,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    _emit_ws({
        "type": "block_upsert",
        "block": {
            "id": block_id,
            "kind": kind,
            "title": block_json.get("title", kind),
            "html": markup,
            "parent": record.get("parent"),
            "json": block_json,
        }
    })

    return {"status": "ok", "block_id": block_id, "highlighted": labels}


def illustrate_step(block_id: str, node_label: str, visual_description: str) -> dict:
    """
    Nano Banana, flow blocks only. Only when asked for pictures.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: illustrate_step] sid={sid}, block_id={block_id}, node={node_label}")
    record = get_block(sid, block_id)
    if not record or record.get("kind") != "flow":
        return {"status": "error", "message": f"Flow block {block_id} not found"}

    img_url = generate_step_image(node_label, visual_description)
    block_json = record["json"]

    matched = False
    norm_target = node_label.strip().lower()
    for node in block_json.get("nodes", []):
        lbl = str(node.get("label", "")).strip().lower()
        nid = str(node.get("id", "")).strip().lower()
        if norm_target in lbl or norm_target == nid:
            node["image_url"] = img_url
            matched = True
            break

    if matched:
        markup = render_block("flow", block_json)
        save_block(sid, block_id, "flow", block_json, parent=record.get("parent"))

        log_turn(
            sid=sid,
            transcript=transcript,
            tool="illustrate_step",
            block_id=block_id,
            kind="flow",
            instruction=f"illustrate: {node_label}",
            json_after=block_json,
            latency_ms=(time.time() - t0) * 1000.0,
        )

        _emit_ws({
            "type": "block_upsert",
            "block": {
                "id": block_id,
                "kind": "flow",
                "title": block_json.get("title", "Process Workflow"),
                "html": markup,
                "parent": record.get("parent"),
                "json": block_json,
            }
        })
        return {"status": "ok", "node": node_label, "image_url": img_url}

    return {"status": "error", "message": f"Node '{node_label}' not found in flow {block_id}"}


def flag_contradiction(earlier: str, now: str) -> dict:
    """
    Speaks one short question asking which is correct.
    This is the agent's one unprompted behaviour.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: flag_contradiction] earlier='{earlier}', now='{now}'")
    question = f"Earlier you mentioned '{earlier}', but now '{now}'. Which is correct?"
    audio_b64 = synthesize_speech(question)

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="flag_contradiction",
        block_id=None,
        kind=None,
        instruction=f"Contradiction: {earlier} vs {now}",
        json_after=None,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    _emit_ws({
        "type": "contradiction",
        "earlier": earlier,
        "now": now,
        "question": question,
        "audio": audio_b64,
    })

    return {"status": "ok", "question": question}


def read_back(block_id: str | None) -> str:
    """
    Short spoken summary of one block, or of the entire canvas.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    summary_text = ""
    if block_id:
        record = get_block(sid, block_id)
        if record:
            b_json = record.get("json", {})
            title = b_json.get("title") or record.get("kind")
            summary_text = f"Block {title} is currently on the canvas."
        else:
            summary_text = f"Block {block_id} was not found on the canvas."
    else:
        blocks = get_blocks(sid)
        if not blocks:
            summary_text = "The canvas is currently empty."
        else:
            titles = [b.get("json", {}).get("title", b.get("kind")) for b in blocks]
            summary_text = f"The canvas currently contains {len(blocks)} blocks: {', '.join(titles)}."

    audio_b64 = synthesize_speech(summary_text)

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="read_back",
        block_id=block_id,
        kind=None,
        instruction="read_back",
        json_after=None,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    _emit_ws({
        "type": "speak",
        "text": summary_text,
        "audio": audio_b64,
    })

    return summary_text


# =========================================================================
# Verbatim System Instruction from Section 7
# =========================================================================

SYSTEM_INSTRUCTION = """You listen to a meeting and maintain a canvas of blocks showing what is being discussed.
WHEN TO DO NOTHING
Most of what you hear is greetings, filler, half-finished sentences and small talk.
Produce no tool call and no reply for those. Silence is the correct output more often
than not. Only act when something has been described, asked, compared or agreed — or
when you were addressed directly.
CHOOSING WHAT TO SHOW
You decide the representation. Nobody will tell you which to use.
- A sequence of steps, or how work moves through stages -> flow
- Named options being weighed against each other -> compare
- A question with a findable answer -> answer
- Things someone agreed to do, or must be true -> checklist
Pick the one that makes the point visible fastest. If none fits, show nothing.
Never show two blocks that say the same thing in different shapes.
UPDATE, DO NOT DUPLICATE
You can see every block already on the canvas. If the conversation returns to something
already there, call upsert_block with THAT block_id. Create a new block only for a
genuinely new subject. A meeting that revisits a topic four times must end with one
block, not four.
HOW TO CHANGE A BLOCK
Pass ONE short delta describing only what changed. Never restate the whole thing.
"add inspection after processing" — not a list of every step.
Build from the conversation as a whole, not sentence by sentence; if someone is
mid-explanation, wait for the thought to finish.
HIGHLIGHTING
When asked to highlight, pass EVERY item named. If they name two things, pass two.
CONTRADICTIONS
If something said now cannot both be true with something said earlier, call
flag_contradiction once and ask which is right in one short sentence. Do not raise the
same contradiction twice. Do not nitpick wording — only real conflicts.
ADDRESSING YOU
Treat any clear instruction aimed at you as addressed to you. Judge by direction, not
by exact wording — there is no magic phrase.
REPLIES
Spoken replies are one sentence. Never read a block out unless asked.
Never describe what you are about to do; just do it."""


# =========================================================================
# ADK Agent and Runner Factory
# =========================================================================

def create_adk_agent() -> Agent:
    """Build the official Google ADK Agent with Section 7 tools."""
    return Agent(
        name="meeting_assistant",
        model=REASONING_MODEL,
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            upsert_block,
            remove_block,
            highlight,
            illustrate_step,
            flag_contradiction,
            read_back,
        ],
    )


class MeetingAgentSession:
    """Manages an active meeting session with the ADK runner and tool loop."""

    def __init__(self, sid: str, ws_sender: Callable[[Dict[str, Any]], Any], loop: Optional[asyncio.AbstractEventLoop] = None):
        self.sid = sid
        self.ws_sender = ws_sender
        self.loop = loop
        self.agent = create_adk_agent()
        self.runner = InMemoryRunner(agent=self.agent, app_name="ai_meeting_assistant")
        self._session_initialized = False

    async def init_session(self):
        if not self._session_initialized:
            await self.runner.session_service.create_session(
                user_id="operator",
                session_id=self.sid,
                app_name="ai_meeting_assistant",
            )
            self._session_initialized = True

    async def process_turn(self, transcript_text: str):
        """Processes a speech turn through the ADK agent tool loop."""
        if not transcript_text or not transcript_text.strip():
            return

        await self.init_session()

        # Canvas state summary injection (Section 7)
        existing_blocks = get_blocks(self.sid)
        canvas_summary = [
            {"id": b["id"], "kind": b["kind"], "title": b.get("json", {}).get("title", b["kind"])}
            for b in existing_blocks
        ]

        user_content_str = (
            f"CANVAS STATE:\n{json.dumps(canvas_summary, indent=2)}\n\n"
            f"HEARD IN MEETING:\n{transcript_text}"
        )

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_content_str)],
        )

        active_loop = self.loop
        if active_loop is None:
            try:
                active_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        # Bind contextvars for this execution
        token_sid = _current_sid.set(self.sid)
        token_sender = _current_ws_sender.set(self.ws_sender)
        token_transcript = _current_transcript.set(transcript_text)
        token_loop = _current_loop.set(active_loop)

        try:
            async for event in self.runner.run_async(
                user_id="operator",
                session_id=self.sid,
                new_message=content,
            ):
                # If agent produces spoken text reply, synthesize and send
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            text_reply = part.text.strip()
                            if text_reply:
                                audio_b64 = synthesize_speech(text_reply)
                                _emit_ws({
                                    "type": "speak",
                                    "text": text_reply,
                                    "audio": audio_b64,
                                })
        except Exception as e:
            logger.error(f"Error in ADK agent turn: {e}", exc_info=True)
        finally:
            _current_sid.reset(token_sid)
            _current_ws_sender.reset(token_sender)
            _current_transcript.reset(token_transcript)
            _current_loop.reset(token_loop)
