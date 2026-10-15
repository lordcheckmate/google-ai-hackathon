"""
Storage and persistence module for sessions, blocks, and turns.
Supports Google Cloud Firestore with zero-dependency in-memory cache for offline/local development.
Schema (Section 9):
- sessions/{sid} {created_at, title, status}
- sessions/{sid}/blocks/{block_id} {kind, json, order, updated_at, version, parent}
- sessions/{sid}/turns/{auto} {ts, transcript, tool, block_id, kind, instruction, json_after, latency_ms}
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("store")

# In-memory storage cache
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_BLOCKS: Dict[str, Dict[str, Dict[str, Any]]] = {}  # sid -> {block_id -> block_record}
_TURNS: Dict[str, List[Dict[str, Any]]] = {}  # sid -> list of turns
_CACHE: Dict[str, Dict[str, Any]] = {}  # (block_id, ref) -> child_block cache for section 6b

_firestore_client = None


def get_firestore_client():
    """Lazy initialize Firestore client if credentials exist."""
    global _firestore_client
    if _firestore_client is None:
        try:
            from google.cloud import firestore
            project = os.getenv("GOOGLE_CLOUD_PROJECT")
            if project:
                _firestore_client = firestore.Client(project=project)
                logger.info(f"Connected to Firestore project: {project}")
        except Exception as e:
            logger.debug(f"Firestore not initialized ({e}); using local memory store.")
    return _firestore_client


def save_session(sid: str, title: str = "Meeting Session") -> Dict[str, Any]:
    sess = {
        "sid": sid,
        "title": title,
        "status": "active",
        "created_at": time.time(),
    }
    _SESSIONS[sid] = sess
    if sid not in _BLOCKS:
        _BLOCKS[sid] = {}
    if sid not in _TURNS:
        _TURNS[sid] = []

    db = get_firestore_client()
    if db:
        try:
            db.collection("sessions").document(sid).set(sess)
        except Exception as e:
            logger.warning(f"Firestore save_session error: {e}")
    return sess


def get_blocks(sid: str) -> List[Dict[str, Any]]:
    if sid not in _BLOCKS or not _BLOCKS[sid]:
        db = get_firestore_client()
        if db:
            try:
                docs = db.collection("sessions").document(sid).collection("blocks").stream()
                if sid not in _BLOCKS:
                    _BLOCKS[sid] = {}
                for doc in docs:
                    data = doc.to_dict()
                    _BLOCKS[sid][data.get("id", doc.id)] = data
            except Exception as e:
                logger.warning(f"Firestore get_blocks error: {e}")
    return list(_BLOCKS.get(sid, {}).values())


def get_block(sid: str, block_id: str) -> Optional[Dict[str, Any]]:
    if sid not in _BLOCKS or block_id not in _BLOCKS[sid]:
        db = get_firestore_client()
        if db:
            try:
                doc = db.collection("sessions").document(sid).collection("blocks").document(block_id).get()
                if doc.exists:
                    if sid not in _BLOCKS:
                        _BLOCKS[sid] = {}
                    _BLOCKS[sid][block_id] = doc.to_dict()
            except Exception as e:
                logger.warning(f"Firestore get_block error: {e}")
    return _BLOCKS.get(sid, {}).get(block_id)


def save_block(
    sid: str,
    block_id: str,
    kind: str,
    block_json: Dict[str, Any],
    parent: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if sid not in _BLOCKS:
        _BLOCKS[sid] = {}

    existing = _BLOCKS[sid].get(block_id, {})
    order = existing.get("order", len(_BLOCKS[sid]))
    version = existing.get("version", 0) + 1

    record = {
        "id": block_id,
        "kind": kind,
        "json": block_json,
        "order": order,
        "version": version,
        "updated_at": time.time(),
        "parent": parent,
    }
    _BLOCKS[sid][block_id] = record

    db = get_firestore_client()
    if db:
        try:
            db.collection("sessions").document(sid).collection("blocks").document(block_id).set(record)
        except Exception as e:
            logger.warning(f"Firestore save_block error: {e}")

    return record


def delete_block(sid: str, block_id: str) -> bool:
    if sid in _BLOCKS and block_id in _BLOCKS[sid]:
        del _BLOCKS[sid][block_id]
    db = get_firestore_client()
    if db:
        try:
            db.collection("sessions").document(sid).collection("blocks").document(block_id).delete()
        except Exception as e:
            logger.warning(f"Firestore delete_block error: {e}")
    return True


def clear_session_blocks(sid: str) -> int:
    """Wipe all blocks for a session from both in-memory cache and Firestore."""
    count = 0
    if sid in _BLOCKS:
        count = len(_BLOCKS[sid])
        _BLOCKS[sid].clear()

    db = get_firestore_client()
    if db:
        try:
            coll = db.collection("sessions").document(sid).collection("blocks")
            docs = list(coll.stream())
            for d in docs:
                d.reference.delete()
            count = max(count, len(docs))
            logger.info(f"Cleared {len(docs)} Firestore blocks for session {sid}")
        except Exception as e:
            logger.warning(f"Firestore clear_session_blocks error: {e}")
    return count


def log_turn(
    sid: str,
    transcript: str,
    tool: str,
    block_id: Optional[str],
    kind: Optional[str],
    instruction: Optional[str],
    json_after: Optional[Dict[str, Any]],
    latency_ms: float,
):
    """Log an agent turn into the audit trail."""
    turn = {
        "ts": time.time(),
        "transcript": transcript,
        "tool": tool,
        "block_id": block_id,
        "kind": kind,
        "instruction": instruction,
        "json_after": json_after,
        "latency_ms": latency_ms,
    }
    if sid not in _TURNS:
        _TURNS[sid] = []
    _TURNS[sid].append(turn)

    db = get_firestore_client()
    if db:
        try:
            db.collection("sessions").document(sid).collection("turns").add(turn)
        except Exception as e:
            logger.warning(f"Firestore log_turn error: {e}")


def get_transcript_history(sid: str) -> List[str]:
    """Retrieve chronologically ordered speech transcripts for the session."""
    turns = _TURNS.get(sid, [])
    history = []
    for t in turns:
        txt = t.get("transcript")
        if txt and txt.strip() and (not history or history[-1] != txt.strip()):
            history.append(txt.strip())
    return history


# Section 6b: Drill-in Cache
def get_cached_child(block_id: str, ref: str) -> Optional[Dict[str, Any]]:
    key = f"{block_id}::{ref}"
    return _CACHE.get(key)


def set_cached_child(block_id: str, ref: str, child_block: Dict[str, Any]):
    key = f"{block_id}::{ref}"
    _CACHE[key] = child_block


def invalidate_cached_children(block_id: str):
    prefix = f"{block_id}::"
    keys_to_del = [k for k in _CACHE if k.startswith(prefix)]
    for k in keys_to_del:
        del _CACHE[k]
