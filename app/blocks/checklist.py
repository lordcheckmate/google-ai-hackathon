"""
Pure Python HTML renderer for `checklist` blocks.
Strict rule: No model ever emits markup. Deterministic checklist items with toggle data-ref.
"""

import html
from typing import Any
from app.blocks.schema import ChecklistBlock


def render_checklist(data: Any) -> str:
    """Render a ChecklistBlock into an interactive HTML list."""
    if isinstance(data, dict):
        block = ChecklistBlock.model_validate(data)
    else:
        block = data

    items_html = []
    for idx, item in enumerate(block.items):
        is_done = item.done
        check_icon = "☑" if is_done else "☐"
        text_style = "text-decoration: line-through; color: #64748b;" if is_done else "color: #e2e8f0;"
        owner_badge = (
            f'<span style="font-size:0.75rem; color:#38bdf8; background:#0f2b38; padding:0.1rem 0.4rem; '
            f'border-radius:4px; margin-left:0.5rem; border:1px solid #0369a1;">@{html.escape(item.owner)}</span>'
            if item.owner
            else ""
        )

        items_html.append(
            f'<li style="display:flex; align-items:center; padding:0.45rem 0; border-bottom:1px solid #1e293b; cursor:pointer;" '
            f'data-ref="item:{idx}">'
            f'<span style="font-size:1.15rem; margin-right:0.6rem; color:#38bdf8;">{check_icon}</span>'
            f'<span style="{text_style} font-size:0.9rem; flex:1;">{html.escape(item.text)}</span>'
            f'{owner_badge}'
            f'</li>'
        )

    return (
        f'<div class="checklist-container">'
        f'<ul style="list-style:none; padding:0; margin:0;">'
        f'{"".join(items_html)}'
        f'</ul>'
        f'</div>'
    )
