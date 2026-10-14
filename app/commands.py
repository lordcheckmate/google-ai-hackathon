"""
Single Command Registry for Voice and Click Parity (Section 8).
Neither path contains logic the other lacks.
"""

import re
import logging
from typing import Dict, Any, Optional, Callable, Tuple

from app.store import get_block, save_block, delete_block, get_blocks, _CACHE, _BLOCKS, get_transcript_history
from app.blocks import render_block
from app.blocks.generate import generate_block_json

logger = logging.getLogger("commands")

# Session state flags
_SESSION_STATES: Dict[str, str] = {}  # sid -> "active" | "paused" | "ended"


def is_session_paused(sid: str) -> bool:
    return _SESSION_STATES.get(sid, "active") == "paused"


# =========================================================================
# Command Handlers
# =========================================================================

async def handle_start(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Start or resume the active meeting session."""
    _SESSION_STATES[sid] = "active"
    logger.info(f"Session {sid} resumed/started")
    await ws_sender({"type": "session_status", "status": "active"})
    return {"status": "ok", "session": "active"}


async def handle_pause(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Pause meeting listening while keeping mic armed."""
    _SESSION_STATES[sid] = "paused"
    logger.info(f"Session {sid} paused")
    await ws_sender({"type": "session_status", "status": "paused"})
    return {"status": "ok", "session": "paused"}


async def handle_end(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """End the meeting session."""
    _SESSION_STATES[sid] = "ended"
    logger.info(f"Session {sid} ended")
    await ws_sender({"type": "session_status", "status": "ended"})
    return {"status": "ok", "session": "ended"}


async def handle_clear(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Clear all blocks from the canvas."""
    blocks = get_blocks(sid)
    for b in blocks:
        delete_block(sid, b["id"])
    _CACHE.clear()
    logger.info(f"Cleared all blocks for session {sid}")
    await ws_sender({"type": "canvas_cleared"})
    return {"status": "ok", "cleared": len(blocks)}


async def handle_undo(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Undo the last added block."""
    blocks = get_blocks(sid)
    if blocks:
        # Sort by updated_at descending
        sorted_blocks = sorted(blocks, key=lambda x: x.get("updated_at", 0), reverse=True)
        target = sorted_blocks[0]
        delete_block(sid, target["id"])
        await ws_sender({"type": "block_remove", "block_id": target["id"]})
        return {"status": "ok", "undone_block_id": target["id"]}
    return {"status": "ok", "message": "Nothing to undo"}


async def handle_toggle(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Toggle a checklist item done status."""
    block_id = args.get("block_id")
    ref = args.get("ref", "")  # e.g. "item:2" or "2"
    record = get_block(sid, block_id)
    if not record or record.get("kind") != "checklist":
        return {"status": "error", "message": "Checklist block not found"}

    item_idx = None
    if ref.startswith("item:"):
        try:
            item_idx = int(ref.split(":")[1])
        except ValueError:
            pass
    elif ref.isdigit():
        item_idx = int(ref)

    block_json = record["json"]
    items = block_json.get("items", [])
    if item_idx is not None and 0 <= item_idx < len(items):
        items[item_idx]["done"] = not items[item_idx].get("done", False)
        markup = render_block("checklist", block_json)
        save_block(sid, block_id, "checklist", block_json, parent=record.get("parent"))

        await ws_sender({
            "type": "block_upsert",
            "block": {
                "id": block_id,
                "kind": "checklist",
                "title": block_json.get("title", "Checklist"),
                "html": markup,
                "parent": record.get("parent"),
                "json": block_json,
            }
        })
        return {"status": "ok", "item_idx": item_idx, "done": items[item_idx]["done"]}

    return {"status": "error", "message": f"Invalid item index {ref}"}


async def handle_inspect(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """
    Section 6b: Clickable content / drilling in.
    Resolves ref, checks cache, generates child block with parent={block_id, ref}.
    """
    block_id = args.get("block_id")
    ref = args.get("ref")

    if not block_id or not ref:
        return {"status": "error", "message": "Missing block_id or ref"}

    record = get_block(sid, block_id)
    if not record:
        return {"status": "error", "message": f"Parent block {block_id} not found"}

    cache_key = f"{sid}:{block_id}:{ref}"

    # Check if a child block with this parent already exists on the canvas (collapse toggle)
    existing_blocks = get_blocks(sid)
    for b in existing_blocks:
        parent = b.get("parent")
        if parent and parent.get("block_id") == block_id and parent.get("ref") == ref:
            # Clicking again collapses it! (Section 6b item 5)
            child_id = b["id"]
            delete_block(sid, child_id)
            await ws_sender({"type": "block_remove", "block_id": child_id})
            return {"status": "collapsed", "child_id": child_id}

    # Check cache by (block_id, ref) (Section 6b rule 1)
    if cache_key in _CACHE:
        cached_record = _CACHE[cache_key]
        child_id = cached_record["id"]
        save_block(sid, child_id, cached_record["kind"], cached_record["json"], parent=cached_record["parent"])
        markup = render_block(cached_record["kind"], cached_record["json"])
        await ws_sender({
            "type": "block_upsert",
            "block": {
                "id": child_id,
                "kind": cached_record["kind"],
                "title": cached_record["json"].get("title", cached_record["kind"]),
                "html": markup,
                "parent": cached_record["parent"],
                "json": cached_record["json"],
            }
        })
        return {"status": "served_from_cache", "child_id": child_id}

    # Resolve ref against stored JSON (Rule 2)
    resolved_subject, suggested_kind = resolve_ref_element(record["kind"], record["json"], ref)
    if not resolved_subject:
        return {"status": "error", "message": f"Ref '{ref}' does not address a real element in {block_id}"}

    # Generate child block
    child_id = f"sub_{block_id}_{ref.replace(':', '_')}"
    parent_ref = {"block_id": block_id, "ref": ref}

    # Prompt instruction to explain this specific element
    instruction = f"Explain in detail this specific element from {record['kind']} block: {resolved_subject}."
    history = get_transcript_history(sid)
    child_json = generate_block_json(suggested_kind, instruction, conversation_history=history)
    markup = render_block(suggested_kind, child_json)

    # Save and cache
    child_record = save_block(sid, child_id, suggested_kind, child_json, parent=parent_ref)
    _CACHE[cache_key] = child_record

    await ws_sender({
        "type": "block_upsert",
        "block": {
            "id": child_id,
            "kind": suggested_kind,
            "title": child_json.get("title", suggested_kind.capitalize()),
            "html": markup,
            "parent": parent_ref,
            "json": child_json,
        }
    })

    return {"status": "created", "child_id": child_id, "kind": suggested_kind}


async def handle_illustrate(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Generate Nano Banana illustration for a flow step."""
    from app.images import generate_step_image

    block_id = args.get("block_id")
    node_label = args.get("node_label") or args.get("ref") or ""

    blocks = get_blocks(sid)
    target_block = None
    if block_id:
        target_block = get_block(sid, block_id)
    else:
        for b in blocks:
            if b.get("kind") == "flow":
                target_block = b
                block_id = b["id"]
                break

    if not target_block or target_block.get("kind") != "flow":
        # If no flow diagram exists yet, create one automatically
        block_id = "process_flow_1"
        block_json = generate_block_json("flow", "First take notes, then show to client, then make decisions.")
        target_block = save_block(sid, block_id, "flow", block_json)
    else:
        block_json = target_block["json"]

    nodes = block_json.get("nodes", [])
    if not nodes:
        return {"status": "error", "message": "Flow diagram contains no steps"}

    # If a specific node is requested, illustrate that node; otherwise illustrate all nodes!
    norm = node_label.strip().lower()
    if norm:
        target_node = None
        for n in nodes:
            if norm in n.get("label", "").lower() or norm == n.get("id", "").lower():
                target_node = n
                break
        if not target_node:
            target_node = nodes[0]
        img_url = generate_step_image(target_node["label"], f"Line icon for {target_node['label']}", is_icon=True)
        target_node["image_url"] = img_url
        illustrated_label = target_node["label"]
    else:
        for n in nodes:
            n["image_url"] = generate_step_image(n["label"], f"Line icon for {n['label']}", is_icon=True)
        illustrated_label = "all steps"

    markup = render_block("flow", block_json)
    save_block(sid, block_id, "flow", block_json, parent=target_block.get("parent"))

    await ws_sender({
        "type": "block_upsert",
        "block": {
            "id": block_id,
            "kind": "flow",
            "title": block_json.get("title", "Process Workflow"),
            "html": markup,
            "parent": target_block.get("parent"),
            "json": block_json,
        }
    })

    return {"status": "ok", "block_id": block_id, "node": illustrated_label}


async def handle_highlight(sid: str, args: Dict[str, Any], ws_sender: Callable) -> Dict[str, Any]:
    """Highlight specified steps or items in real time."""
    labels = args.get("labels", [])
    target = args.get("target") or args.get("node_label")
    if target and not labels:
        labels = [target]

    blocks = get_blocks(sid)
    if not blocks:
        return {"status": "error", "message": "No blocks to highlight"}

    block_id = args.get("block_id")
    target_block = None
    if block_id:
        target_block = get_block(sid, block_id)
    else:
        for b in reversed(blocks):
            if b.get("kind") in ("flow", "checklist"):
                target_block = b
                block_id = b["id"]
                break

    if not target_block:
        target_block = blocks[-1]
        block_id = target_block["id"]

    kind = target_block["kind"]
    block_json = target_block["json"]
    norm_labels = [str(l).strip().lower() for l in labels]

    if kind == "flow":
        for node in block_json.get("nodes", []):
            node_label = str(node.get("label", "")).strip().lower()
            node_id = str(node.get("id", "")).strip().lower()
            node["highlight"] = any(nl in node_label or nl == node_id for nl in norm_labels)
    elif kind == "checklist":
        for item in block_json.get("items", []):
            txt = str(item.get("text", "")).strip().lower()
            item["highlight"] = any(nl in txt for nl in norm_labels)

    markup = render_block(kind, block_json)
    save_block(sid, block_id, kind, block_json, parent=target_block.get("parent"))

    await ws_sender({
        "type": "block_upsert",
        "block": {
            "id": block_id,
            "kind": kind,
            "title": block_json.get("title", kind),
            "html": markup,
            "parent": target_block.get("parent"),
            "json": block_json,
        }
    })
    return {"status": "ok", "block_id": block_id, "highlighted": labels}


def resolve_ref_element(kind: str, block_json: Dict[str, Any], ref: str) -> Tuple[Optional[str], str]:
    """
    Look up the actual node, cell or item from the stored JSON (Section 6b).
    Returns (resolved_subject_description, suggested_block_kind).
    """
    if kind == "flow":
        nodes = block_json.get("nodes", [])
        for n in nodes:
            if n.get("id") == ref or n.get("label", "").lower() == ref.lower():
                label = n.get("label", "")
                note = n.get("note", "")
                desc = f"Process Step: '{label}' ({note})" if note else f"Process Step: '{label}'"
                # Sub-process flow or detailed answer
                return desc, "flow" if "process" in label.lower() or "workflow" in label.lower() else "answer"

    elif kind == "compare":
        options = block_json.get("options", [])
        criteria = block_json.get("criteria", [])
        cells = block_json.get("cells", [])

        if ref.startswith("opt:"):
            try:
                idx = int(ref.split(":")[1])
                if 0 <= idx < len(options):
                    return f"Option '{options[idx]}'", "answer"
            except ValueError:
                pass
        elif ref.startswith("cell:"):
            try:
                _, crit_idx, opt_idx = ref.split(":")
                ci, oi = int(crit_idx), int(opt_idx)
                if 0 <= ci < len(criteria) and 0 <= oi < len(options):
                    val = cells[ci][oi] if ci < len(cells) and oi < len(cells[ci]) else ""
                    return f"Criterion '{criteria[ci]}' for Option '{options[oi]}': {val}", "answer"
            except ValueError:
                pass

    elif kind == "answer":
        sources = block_json.get("sources", [])
        if ref.startswith("src:"):
            try:
                idx = int(ref.split(":")[1])
                if 0 <= idx < len(sources):
                    src = sources[idx]
                    return f"Citation Source '{src.get('title')}': {src.get('url')}", "answer"
            except ValueError:
                pass

    elif kind == "checklist":
        items = block_json.get("items", [])
        if ref.startswith("item:"):
            try:
                idx = int(ref.split(":")[1])
                if 0 <= idx < len(items):
                    item = items[idx]
                    owner = f" (Owner: {item['owner']})" if item.get("owner") else ""
                    return f"Action Item '{item.get('text')}'{owner}", "checklist"
            except ValueError:
                pass

    return None, "answer"


# =========================================================================
# Single Command Registry
# =========================================================================

COMMANDS: Dict[str, Callable] = {
    "start_session": handle_start,
    "pause_session": handle_pause,
    "end_session": handle_end,
    "undo": handle_undo,
    "clear": handle_clear,
    "toggle_item": handle_toggle,
    "inspect": handle_inspect,
    "illustrate_step": handle_illustrate,
    "illustrate": handle_illustrate,
    "highlight": handle_highlight,
}


# =========================================================================
# Voice Path Regex Extractor (Section 8)
# =========================================================================

VOICE_PATTERNS = [
    (r"\b(?:start session|resume session|start meeting|resume meeting)\b", "start_session", lambda m, sid: {}),
    (r"\b(?:pause session|stop session|pause meeting)\b", "pause_session", lambda m, sid: {}),
    (r"\b(?:end session|finish session|end meeting)\b", "end_session", lambda m, sid: {}),
    (r"\b(?:undo that|undo|revert)\b", "undo", lambda m, sid: {}),
    (r"\b(?:clear canvas|clear screen|clear all)\b", "clear", lambda m, sid: {}),
    (r"\b(?:highlight|focus on|emphasize)\s+([a-zA-Z0-9_\-\s]+)", "highlight", lambda m, sid: {"labels": [m.group(1).strip()]}),
    (r"\b(?:illustrate|draw picture for|add picture to|generate image for|draw icon for|nano banana for)\s+([a-zA-Z0-9_\-\s]+)", "illustrate_step", lambda m, sid: {"node_label": m.group(1).strip()}),
    (r"\b(?:illustrate steps?|illustrate flow|draw pictures?|add pictures?|nano banana)\b", "illustrate_step", lambda m, sid: {}),
    (r"(?:tell me more about|explain|inspect)\s+([a-zA-Z0-9_\-\s]+)", "inspect", lambda m, sid: resolve_voice_inspect_args(sid, m.group(1).strip())),
]


def resolve_voice_inspect_args(sid: str, query: str) -> Dict[str, Any]:
    """Find the block_id and ref matching the spoken phrase."""
    blocks = get_blocks(sid)
    norm_query = query.lower()

    for b in blocks:
        b_json = b.get("json", {})
        # Check flow nodes
        for node in b_json.get("nodes", []):
            if norm_query in node.get("label", "").lower() or norm_query == node.get("id", "").lower():
                return {"block_id": b["id"], "ref": node["id"]}

        # Check compare options
        for idx, opt in enumerate(b_json.get("options", [])):
            if norm_query in opt.lower():
                return {"block_id": b["id"], "ref": f"opt:{idx}"}

        # Check checklist items
        for idx, item in enumerate(b_json.get("items", [])):
            if norm_query in item.get("text", "").lower():
                return {"block_id": b["id"], "ref": f"item:{idx}"}

    return {}


def extract_voice_command(sid: str, transcript: str) -> Tuple[Optional[str], Dict[str, Any], str]:
    """
    Checks if final transcript contains a registered voice command.
    If matched, returns (command_name, args, stripped_transcript).
    If no command matches, returns (None, {}, transcript).
    """
    text = transcript.strip()
    for pattern, cmd_name, arg_builder in VOICE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            args = arg_builder(match, sid)
            # Strip command text out so it never reaches agent as content (Section 8)
            stripped = text[:match.start()] + text[match.end():]
            return cmd_name, args, stripped.strip()

    return None, {}, text
