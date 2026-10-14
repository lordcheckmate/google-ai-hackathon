"""
Pure Python HTML renderer for `answer` blocks.
Strict rule: No model ever emits markup. Deterministic card rendering with citations and confidence tag.
"""

import html
from typing import Any
from app.blocks.schema import AnswerBlock


def render_answer(data: Any) -> str:
    """Render an AnswerBlock into an HTML card."""
    if isinstance(data, dict):
        block = AnswerBlock.model_validate(data)
    else:
        block = data

    conf_colors = {
        "high": ("#064e3b", "#34d399"),
        "medium": ("#78350f", "#fbbf24"),
        "low": ("#7f1d1d", "#f87171"),
    }
    bg, fg = conf_colors.get(block.confidence, ("#1e293b", "#94a3b8"))

    conf_badge = (
        f'<span class="confidence-badge confidence-{block.confidence}" style="font-size:0.75rem; font-weight:600; text-transform:uppercase; '
        f'padding:0.15rem 0.5rem; border-radius:9999px; background:{bg}; color:{fg};">'
        f'{html.escape(block.confidence)} confidence</span>'
    )

    detail_html = ""
    if block.detail:
        detail_html = f'<p style="margin-top:0.5rem; font-size:0.875rem; color:#94a3b8;">{html.escape(block.detail)}</p>'

    sources_html = ""
    if block.sources:
        source_pills = []
        for idx, src in enumerate(block.sources):
            title_esc = html.escape(src.title)
            url_esc = html.escape(src.url)
            source_pills.append(
                f'<a href="{url_esc}" target="_blank" rel="noopener noreferrer" '
                f'data-ref="src:{idx}" '
                f'style="display:inline-block; font-size:0.75rem; color:#38bdf8; text-decoration:none; '
                f'background:#1e293b; padding:0.2rem 0.6rem; border-radius:4px; border:1px solid #334155;">'
                f'🔗 {title_esc}</a>'
            )
        sources_html = (
            f'<div style="margin-top:0.75rem; display:flex; flex-wrap:wrap; gap:0.5rem; align-items:center;">'
            f'<span style="font-size:0.75rem; color:#64748b;">Sources:</span>'
            f'{"".join(source_pills)}'
            f'</div>'
        )

    return (
        f'<div class="answer-card" style="padding:0.5rem 0;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">'
        f'<h4 style="font-size:1rem; color:#f8fafc; font-weight:600;">{html.escape(block.question)}</h4>'
        f'{conf_badge}'
        f'</div>'
        f'<p style="font-size:0.95rem; line-height:1.5; color:#e2e8f0;">{html.escape(block.answer)}</p>'
        f'{detail_html}'
        f'{sources_html}'
        f'</div>'
    )
