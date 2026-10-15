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

    visual_html = ""
    if block.image_url in ("loading", "generating", "__loading__"):
        visual_html = (
            f'<div class="answer-visual-wrapper loading-shimmer" style="display:flex; flex-direction:column; justify-content:center; align-items:center; '
            f'margin:1rem 0; padding:2rem 1.25rem; background:#050811; border:1px solid rgba(6,182,212,0.4); '
            f'border-radius:12px; box-shadow:0 0 25px rgba(6,182,212,0.2); text-align:center;">'
            f'<div class="spinner-circle" style="width:36px; height:36px; border:3px solid rgba(6,182,212,0.2); border-top-color:#06b6d4; border-radius:50%; animation:spin-slow 1s linear infinite; margin-bottom:0.85rem;"></div>'
            f'<span style="font-family:var(--font-mono, monospace); font-size:0.85rem; color:#22d3ee; letter-spacing:0.06em; font-weight:700;">SYNTHESIZING NANO BANANA 2 LITE ILLUSTRATION...</span>'
            f'<span style="font-size:0.75rem; color:#64748b; margin-top:0.35rem;">Reasoning &amp; speech emitted instantly • Streaming visual in background</span>'
            f'</div>'
        )
    elif block.image_url:
        visual_html = (
            f'<div class="answer-visual-wrapper" style="display:flex; justify-content:center; align-items:center; '
            f'margin:1rem 0; padding:1.25rem; background:#000; border:1px solid rgba(6,182,212,0.3); '
            f'border-radius:12px; box-shadow:0 0 20px rgba(6,182,212,0.15);">'
            f'<img src="{html.escape(block.image_url)}" alt="Visual Explanation" style="max-height:280px; max-width:100%; object-fit:contain; border-radius:8px;" />'
            f'</div>'
        )
    else:
        # Pure explanation in words: do not render any fake dummy SVG diagram
        visual_html = ""

    caption_text = block.visual_caption or block.answer

    return (
        f'<div class="answer-card" style="width:100%; max-width:760px; padding:0.5rem 0;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">'
        f'<h4 style="font-size:1.1rem; color:#f8fafc; font-weight:700; font-family:var(--font-mono, monospace);">{html.escape(block.question)}</h4>'
        f'{conf_badge}'
        f'</div>'
        f'{visual_html}'
        f'<div class="answer-caption-box" style="margin-top:0.75rem; padding:0.9rem 1.1rem; background:#080d17; border-left:3px solid #06b6d4; border-radius:0 8px 8px 0; border-top:1px solid #1e293b; border-right:1px solid #1e293b; border-bottom:1px solid #1e293b;">'
        f'<div style="font-size:0.75rem; font-family:var(--font-mono, monospace); font-weight:800; color:#38bdf8; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:0.35rem;">💡 CAPTION & EXPLANATION</div>'
        f'<p style="font-size:0.95rem; line-height:1.6; color:#f1f5f9;">{html.escape(caption_text)}</p>'
        f'{detail_html}'
        f'{sources_html}'
        f'</div>'
        f'</div>'
    )

