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
_current_tool_count: contextvars.ContextVar[int] = contextvars.ContextVar("current_tool_count", default=0)



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
    Generate or update a structured visual canvas block.

    Args:
        block_id: Topic-specific ID (e.g. 'use_cases_overview', 'use_case_1_salesforce', 'use_case_2_enrichment', 'checklist_actions', 'pricing_compare').
            IMPORTANT: Every distinct process or use case MUST have its own unique block_id.
            Never reuse the same block_id for different use cases or different processes!
        kind: 'flow' (process diagram), 'compare' (comparison table), 'answer' (calculation/metrics card), or 'checklist' (todos).
        instruction: Plain-language description of what to visualize or what delta to apply.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get()
    t0 = time.time()

    logger.info(f"[Tool: upsert_block] sid={sid}, block_id={block_id}, kind={kind}, instruction='{instruction}'")

    # 0. Strict recursion limit: maximum one upsert per speech turn
    tool_count = _current_tool_count.get()
    if tool_count >= 1:
        logger.warning(f"[upsert_block: recursion prevented] Already executed a canvas tool in this turn (count={tool_count}). Halting loop.")
        return {
            "status": "completed",
            "message": "Canvas was already updated for this turn. Do not call upsert_block again."
        }
    _current_tool_count.set(tool_count + 1)

    instr_lower = instruction.lower().strip()
    norm_instr = instr_lower.strip(" .!?,")

    # 1. Guard against small-talk and greetings modifying the canvas
    greetings = {
        "hello", "hi", "hey", "how are you", "good morning", "good afternoon",
        "good evening", "how are you doing", "how's it going", "can you hear me",
        "testing", "test", "thanks", "thank you", "bye", "goodbye", "ok", "okay"
    }
    if norm_instr in greetings or any(g in norm_instr for g in ["how are you", "good morning", "can you hear me", "how are you doing"]):
        logger.info(f"[upsert_block: ignored greeting/small-talk] '{instruction}'")
        return {"status": "ignored", "reason": "Greetings and small talk do not modify the canvas."}

    # 2. Guard against premature flow creation before any actual steps are mentioned
    if kind == "flow":
        has_sequence = any(w in instr_lower for w in [
            "first", "then", "after", "next", "finally", "step 1", "step 2", "stage", "->", "followed by", "begins with"
        ]) or ("," in instruction and len(instruction.split(",")) >= 3)

        is_mere_announcement = any(instr_lower.startswith(p) or instr_lower == p for p in [
            "i have a business process", "we have a business process", "i have a process",
            "we have a process", "there is a process", "let's discuss a process",
            "new business process", "a business process", "business process", "let's start", "start process"
        ])
        if is_mere_announcement and not has_sequence:
            logger.info(f"[upsert_block: ignored premature flow announcement] '{instruction}' without actual steps.")
            return {"status": "ignored", "reason": "Waiting for participants to describe the actual steps of the process."}

    # Topic isolation: detect if the instruction targets a specific use case or new topic
    base_id = re.sub(r"_v\d+$", "", block_id).strip().lower()

    # Detect Use Case mentions (e.g., "use case 1", "use case 2")
    uc_match = re.search(r"use[\s_-]*case[\s_-]*(\d+|[a-zA-Z]+)", instruction, re.IGNORECASE)
    if uc_match:
        uc_num = uc_match.group(1).lower()
        if base_id in ("process_flow", "flow", "workflow", "block", "default") or not base_id.startswith(f"use_case_{uc_num}"):
            base_id = f"use_case_{uc_num}"
    elif base_id in ("process_flow", "flow", "workflow", "block", "default"):
        # Derive topic slug from instruction keywords to prevent collision
        words = re.findall(r"[a-zA-Z0-9]+", instr_lower)
        stop_words = {"create", "the", "a", "an", "flow", "process", "add", "step", "is", "for", "in", "to", "of", "and", "new"}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        if keywords:
            base_id = "_".join(keywords[:3])

    # Look for existing blocks matching this specific topic/base_id
    matching_topic_blocks = [
        b for b in get_blocks(sid)
        if re.sub(r"_v\d+$", "", b.get("id", "")) == base_id
    ]

    is_explicit_new = any(instr_lower.startswith(prefix) for prefix in ["create a new", "create new", "start a new", "start new"])

    if is_explicit_new and matching_topic_blocks:
        existing_record = None
        existing_json = None
        parent = None
    else:
        existing_record = matching_topic_blocks[-1] if matching_topic_blocks else None
        existing_json = existing_record.get("json") if existing_record else None
        parent = existing_record.get("parent") if existing_record else None

    # Step 1: Generate typed JSON via Gemini + Pydantic schema using full conversation context
    # (Pulls old diagram of this specific topic only and adds to it if updating)
    history = get_transcript_history(sid)
    block_json = generate_block_json(kind, instruction, existing_json, conversation_history=history)

    # Every generation of this topic gets a new dedicated tab version (v1, v2, v3...)
    total_versions = len(matching_topic_blocks) + 1
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

    # Auto-title session if it currently has a default title
    try:
        from app.store import _SESSIONS, update_session_title
        sess = _SESSIONS.get(sid)
        if sess and sess.get("title") in ("New Meeting", "Meeting Session", "Live Meeting", "default_session"):
            clean_name = raw_title_clean[:35].strip()
            update_session_title(sid, clean_name)
            _emit_ws({
                "type": "session_title_updated",
                "session_id": sid,
                "title": clean_name,
            })
    except Exception as e:
        logger.debug(f"Auto-title error: {e}")

    return {
        "status": "ok",
        "block_id": actual_block_id,
        "kind": kind,
        "title": versioned_title,
    }


def remove_step(step: str, block_id: str = "") -> dict:
    """
    Remove a specific step or node from the active flow diagram or checklist.
    Connects the surrounding steps together seamlessly. Use this whenever the user
    asks to remove, delete, drop, or omit a step from an existing process.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get() or ""
    t0 = time.time()

    logger.info(f"[Tool: remove_step] sid={sid}, block_id={block_id}, step={step}")
    from app.matcher import remove_step_from_flow, remove_item_from_checklist

    blocks = get_blocks(sid)
    if not blocks:
        return {"status": "error", "message": "No blocks on canvas"}

    target_block = None
    if block_id:
        target_block = get_block(sid, block_id)
        if not target_block:
            matching = [b for b in blocks if re.sub(r"_v\d+$", "", b.get("id", "")) == re.sub(r"_v\d+$", "", block_id)]
            if matching:
                target_block = matching[-1]

    if not target_block:
        for b in reversed(blocks):
            if b.get("kind") in ("flow", "checklist"):
                target_block = b
                break
    if not target_block:
        target_block = blocks[-1]

    kind = target_block.get("kind")
    block_json = target_block.get("json", {})
    orig_id = target_block.get("id", "")

    if kind == "flow":
        updated_flow, removed_node = remove_step_from_flow(block_json, step)
        if not removed_node:
            return {"status": "error", "message": f"Step '{step}' not found in flow diagram"}

        base_id = re.sub(r"_v\d+$", "", orig_id)
        matching_versions = [b for b in blocks if re.sub(r"_v\d+$", "", b.get("id", "")) == base_id]
        next_version = len(matching_versions) + 1
        new_block_id = f"{base_id}_v{next_version}"

        raw_title = updated_flow.get("title") or "Workflow"
        raw_title_clean = re.sub(r"\s*\(v\d+\)$", "", raw_title)
        versioned_title = f"{raw_title_clean} (v{next_version})"
        updated_flow["title"] = versioned_title

        markup = render_block("flow", updated_flow)
        save_block(sid, new_block_id, "flow", updated_flow, parent=target_block.get("parent"))

        log_turn(
            sid=sid,
            transcript=transcript,
            tool="remove_step",
            block_id=new_block_id,
            kind="flow",
            instruction=f"remove_step: {step}",
            json_after=updated_flow,
            latency_ms=(time.time() - t0) * 1000.0,
        )

        _emit_ws({
            "type": "block_upsert",
            "block": {
                "id": new_block_id,
                "kind": "flow",
                "title": versioned_title,
                "html": markup,
                "parent": target_block.get("parent"),
                "json": updated_flow,
            }
        })
        return {"status": "ok", "block_id": new_block_id, "removed_step": removed_node.get("label")}

    elif kind == "checklist":
        updated_chk, removed_item = remove_item_from_checklist(block_json, step)
        if not removed_item:
            return {"status": "error", "message": f"Item '{step}' not found in checklist"}

        base_id = re.sub(r"_v\d+$", "", orig_id)
        matching_versions = [b for b in blocks if re.sub(r"_v\d+$", "", b.get("id", "")) == base_id]
        next_version = len(matching_versions) + 1
        new_block_id = f"{base_id}_v{next_version}"

        raw_title = updated_chk.get("title") or "Checklist"
        raw_title_clean = re.sub(r"\s*\(v\d+\)$", "", raw_title)
        versioned_title = f"{raw_title_clean} (v{next_version})"
        updated_chk["title"] = versioned_title

        markup = render_block("checklist", updated_chk)
        save_block(sid, new_block_id, "checklist", updated_chk, parent=target_block.get("parent"))

        log_turn(
            sid=sid,
            transcript=transcript,
            tool="remove_step",
            block_id=new_block_id,
            kind="checklist",
            instruction=f"remove_item: {step}",
            json_after=updated_chk,
            latency_ms=(time.time() - t0) * 1000.0,
        )

        _emit_ws({
            "type": "block_upsert",
            "block": {
                "id": new_block_id,
                "kind": "checklist",
                "title": versioned_title,
                "html": markup,
                "parent": target_block.get("parent"),
                "json": updated_chk,
            }
        })
        return {"status": "ok", "block_id": new_block_id, "removed_item": removed_item.get("text")}

    return {"status": "error", "message": f"Block kind '{kind}' does not support step removal"}


def remove_block(block_id: str, target: str = "") -> dict:
    """
    Remove an entire visual block/diagram from the canvas.
    Note: If asked to remove a single step from a diagram, use remove_step instead.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get() or ""
    t0 = time.time()

    # Safety Fallback: Did Gemini call remove_block when the user actually asked to remove a step?
    from app.matcher import match_items
    blocks = get_blocks(sid)

    # If target step is provided, delegate to remove_step
    if target:
        return remove_step(step=target, block_id=block_id)

    # Check if block_id actually matches a node label rather than a block ID
    latest_flow = next((b for b in reversed(blocks) if b.get("kind") == "flow"), None)
    if latest_flow:
        nodes = latest_flow.get("json", {}).get("nodes", [])
        if match_items(block_id, nodes, text_key="label", id_key="id"):
            logger.info(f"[remove_block fallback] block_id '{block_id}' matched a step label -> routing to remove_step")
            return remove_step(step=block_id, block_id=latest_flow.get("id"))

    # Also check if user transcript explicitly asked to remove a step/node
    step_match = re.search(r"\b(?:remove|delete|take\s+out|drop|omit)\s+(?:the\s+)?(?:step\s+)?([a-zA-Z0-9_\-\s]+)", transcript, re.IGNORECASE)
    if step_match and latest_flow:
        candidate_step = step_match.group(1).strip()
        nodes = latest_flow.get("json", {}).get("nodes", [])
        if match_items(candidate_step, nodes, text_key="label", id_key="id"):
            logger.info(f"[remove_block fallback] transcript requested step removal '{candidate_step}' -> routing to remove_step")
            return remove_step(step=candidate_step, block_id=latest_flow.get("id"))

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
    Accepts one OR MORE labels. Clears previous highlights in that block and highlights target items.
    """
    sid = _current_sid.get()
    transcript = _current_transcript.get() or ""
    t0 = time.time()

    logger.info(f"[Tool: highlight] sid={sid}, block_id={block_id}, labels={labels}")
    from app.matcher import match_items

    blocks = get_blocks(sid)
    record = None
    if block_id:
        record = get_block(sid, block_id)
        if not record:
            matching = [b for b in blocks if re.sub(r"_v\d+$", "", b.get("id", "")) == re.sub(r"_v\d+$", "", block_id)]
            if matching:
                record = matching[-1]
                block_id = record["id"]

    if not record:
        for b in reversed(blocks):
            if b.get("kind") in ("flow", "checklist"):
                record = b
                block_id = b["id"]
                break

    if not record and blocks:
        record = blocks[-1]
        block_id = record["id"]

    if not record:
        return {"status": "error", "message": f"No block found to highlight"}

    kind = record["kind"]
    block_json = record["json"]

    if kind == "flow":
        nodes = block_json.get("nodes", [])
        matched = match_items(labels, nodes, text_key="label", id_key="id")
        matched_ids = {n.get("id") for n in matched}
        for node in nodes:
            node["highlight"] = node.get("id") in matched_ids
    elif kind == "checklist":
        items = block_json.get("items", [])
        matched = match_items(labels, items, text_key="text", id_key="id")
        matched_set = {id(it) for it in matched}
        for item in items:
            item["highlight"] = id(item) in matched_set

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
    Uses Gemini 3.1 Flash Lite Image for high-speed high-contrast visuals.
    Runs asynchronously in parallel with speech and reasoning so there is ZERO waiting time.
    """
    from app.images import generate_nano_banana_image
    import uuid
    import threading

    sid = _current_sid.get()
    transcript = _current_transcript.get()
    sender = _current_ws_sender.get()
    loop = _current_loop.get()
    t0 = time.time()

    tool_count = _current_tool_count.get()
    if tool_count >= 2:
        logger.warning(f"[illustrate_step: recursion prevented] Already executed {tool_count} tools in this turn. Halting loop.")
        return {
            "status": "completed",
            "message": "Turn limit reached. Conclude turn."
        }
    _current_tool_count.set(tool_count + 1)

    logger.info(f"[Tool: illustrate_step] sid={sid}, block_id={block_id}, node={node_label}")
    record = get_block(sid, block_id)
    if not record:
        flows = [b for b in get_blocks(sid) if b.get("kind") == "flow"]
        if flows:
            record = flows[-1]
            block_id = record["id"]

    clean_label = node_label.strip()
    norm_label = clean_label.lower().strip(" .!?,")
    greetings = {
        "hello", "hi", "hey", "how are you", "good morning", "good afternoon",
        "good evening", "how are you doing", "how's it going", "can you hear me",
        "testing", "test", "thanks", "thank you", "bye", "goodbye", "ok", "okay"
    }
    if norm_label in greetings or any(g in norm_label for g in ["how are you", "good morning", "can you hear me", "how are you doing"]):
        logger.info(f"[illustrate_step: ignored greeting/small-talk] '{node_label}'")
        return {"status": "ignored", "reason": "Greetings and small talk cannot be illustrated."}

    if norm_label in ("business process", "process", "workflow", "pipeline", "meeting") and not visual_description:
        logger.info(f"[illustrate_step: ignored generic label without visual description] '{node_label}'")
        return {"status": "ignored", "reason": "Cannot illustrate generic label without a concrete subject."}

    tab_id = f"tab_step_{uuid.uuid4().hex[:6]}"
    parent = {"block_id": block_id, "ref": clean_label} if record else None

    # Step 1: Instantly emit a sleek loading placeholder tab (<10ms)
    loading_title = f"🎨 {clean_label[:18].capitalize()}..."
    loading_json = {
        "kind": "answer",
        "title": loading_title,
        "question": f"Illustration: {clean_label}",
        "answer": visual_description or f"Synthesizing high-contrast illustration for '{clean_label}'...",
        "detail": "Generating via Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite)...",
        "image_url": "loading",
        "visual_caption": f"Synthesizing visual illustration for '{clean_label}' in parallel...",
        "sources": [{"title": "Gemini 3.1 Flash-Lite Image", "url": "#"}],
        "confidence": "high",
    }
    save_block(sid, tab_id, "answer", loading_json, parent=parent)
    markup = render_block("answer", loading_json)

    _emit_ws({
        "type": "block_upsert",
        "block": {
            "id": tab_id,
            "kind": "answer",
            "title": loading_title,
            "html": markup,
            "parent": parent,
            "json": loading_json,
        }
    })

    # Step 2: Background worker generates the image via gemini-3.1-flash-lite-image concurrently
    def _bg_generate():
        try:
            img_url, gen_desc = generate_nano_banana_image(
                clean_label,
                visual_description or f"Process illustration for {clean_label}"
            )
            final_title = f"🎨 {clean_label[:20].capitalize()}"
            final_json = {
                "kind": "answer",
                "title": final_title,
                "question": f"Illustration: {clean_label}",
                "answer": gen_desc or visual_description or f"Detailed execution schematic for '{clean_label}'.",
                "detail": "Generated via Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite).",
                "image_url": img_url,
                "visual_caption": gen_desc or f"Nano Banana visual diagram for {clean_label}.",
                "sources": [{"title": "Gemini 3.1 Flash-Lite Image", "url": img_url}],
                "confidence": "high",
            }
            save_block(sid, tab_id, "answer", final_json, parent=parent)
            final_markup = render_block("answer", final_json)

            payload = {
                "type": "block_upsert",
                "block": {
                    "id": tab_id,
                    "kind": "answer",
                    "title": final_title,
                    "html": final_markup,
                    "parent": parent,
                    "json": final_json,
                }
            }
            if sender and loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(sender(payload), loop)
            logger.info(f"[illustrate_step: async completed] tab_id={tab_id}, img_url={img_url}")

            # Also attach image directly over the parent diagram step / comparison table!
            if block_id:
                try:
                    latest_parent = get_block(sid, block_id)
                    if latest_parent:
                        p_kind = latest_parent.get("kind")
                        p_json = latest_parent.get("json", {})
                        updated_parent = False
                        if p_kind == "flow" and "nodes" in p_json:
                            for n in p_json["nodes"]:
                                n_lbl = n.get("label", "").lower()
                                c_lbl = clean_label.lower()
                                if n.get("id") == clean_label or c_lbl in n_lbl or n_lbl in c_lbl:
                                    n["image_url"] = img_url
                                    updated_parent = True
                                    break
                            if not updated_parent and p_json["nodes"]:
                                p_json["nodes"][0]["image_url"] = img_url
                                updated_parent = True
                        elif p_kind == "compare":
                            p_json["image_url"] = img_url
                            updated_parent = True

                        if updated_parent:
                            save_block(sid, block_id, p_kind, p_json, parent=latest_parent.get("parent"))
                            parent_markup = render_block(p_kind, p_json)
                            parent_payload = {
                                "type": "block_upsert",
                                "block": {
                                    "id": block_id,
                                    "kind": p_kind,
                                    "title": p_json.get("title", p_kind),
                                    "html": parent_markup,
                                    "parent": latest_parent.get("parent"),
                                    "json": p_json,
                                }
                            }
                            if sender and loop and loop.is_running():
                                asyncio.run_coroutine_threadsafe(sender(parent_payload), loop)
                            logger.info(f"[illustrate_step] Attached picture over parent {p_kind} block {block_id}")
                except Exception as p_err:
                    logger.warning(f"Failed to update parent block with image: {p_err}")
        except Exception as err:
            logger.error(f"[illustrate_step: async error] {err}", exc_info=True)

    threading.Thread(target=_bg_generate, daemon=True).start()

    log_turn(
        sid=sid,
        transcript=transcript,
        tool="illustrate_step",
        block_id=tab_id,
        kind="answer",
        instruction=f"illustrate: {node_label} (parallel async dispatched)",
        json_after=loading_json,
        latency_ms=(time.time() - t0) * 1000.0,
    )

    return {"status": "ok", "tab_id": tab_id, "state": "generating"}


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


def read_back(block_id: str = "") -> str:
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
        "remove_step": remove_step,
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

SYSTEM_INSTRUCTION = """You listen to a live meeting and maintain a visual neon canvas showing what is being discussed.
IMPORTANT: Always invoke tools using standard tool function calls. Never write Python tool code as plain text.

CRITICAL RULE #0: STRICT ONE-TOOL-CALL-PER-TURN LIMIT:
Once you call upsert_block, illustrate_step, remove_step, or any visual tool, YOUR TURN IS 100% FINISHED.
NEVER call upsert_block repeatedly in a loop! Never call more than one visual tool per turn!
After calling a tool, conclude the turn immediately with empty text or silence unless asked aloud.

CRITICAL RULE #1: WHEN TO REMAIN TOTALLY SILENT (DO NOT TOUCH CANVAS / NO TOOL CALLS):
1. GREETINGS & SOCIAL CHIT-CHAT:
   - For ANY greeting, check-in, or small talk (e.g., "hello", "hi", "hey", "how are you", "good morning", "can you hear me", "are you there", "thanks", "okay", "let's get started"):
     * NEVER call ANY tool! NEVER call upsert_block! NEVER call illustrate_step!
     * DO NOT modify the canvas! DO NOT generate diagrams, cards, or pictures!
     * If someone directly asks you "How are you?" or says "Hello", output ONLY a brief polite spoken reply in plain text (e.g. "I'm doing well, ready to map your meeting discussions.") with ZERO tool calls!
2. PREMATURE TOPIC ANNOUNCEMENTS WITHOUT CONCRETE STEPS:
   - When someone says "I have a business process", "we need a workflow", "let's discuss our pipeline", "I want to share a process", or introduces an upcoming topic BEFORE stating what the actual steps are:
     * DO NOT CALL upsert_block! DO NOT CALL illustrate_step!
     * NEVER hallucinate, invent, or create empty/dummy placeholder steps!
     * WAIT until the speakers actually explain the concrete steps (e.g., "First X, then Y, then Z"). Only when real steps are described do you generate a flow!
3. CASUAL / OFF-TOPIC REMARKS:
   - Produce no tool call and no visual for banter, filler, half-finished sentences, or small talk. Silence is your primary state.

CRITICAL RULE #2: WHEN TO GENERATE VISUALS (CONCRETE MEETING TOPICS & EXPLICIT REQUESTS ONLY):
Only call visual tools when CONCRETE, SUBSTANTIVE information is provided or explicitly requested:
1. PROCESS FLOWS & WORKFLOWS:
   - Call upsert_block with kind='flow' and a topic-specific block_id ONLY when at least TWO concrete sequence steps are explicitly described or when a specific existing step is modified (e.g. 'first X, then Y', 'add step Z after X').
   - NEVER create a flow diagram if no actual steps have been described!
2. COMPARISONS & TABLES:
   - Call upsert_block with kind='compare' ONLY when named options are explicitly being evaluated against criteria (e.g. 'Option A vs Option B').
3. METRICS & BUDGET:
   - Call upsert_block with kind='answer' ONLY when specific numbers, financial calculations, or budget quantities are discussed.
4. ACTION ITEMS & CHECKLISTS:
   - Call upsert_block with kind='checklist' ONLY when concrete tasks with assignees or deadlines are agreed upon.
5. NANO BANANA PICTURES (GEMINI 3.1 FLASH LITE IMAGE):
   - Call illustrate_step ONLY when:
     a) The user explicitly asks for an illustration, picture, image, or logo (e.g. "illustrate step 2", "generate a picture for X", "draw a logo for Y").
     b) OR a concrete, meaningful step in an existing workflow genuinely warrants a visual schematic.
   - NEVER call illustrate_step on greetings, chit-chat, or vague statements!

REMOVING STEPS VS REMOVING BLOCKS:
- When asked to remove, delete, drop, or omit a STEP from a diagram (e.g. "remove the pre-meeting survey step", "delete step 2", "drop consent step"):
  Call remove_step(step="<step name or index>")! NEVER call remove_block!
  remove_step will update the diagram, reconnect surrounding steps, and increment the diagram version on the timeline.
- Only call remove_block when the user explicitly asks to delete an ENTIRE diagram, card, or table from the canvas (e.g. "delete the communication diagram", "remove this workflow").

HIGHLIGHTING:
When asked to highlight, pass EVERY item named to the highlight tool. If they name two things, pass both (e.g. labels=["record meeting", "save notes"]).

EXPLAINING & SPEAKING ALOUD:
When asked to explain something verbally or answer a substantive question aloud:
- If asked a conversational greeting ("how are you?"), reply with a short text sentence only (NO visual tools).
- For substantive explanations, provide a clear, concise 1-2 sentence spoken explanation in your text response so it is spoken aloud via TTS.
- Only generate a visual block if a concrete visual representation was specifically asked for or enhances the explanation.

CONTRADICTIONS & SPEAKING OVER:
If something said now cannot both be true with something said earlier in the meeting (e.g. earlier agreeing a step is required or done, but now someone says to skip it, cancel it, bypass it, or do the opposite; or conflicting dates, requirements, owners, tech choices), IMMEDIATELY call flag_contradiction once. This interrupts and speaks over the meeting with one short question asking which is right. Do not raise the same contradiction twice. Only real conflicts.

TIMELINE OF GENERATIONS:
Every generation is appended to the interactive timeline. The canvas displays the latest generation by default.
When discussing a DIFFERENT use case or new process, ALWAYS use a NEW descriptive block_id (e.g. use_case_1_salesforce, use_case_2_data_cleaning).

HOW TO CHANGE A BLOCK:
Pass ONE short delta describing only what changed. Never restate the whole thing.
"add inspection after processing" — not a list of every step.

ADDRESSING YOU:
Treat any clear instruction aimed at you as addressed to you.

MULTILINGUAL & JAPANESE SUPPORT:
You fully support both Japanese (日本語) and English.
- When speakers converse in Japanese:
  * Generate diagram titles, steps, and notes in natural Japanese (e.g. 「クライアント連絡」「ノート保存」「事前アンケート送付」).
  * Remain 100% completely silent while they talk. Do NOT say greetings, confirmations, or interject!
- When speakers converse in English, maintain English.
- Always match the primary language being spoken by the participants.

REPLIES & WHEN TO SPEAK:
SILENCE IS MANDATORY. Human attendees are in a meeting talking to EACH OTHER, not to you!
- When people say "こんにちは", "よろしくお願いします", "hello", "good morning", stay 100% SILENT.
- NEVER speak confirmations ("わかりました", "図を作成しました", "I have updated the flow") or commentary.
- NEVER speak unless a participant DIRECTLY calls your name ("Hey Aegis", "エイジス", "エージス", "エージェント") and asks you to speak aloud!
- In all other circumstances, your text response MUST be completely EMPTY. Just update the canvas silently."""




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
            temperature=0.1,
        ),
        tools=[
            upsert_block,
            remove_step,
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
        self._lock = asyncio.Lock()
        self._is_busy = False
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
        """Processes a speech turn through the ADK agent tool loop with concurrency guard."""
        if not transcript_text or not transcript_text.strip():
            return

        if self._is_busy:
            logger.info(f"[MeetingAgentSession] Agent busy, dropping concurrent turn to prevent stampede: '{transcript_text[:60]}'")
            return

        async with self._lock:
            self._is_busy = True
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
            token_tool_count = _current_tool_count.set(0)

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
                                    explicitly_addressed = any(name in t_lower for name in [
                                        "hey aegis", "aegis", "hey agent", "エイジス", "エージス", "エージェント"
                                    ])
                                    if explicitly_addressed:
                                        audio_b64 = synthesize_speech(text_reply)
                                        _emit_ws({
                                            "type": "speak",
                                            "text": text_reply,
                                            "audio": audio_b64,
                                        })
                                    else:
                                        # Do NOT speak aloud! Never interrupt meeting speakers with audio
                                        _emit_ws({
                                            "type": "speak",
                                            "text": text_reply,
                                            "audio": None,
                                        })
            except Exception as e:

                logger.error(f"Error in ADK agent turn: {e}", exc_info=True)
            finally:
                self._is_busy = False
                _emit_ws({"type": "turn_complete"})
                _current_sid.reset(token_sid)
                _current_ws_sender.reset(token_sender)
                _current_transcript.reset(token_transcript)
                _current_loop.reset(token_loop)
                _current_tool_count.reset(token_tool_count)


