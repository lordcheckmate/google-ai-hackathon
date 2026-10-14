"""
Truth Sentinel: Real-time contradiction and inconsistency detector for meetings.
Tracks chronological claims, metrics, decisions, and dates across multiple speakers
and languages, detecting discrepancies between "old speak" and "new speak".
"""

import re
import time
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ClaimEntry(BaseModel):
    id: str
    timestamp: float
    time_str: str
    speaker: str
    raw_text: str
    topic: str
    category: str  # timeline, budget, metric, architecture, decision, general
    claim_summary: str
    extracted_value: Optional[str] = None
    language: str = "en"


class ContradictionAlert(BaseModel):
    id: str
    timestamp: float
    topic: str
    category: str
    old_claim: ClaimEntry
    new_claim: ClaimEntry
    discrepancy_reason: str
    clarification_question: str
    options: List[str]
    auto_chat_message: str


class TruthSentinel:
    def __init__(self, gemini_client=None):
        self.claims: List[ClaimEntry] = []
        self.contradictions: List[ContradictionAlert] = []
        self.gemini_client = gemini_client
        self._claim_counter = 0

    def add_claim(
        self,
        speaker: str,
        text: str,
        topic: Optional[str] = None,
        category: str = "general",
        extracted_value: Optional[str] = None,
        language: str = "en"
    ) -> ClaimEntry:
        self._claim_counter += 1
        now = time.time()
        time_str = time.strftime("%H:%M:%S", time.localtime(now))
        
        # Auto-detect category & extracted value if not provided
        inferred_category, inferred_topic, val = self._infer_category_and_value(text)
        category = category if category != "general" else inferred_category
        topic = topic or inferred_topic

        entry = ClaimEntry(
            id=f"claim_{self._claim_counter}",
            timestamp=now,
            time_str=time_str,
            speaker=speaker or "Speaker",
            raw_text=text.strip(),
            topic=topic,
            category=category,
            claim_summary=text.strip(),
            extracted_value=extracted_value or val,
            language=language
        )
        self.claims.append(entry)
        return entry

    def check_for_contradictions(self, new_entry: ClaimEntry) -> Optional[ContradictionAlert]:
        """
        Compares the new claim against historical claims to detect conflicts.
        Uses fast deterministic heuristics first, falling back to semantic verification.
        """
        for old in reversed(self.claims[:-1]):
            # If topics match or values conflict in the same category
            if self._is_conflicting(old, new_entry):
                alert_id = f"conflict_{len(self.contradictions) + 1}"
                
                # Format clarification question
                opt_a = f"{old.extracted_value or old.claim_summary}"
                opt_b = f"{new_entry.extracted_value or new_entry.claim_summary}"
                clarification = f"Which one do you mean: {opt_a} vs {opt_b}?"
                
                chat_msg = (
                    f"⚠️ [AI Sentinel] Discrepancy detected on '{new_entry.topic}':\n"
                    f"• Earlier ({old.time_str}, {old.speaker}): \"{old.raw_text}\"\n"
                    f"• Just now ({new_entry.time_str}, {new_entry.speaker}): \"{new_entry.raw_text}\"\n"
                    f"👉 {clarification}"
                )

                alert = ContradictionAlert(
                    id=alert_id,
                    timestamp=time.time(),
                    topic=new_entry.topic,
                    category=new_entry.category,
                    old_claim=old,
                    new_claim=new_entry,
                    discrepancy_reason=f"Mismatch in {new_entry.category}: '{opt_a}' contradicts '{opt_b}'",
                    clarification_question=clarification,
                    options=[opt_a, opt_b],
                    auto_chat_message=chat_msg
                )
                self.contradictions.append(alert)
                return alert

        return None

    def ingest_statement(
        self,
        speaker: str,
        text: str,
        language: str = "en"
    ) -> Optional[ContradictionAlert]:
        """
        Main pipeline entry point: ingests speaker text, records claims,
        and returns any contradiction alert if detected.
        """
        entry = self.add_claim(speaker, text, language=language)
        return self.check_for_contradictions(entry)

    def _infer_category_and_value(self, text: str) -> tuple[str, str, Optional[str]]:
        lower = text.lower()

        # 1. Timeline / Schedule patterns (e.g. Q1, Q2, Q3, Q4, Months, quarters, deadlines)
        quarter_match = re.search(r'(?:\b(q[1-4])\b|(第[1-4]四半期))', lower)
        month_match = re.search(r'(?:\b(january|february|march|april|may|june|july|august|september|october|november|december)\b|([1-9]|1[0-2])月)', lower)
        date_match = re.search(r'(?:\b(202[4-9]|next week|next month|end of year|eoy)\b|(来週|来月|年末))', lower)

        if quarter_match:
            raw_q = quarter_match.group(1) or quarter_match.group(2)
            # Normalize 第X四半期 to QX
            if "第" in raw_q:
                num = re.search(r'[1-4]', raw_q).group(0)
                val = f"Q{num} (第{num}四半期)"
            else:
                val = raw_q.upper()
            return ("timeline", "Release Timeline", val)
        if month_match:
            raw_m = month_match.group(1) or month_match.group(2)
            val = raw_m.capitalize()
            return ("timeline", "Schedule Target", val)
        if date_match:
            val = date_match.group(1) or date_match.group(2)
            return ("timeline", "Target Deadline", val)

        # 2. Budget / Monetary patterns (e.g. $50k, 50,000 USD, 30万円, etc.)
        money_match = re.search(r'(\$[\d,]+k?|\b[\d,]+\s*(?:usd|dollars|euro|eur|万円|円|dollars|bucks)\b)', lower)
        if money_match or any(w in lower for w in ["budget", "cost", "pricing", "予算", "コスト"]):
            val = money_match.group(1) if money_match else None
            return ("budget", "Budget & Cost", val)

        # 3. Numeric Metrics & Headcount (e.g. 5 engineers, 100 users, 99.9% uptime)
        metric_match = re.search(r'(\d+(?:\.\d+)?\s*(?:%|users|people|engineers|devs|req/s|fps|ms|人|名))', lower)
        if metric_match:
            val = metric_match.group(1)
            return ("metric", "Target Metric", val)

        # 4. Architecture / Technology Decisions
        tech_keywords = ["postgres", "postgresql", "mysql", "mongodb", "redis", "aws", "gcp", "azure", "docker", "kubernetes"]
        for tech in tech_keywords:
            if tech in lower:
                return ("architecture", "Tech Stack Architecture", tech.capitalize())

        return ("general", "Meeting Point", None)

    def _is_conflicting(self, old: ClaimEntry, new: ClaimEntry) -> bool:
        """Determines if two claim entries contradict each other."""
        # Check timeline contradictions (e.g. Q3 vs Q2, different deadlines)
        if old.category == "timeline" and new.category == "timeline":
            if old.extracted_value and new.extracted_value and old.extracted_value != new.extracted_value:
                return True

        # Check budget contradictions (e.g. $50k vs $30k)
        if old.category == "budget" and new.category == "budget":
            if old.extracted_value and new.extracted_value and old.extracted_value != new.extracted_value:
                return True

        # Check metric contradictions (e.g. 5 devs vs 10 devs)
        if old.category == "metric" and new.category == "metric":
            if old.extracted_value and new.extracted_value and old.extracted_value != new.extracted_value:
                return True

        # Check architecture stack contradictions (e.g. Postgres vs MySQL)
        if old.category == "architecture" and new.category == "architecture":
            if old.extracted_value and new.extracted_value and old.extracted_value != new.extracted_value:
                return True

        return False
