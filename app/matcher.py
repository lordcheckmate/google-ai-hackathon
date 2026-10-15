"""
app/matcher.py - Robust, fuzzy, index-aware matching and diagram manipulation.
Handles voice fillers, plurals/stems, ordinal step references, and step removal.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Common English stopwords to ignore in fuzzy token overlap
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "for", "in", "on", "of", "with", "at",
    "by", "from", "that", "this", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "our",
    "my", "your", "their", "its", "we", "us", "you", "they", "it"
}

# Common speech filler words and phrases to strip from the beginning or end of queries
LEADING_FILLERS_REGEX = re.compile(
    r"^(?:\s*(?:asian|agent|aegis|hey|can\s+you|could\s+you|would\s+you|please|kindly|"
    r"i\s+want\s+to|i\s+want\s+you\s+to|let'?s|highlight|focus\s+on|emphasize|"
    r"remove|delete|take\s+out|drop|get\s+rid\s+of|eliminate|erase|clear|"
    r"that|the|a|an|this|these|those|step|node|box|item|card|about|for|"
    r"あの|えっと|その|この|ステップ|ノード|ハイライト|強調|削除|消して)\s*)+",
    re.IGNORECASE
)

TRAILING_FILLERS_REGEX = re.compile(
    r"(?:\s*(?:step|node|box|item|please|thanks|thank\s+you|"
    r"のステップ|ステップ|ノード|をハイライト|を強調|を削除|を消して|を外して|を|と|して|してください))+$",
    re.IGNORECASE
)

# Ordinal words to 0-based indices (English & Japanese)
ORDINALS_MAP = {
    # English
    "first": 0, "1st": 0, "one": 0, "1": 0,
    "second": 1, "2nd": 1, "two": 1, "2": 1,
    "third": 2, "3rd": 2, "three": 2, "3": 2,
    "fourth": 3, "4th": 3, "four": 3, "3": 3,
    "fifth": 4, "5th": 4, "five": 4, "5": 4,
    "sixth": 5, "6th": 5, "six": 5, "6": 5,
    "seventh": 6, "7th": 6, "seven": 6, "7": 6,
    "eighth": 7, "8th": 7, "eight": 7, "8": 7,
    "ninth": 8, "9th": 8, "nine": 8, "9": 8,
    "tenth": 9, "10th": 9, "ten": 9, "10": 9,
    "last": -1, "final": -1,
    # Japanese
    "1番目": 0, "一番目": 0, "最初": 0, "1つ目": 0, "一つ目": 0, "最初ステップ": 0,
    "2番目": 1, "二番目": 1, "2つ目": 1, "二つ目": 1,
    "3番目": 2, "三番目": 2, "3つ目": 2, "三つ目": 2,
    "4番目": 3, "四番目": 3, "4つ目": 3, "四つ目": 3,
    "5番目": 4, "五番目": 4, "5つ目": 4, "五つ目": 4,
    "最後": -1, "最終": -1, "最後のステップ": -1,
}



def clean_query_text(text: str) -> str:
    """Strip speech fillers, leading articles, and trailing noise."""
    t = text.strip()
    # Strip leading fillers repeatedly
    prev = None
    while prev != t:
        prev = t
        t = LEADING_FILLERS_REGEX.sub("", t).strip()
    t = TRAILING_FILLERS_REGEX.sub("", t).strip()
    return t


def stem_word(w: str) -> str:
    """Lightweight suffix stripping for plurals and verb inflections."""
    w = w.lower()
    if len(w) <= 3:
        return w
    # Common suffix transformations
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ings") and len(w) > 5:
        return w[:-4]
    if w.endswith("ing") and len(w) > 4:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def extract_stems(text: str) -> set[str]:
    """Tokenize text into significant lowercase stems, ignoring stopwords."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    stems = set()
    for w in words:
        if w not in STOPWORDS and len(w) > 1:
            stems.add(stem_word(w))
    return stems


def parse_ordinal_index(text: str, total_count: int) -> Optional[int]:
    """Check if query is referencing a step by ordinal (e.g., 'second step', 'step 3')."""
    clean = text.lower().strip()
    
    # Check "step X" or "node X" pattern
    m = re.search(r"\b(?:step|node|item|box)\s*#?\s*([0-9]+|[a-z]+)\b", clean)
    if m:
        token = m.group(1).lower()
        if token in ORDINALS_MAP:
            idx = ORDINALS_MAP[token]
            if 0 <= idx < total_count:
                return idx
            elif idx == -1 and total_count > 0:
                return total_count - 1
        elif token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < total_count:
                return idx

    # Check Japanese step pattern e.g. "ステップ1", "ステップ2", "第1ステップ"
    m_ja = re.search(r"(?:ステップ|第)\s*([0-9]+)\s*(?:ステップ)?", clean)
    if m_ja and m_ja.group(1).isdigit():
        idx = int(m_ja.group(1)) - 1
        if 0 <= idx < total_count:
            return idx

    # Check standalone ordinals like "the second one", "first", "final step", "2番目", "最初"
    for ord_word, idx in ORDINALS_MAP.items():
        if ord_word in clean or re.search(rf"\b{re.escape(ord_word)}\b", clean):
            if idx == -1 and total_count > 0:
                return total_count - 1
            elif 0 <= idx < total_count:
                return idx

    return None


def split_label_phrases(raw_label: str) -> List[str]:
    """
    Split complex voice phrases like 'that record meeting and save notes'
    or 'ノート保存と録画共有' into individual target queries.
    """
    cleaned = clean_query_text(raw_label)
    if not cleaned:
        cleaned = raw_label.strip()

    # Split on English and Japanese conjunctions (and, &, ,, 、 と, および)
    parts = re.split(r"\s+(?:and|&)\s+|\s*,\s*|\s*、\s*|(?<=[^\s])と(?=[^\s])|\s*および\s*", cleaned, flags=re.IGNORECASE)
    results = []
    for p in parts:
        cp = clean_query_text(p)
        if cp:
            results.append(cp)
        elif p.strip():
            results.append(p.strip())
    return results if results else [cleaned]



def match_items(
    queries: List[str] | str,
    items: List[Dict[str, Any]],
    text_key: str = "label",
    id_key: str = "id"
) -> List[Dict[str, Any]]:
    """
    Fuzzy, index-aware match of one or more queries against a list of items (flow nodes or checklist items).
    Returns list of matched item dicts.
    """
    if isinstance(queries, str):
        queries = [queries]

    # Expand any phrases containing ' and '
    expanded_queries: List[str] = []
    for q in queries:
        expanded_queries.extend(split_label_phrases(q))

    matched_indices: set[int] = set()

    for query in expanded_queries:
        if not query:
            continue
        clean_q = clean_query_text(query)
        q_stems = extract_stems(clean_q or query)
        q_lower = (clean_q or query).lower()

        # 1. Check ordinal index match (e.g. "step 2", "second step")
        ord_idx = parse_ordinal_index(query, len(items))
        if ord_idx is not None:
            matched_indices.add(ord_idx)
            continue

        best_score = 0.0
        candidate_scores: Dict[int, float] = {}

        for idx, item in enumerate(items):
            item_text = str(item.get(text_key, "")).strip().lower()
            item_id = str(item.get(id_key, "")).strip().lower()

            # Exact ID or exact label match
            if clean_q == item_id or clean_q == item_text or q_lower == item_id or q_lower == item_text:
                score = 100.0
                candidate_scores[idx] = score
                continue

            # Substring match (either direction)
            if clean_q and (clean_q in item_text or item_text in clean_q):
                score = 50.0 + (len(clean_q) / max(1, len(item_text))) * 20.0
                candidate_scores[idx] = max(candidate_scores.get(idx, 0.0), score)

            # Stem / token overlap match
            item_stems = extract_stems(item_text)
            if q_stems and item_stems:
                intersection = q_stems.intersection(item_stems)
                ratio_q = len(intersection) / len(q_stems)
                ratio_item = len(intersection) / len(item_stems)

                # Single-word query
                if len(q_stems) == 1 and ratio_q == 1.0:
                    score = 25.0 + ratio_item * 15.0
                    candidate_scores[idx] = max(candidate_scores.get(idx, 0.0), score)
                # Multi-word query
                elif len(q_stems) >= 2:
                    if ratio_q == 1.0 or (ratio_q >= 0.65 and len(intersection) >= 2):
                        prefix_bonus = 5.0 if item_text.startswith(clean_q[:min(5, len(clean_q))]) else 0.0
                        score = ratio_q * 30.0 + ratio_item * 20.0 + prefix_bonus
                        candidate_scores[idx] = max(candidate_scores.get(idx, 0.0), score)

        if candidate_scores:
            max_score = max(candidate_scores.values())
            # Select the top candidates (within 5% of max score)
            for idx, sc in candidate_scores.items():
                if sc >= max_score * 0.95 and sc >= 20.0:
                    matched_indices.add(idx)

    return [items[i] for i in sorted(matched_indices)]



def remove_step_from_flow(flow_json: Dict[str, Any], step_query: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Remove a step/node from flow JSON by label, ID, or ordinal.
    Re-links edges around the removed node so the sequence remains continuous.
    Returns (updated_flow_json, removed_node_or_None).
    """
    nodes = flow_json.get("nodes", [])
    if not nodes:
        return flow_json, None

    # Find the target node
    matched = match_items(step_query, nodes, text_key="label", id_key="id")
    if not matched:
        return flow_json, None

    target_node = matched[0]
    target_id = target_node.get("id")

    # Separate edges into incoming, outgoing, and unrelated
    incoming_from_ids: List[str] = []
    outgoing_to_ids: List[str] = []
    retained_edges: List[Dict[str, Any]] = []

    for edge in flow_json.get("edges", []):
        f = edge.get("from")
        t = edge.get("to")
        if t == target_id:
            if f and f != target_id:
                incoming_from_ids.append(f)
        elif f == target_id:
            if t and t != target_id:
                outgoing_to_ids.append(t)
        else:
            retained_edges.append(edge)

    # Reconnect predecessors to successors
    existing_pairs = {(e.get("from"), e.get("to")) for e in retained_edges}
    for in_id in incoming_from_ids:
        for out_id in outgoing_to_ids:
            if in_id != out_id and (in_id, out_id) not in existing_pairs:
                retained_edges.append({
                    "from": in_id,
                    "to": out_id,
                    "label": "Next"
                })
                existing_pairs.add((in_id, out_id))

    # Remove node
    new_nodes = [n for n in nodes if n.get("id") != target_id]

    # Adjust start/end shapes if removed node was start or end
    if target_node.get("shape") == "start" and new_nodes:
        if new_nodes[0].get("shape") != "end":
            new_nodes[0]["shape"] = "start"
    elif target_node.get("shape") == "end" and new_nodes:
        if new_nodes[-1].get("shape") != "start":
            new_nodes[-1]["shape"] = "end"

    updated_flow = dict(flow_json)
    updated_flow["nodes"] = new_nodes
    updated_flow["edges"] = retained_edges

    return updated_flow, target_node


def remove_item_from_checklist(checklist_json: Dict[str, Any], item_query: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Remove an item from checklist JSON by text or ordinal.
    Returns (updated_checklist_json, removed_item_or_None).
    """
    items = checklist_json.get("items", [])
    if not items:
        return checklist_json, None

    matched = match_items(item_query, items, text_key="text", id_key="id")
    if not matched:
        return checklist_json, None

    target_item = matched[0]
    new_items = [it for it in items if it is not target_item]

    updated_checklist = dict(checklist_json)
    updated_checklist["items"] = new_items

    return updated_checklist, target_item
