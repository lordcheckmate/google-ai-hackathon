"""
ADK LlmAgent with tool loop and verbatim system instructions.
Enforces Section 5 (No model ever emits markup) and Section 7 (Agent & Tools).
"""

import os
import re
import ast
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
from app.store import get_block, save_block, delete_block, get_blocks, log_turn, get_transcript_history
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
    Generate or update a block.
    Every generation creates a new dedicated tab version (v1, v2, v3...)
    so the user can review past workflow history.
    instruction: one plain-language delta. Pulls old diagram and adds to it.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: upsert_block] sid={sid}, block_id={block_id}, kind={kind}, instruction='{instruction}'")

    # Inherit from latest existing block of this kind if updating
    existing_blocks_same_kind = [b for b in get_blocks(sid) if b.get("kind") == kind]
    existing_record = get_block(sid, block_id)
    if not existing_record and existing_blocks_same_kind:
        existing_record = existing_blocks_same_kind[-1]

    existing_json = existing_record.get("json") if existing_record else None
    parent = existing_record.get("parent") if existing_record else None

    # Step 1: Generate typed JSON via Gemini + Pydantic schema using full conversation context
    # (Pulls old diagram and adds to it as requested)
    history = get_transcript_history(sid)
    block_json = generate_block_json(kind, instruction, existing_json, conversation_history=history)

    # Every generation gets a new dedicated tab version (v1, v2, v3...)
    total_versions = len(existing_blocks_same_kind) + 1
    base_id = re.sub(r"_v\d+$", "", block_id)
    actual_block_id = f"{base_id}_v{total_versions}"

    raw_title = block_json.get("title") or block_json.get("question") or kind.capitalize()
    raw_title_clean = re.sub(r"\s*\(v\d+\)$", "", raw_title)
    versioned_title = f"{raw_title_clean} (v{total_versions})"
    block_json["title"] = versioned_title

    # Step 2: Render pure Python deterministic markup (HTML or SVG)
    markup = render_block(kind, block_json)

    # Step 3: Persist block record
    record = save_block(sid, actual_block_id, kind, block_json, parent=parent)

    # Step 4: Log turn audit trail (Section 9)
    latency_ms = (time.time() - t0) * 1000.0
    log_turn(
        sid=sid,
        transcript=transcript,
        tool="upsert_block",
        block_id=actual_block_id,
        kind=kind,
        instruction=instruction,
        json_after=block_json,
        latency_ms=latency_ms,
    )

    # Step 5: Push update to the live canvas over WebSocket
    _emit_ws({
        "type": "block_upsert",
        "block": {
            "id": actual_block_id,
            "kind": kind,
            "title": versioned_title,
            "html": markup,
            "parent": parent,
            "json": block_json,
        }
    })

    return {
        "status": "ok",
        "block_id": actual_block_id,
        "kind": kind,
        "title": versioned_title,
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
            node["highlight"] = any(nl in node_label or node_label in nl or nl == node_id for nl in norm_labels)
    elif kind == "checklist":
        for item in block_json.get("items", []):
            txt = str(item.get("text", "")).strip().lower()
            item["highlight"] = any(nl in txt or txt in nl for nl in norm_labels)

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
    Nano Banana step illustration. Generates a dedicated illustration tab at the top.
    Uses Gemini 2.5 Flash Image (Nano Banana) for high-contrast visuals and captions.
    """
    from app.images import generate_nano_banana_image
    import uuid

    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: illustrate_step] sid={sid}, block_id={block_id}, node={node_label}")
    record = get_block(sid, block_id)
    if not record:
        flows = [b for b in get_blocks(sid) if b.get("kind") == "flow"]
        if flows:
            record = flows[-1]
            block_id = record["id"]

    clean_label = node_label.strip()
    img_url, gen_desc = generate_nano_banana_image(
        clean_label,
        visual_description or f"Process illustration for {clean_label}"
    )

    tab_id = f"tab_step_{uuid.uuid4().hex[:6]}"
    tab_json = {
        "kind": "answer",
        "title": f"🖼️ {clean_label[:20].capitalize()}",
        "question": f"Illustration: {clean_label}",
        "answer": gen_desc or visual_description or f"Detailed execution schematic for '{clean_label}'.",
        "detail": f"Generated via Gemini 2.5 Flash Image (Nano Banana).",
        "image_url": img_url,
        "visual_caption": gen_desc or f"Nano Banana visual diagram for {clean_label}.",
        "sources": [{"title": "Gemini 2.5 Flash Image (Nano Banana)", "url": img_url}],
        "confidence": "high",
    }

    parent = {"block_id": block_id, "ref": clean_label} if record else None
    save_block(sid, tab_id, "answer", tab_json, parent=parent)
    markup = render_block("answer", tab_json)

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="illustrate_step",
        block_id=tab_id,
        kind="answer",
        instruction=f"illustrate: {node_label}",
        json_after=tab_json,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    _emit_ws({
        "type": "block_upsert",
        "block": {
            "id": tab_id,
            "kind": "answer",
            "title": f"🖼️ {clean_label[:20].capitalize()}",
            "html": markup,
            "parent": parent,
            "json": tab_json,
        }
    })

    return {"status": "ok", "tab_id": tab_id, "image_url": img_url, "description": gen_desc}


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


def try_parse_and_execute_code_tool_call(text: str) -> bool:
    """
    If the model outputs python tool code as text (e.g. `tool_code print(default_api.upsert_block(...))`),
    parse and execute the tool call.
    """
    tool_funcs = {
        "upsert_block": upsert_block,
        "remove_block": remove_block,
        "highlight": highlight,
        "illustrate_step": illustrate_step,
        "flag_contradiction": flag_contradiction,
        "read_back": read_back,
    }
    match = re.search(r'(?:default_api\.)?(' + '|'.join(tool_funcs.keys()) + r')\s*\((.*?)\)', text, re.DOTALL)
    if not match:
        return False

    func_name = match.group(1)
    args_str = match.group(2).strip()
    try:
        tree = ast.parse(f"func({args_str})")
        call_node = tree.body[0].value
        kwargs = {}
        for kw in call_node.keywords:
            kwargs[kw.arg] = ast.literal_eval(kw.value)
        args = [ast.literal_eval(a) for a in call_node.args]

        func = tool_funcs[func_name]
        logger.info(f"[Code Tool Call Fallback Executed] {func_name} with args={args}, kwargs={kwargs}")
        func(*args, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"Failed to parse and execute code tool call '{func_name}({args_str})': {e}")
        return False


# =========================================================================
# Verbatim System Instruction from Section 7
# =========================================================================

SYSTEM_INSTRUCTION = """You listen to a meeting and maintain a visual neon canvas showing what is being discussed.
IMPORTANT: Always invoke tools using standard tool function calls. Never write Python tool code as plain text.
WHEN TO DO NOTHING
Most of what you hear is greetings, filler, half-finished sentences and small talk.
Produce no tool call and no reply for those. Silence is the correct output more often
than not. Only act when something has been described, asked, compared, agreed, or when you are addressed directly.

AUTONOMOUS VISUALS & NANO BANANA (ALWAYS RUN SHAPE BUILDING OR NANO BANANA OR BOTH)
You decide the representation autonomously without waiting for manual button clicks:
- When a sequence of steps, workflow, pipeline, or stages is described (e.g., 'first X, then Y, then Z') -> IMMEDIATELY call upsert_block ONCE with kind='flow' and block_id='process_flow' containing all the steps in the sequence. Never create separate flow blocks for individual steps!
- When calculations, numbers, metrics, or quantities are discussed (e.g. '10 + 10 units') -> IMMEDIATELY call upsert_block with kind='answer' or kind='flow' showing the visual calculation breakdown.
- Named options being weighed against each other -> IMMEDIATELY call upsert_block with kind='compare'.
- A question with a findable answer -> IMMEDIATELY call upsert_block with kind='answer'.
- Things someone agreed to do, or must be true -> IMMEDIATELY call upsert_block with kind='checklist'.
Pick the one that makes the point visible fastest.
- When asked for pictures, illustrations, or to show a workflow visually, autonomously call illustrate_step for the steps so Nano Banana visual tabs appear at the top. No button clicking required.

EXPLAINING & SPEAKING ALOUD (ALWAYS DRAW PICTURE/DIAGRAM + CAPTION BELOW)
When asked to explain something, answer a question, or clarify:
- NEVER provide an answer with just text!
- ALWAYS generate a visual diagram, picture, or schematic that visually explains the answer, accompanied by a clear caption of explanation directly below it.
- Autonomously generate the visual block in the canvas (flow diagram or illustrated answer card with picture) AND provide a clear, concise one-sentence spoken explanation in your reply so it is spoken aloud via TTS.

HIGHLIGHTING
When asked to highlight, pass EVERY item named to the highlight tool. If they name two things, pass two.

CONTRADICTIONS & SPEAKING OVER
If something said now cannot both be true with something said earlier in the meeting (conflicting dates, requirements, owners, tech choices), IMMEDIATELY call flag_contradiction once. This interrupts and speaks over the meeting with one short question asking which is right. Do not raise the same contradiction twice. Only real conflicts.

UPDATE WITH NEW GENERATION TAB:
Every new generation or diagram update is saved as a new generation version (Workflow v1, Workflow v2...) so users can review the workflow history across tabs. When updating, pass the short delta to upsert_block and it will pull the previous diagram, update it, and create the new version tab.

HOW TO CHANGE A BLOCK
Pass ONE short delta describing only what changed. Never restate the whole thing.
"add inspection after processing" — not a list of every step.

ADDRESSING YOU
Treat any clear instruction aimed at you as addressed to you. Judge by direction, not
by exact wording — there is no magic phrase.

REPLIES & WHEN TO SPEAK
Silence is your default in a meeting. While people speak, focus on silently updating the visual canvas (diagrams, calculations, business processes) without speaking.
Only produce a spoken reply when:
1. You are addressed directly or asked to explain aloud ("hey agent", "tell me", "read back", "can you explain").
2. A contradiction is detected (call flag_contradiction once to speak over).
Never speak confirmations or describe what you are about to do; just update the canvas silently."""


# =========================================================================
# ADK Agent and Runner Factory
# =========================================================================

def create_adk_agent() -> Agent:
    """Build the official Google ADK Agent with Section 7 tools."""
    return Agent(
        name="meeting_assistant",
        model=REASONING_MODEL,
        instruction=SYSTEM_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            temperature=0.1,
        ),
        tools=[
            upsert_block,
            remove_block,
            highlight,
            illustrate_step,
            flag_contradiction,
            read_back,
        ],
    )


ACTIVE_SESSIONS: Dict[str, "MeetingAgentSession"] = {}


async def reset_agent_session(sid: str):
    """Reset the session memory for a given session ID."""
    sess = ACTIVE_SESSIONS.get(sid)
    if sess:
        await sess.reset()


class MeetingAgentSession:
    """Manages an active meeting session with the ADK runner and tool loop."""

    def __init__(self, sid: str, ws_sender: Callable[[Dict[str, Any]], Any], loop: Optional[asyncio.AbstractEventLoop] = None):
        self.sid = sid
        self.ws_sender = ws_sender
        self.loop = loop
        self.agent = create_adk_agent()
        self.runner = InMemoryRunner(agent=self.agent, app_name="ai_meeting_assistant")
        self._session_initialized = False
        ACTIVE_SESSIONS[sid] = self

    async def init_session(self):
        if not self._session_initialized:
            await self.runner.session_service.create_session(
                user_id="operator",
                session_id=self.sid,
                app_name="ai_meeting_assistant",
            )
            self._session_initialized = True

    async def reset(self):
        """Reset the ADK conversation session so history is fresh."""
        try:
            await self.runner.session_service.delete_session(
                user_id="operator",
                session_id=self.sid,
                app_name="ai_meeting_assistant",
            )
            logger.info(f"[MeetingAgentSession] Reset ADK session for {self.sid}")
        except Exception as e:
            logger.debug(f"[MeetingAgentSession] Reset error: {e}")
        self._session_initialized = False

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
                logger.info(f"[ADK Event] type={type(event).__name__} author={getattr(event, 'author', '')} content={getattr(event, 'content', '')}")
                # If agent produces text reply, only speak out loud if explicitly addressed or asked
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            text_reply = part.text.strip()
                            if text_reply:
                                # If the model output python tool code instead of standard function call, execute it
                                if try_parse_and_execute_code_tool_call(text_reply):
                                    continue
                                t_lower = transcript_text.lower()
                                explicitly_asked = any(k in t_lower for k in [
                                    "hey agent", "agent", "assistant", "aegis", "can you tell", "tell me",
                                    "read back", "read the canvas", "explain to us", "explain to me",
                                    "speak", "what do you think", "can you explain", "summarize out loud",
                                    "what is", "how much", "why"
                                ])
                                if explicitly_asked:
                                    audio_b64 = synthesize_speech(text_reply)
                                    _emit_ws({
                                        "type": "speak",
                                        "text": text_reply,
                                        "audio": audio_b64,
                                    })
        except Exception as e:
            logger.error(f"Error in ADK agent turn: {e}", exc_info=True)
        finally:
            _emit_ws({"type": "turn_complete"})
            _current_sid.reset(token_sid)
            _current_ws_sender.reset(token_sender)
            _current_transcript.reset(token_transcript)
            _current_loop.reset(token_loop)
