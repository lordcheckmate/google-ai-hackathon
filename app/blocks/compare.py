"""
Pure Python HTML renderer for `compare` blocks.
Strict rule: No model ever emits markup. Deterministic Python layout with data-ref tags.
"""

import html
from typing import Any
from app.blocks.schema import CompareBlock


def render_compare(data: Any) -> str:
    """Render a CompareBlock into an HTML table."""
    if isinstance(data, dict):
        block = CompareBlock.model_validate(data)
    else:
        block = data

    options = block.options
    criteria = block.criteria
    cells = block.cells

    table_rows = []
    # Header row
    th_cells = ['<th style="padding:0.75rem; text-align:left; color:#94a3b8; border-bottom:1px solid #334155;">Criteria</th>']
    for opt_idx, opt in enumerate(options):
        opt_esc = html.escape(opt)
        th_cells.append(
            f'<th style="padding:0.75rem; text-align:center; color:#f8fafc; border-bottom:1px solid #334155;" '
            f'data-ref="opt:{opt_idx}">{opt_esc}</th>'
        )
    table_rows.append(f'<tr>{"".join(th_cells)}</tr>')

    # Data rows
    for crit_idx, crit in enumerate(criteria):
        td_cells = [
            f'<td style="padding:0.75rem; font-weight:500; color:#cbd5e1; border-bottom:1px solid #1e293b;">{html.escape(crit)}</td>'
        ]
        row_cells = cells[crit_idx] if crit_idx < len(cells) else []
        for opt_idx in range(len(options)):
            val = row_cells[opt_idx] if opt_idx < len(row_cells) else "-"
            val_esc = html.escape(str(val))
            td_cells.append(
                f'<td style="padding:0.75rem; text-align:center; color:#e2e8f0; border-bottom:1px solid #1e293b; cursor:pointer;" '
                f'data-ref="cell:{crit_idx}:{opt_idx}">{val_esc}</td>'
            )
        table_rows.append(f'<tr>{"".join(td_cells)}</tr>')

    rec_html = ""
    if block.recommendation:
        rec_esc = html.escape(block.recommendation)
        rec_html = (
            f'<div style="margin-top:0.75rem; padding:0.5rem 0.75rem; background:#0f2b38; '
            f'border:1px solid #0284c7; border-radius:6px; font-size:0.85rem; color:#38bdf8;">'
            f'💡 <strong>Recommendation:</strong> {rec_esc}</div>'
        )

    img_html = ""
    if getattr(block, "image_url", None) and block.image_url != "loading":
        img_html = (
            f'<div class="compare-visual-banner" style="margin-bottom:1rem; text-align:center;">'
            f'<img src="{html.escape(block.image_url)}" alt="{html.escape(block.title)}" '
            f'style="max-height:220px; max-width:100%; border-radius:10px; border:1px solid #06b6d4; '
            f'box-shadow:0 0 16px rgba(6,182,212,0.25); object-fit:cover;" />'
            f'</div>'
        )
    elif getattr(block, "image_url", None) == "loading":
        img_html = (
            f'<div style="margin-bottom:1rem; padding:0.6rem; text-align:center; background:#071526; '
            f'border:1px dashed #38bdf8; border-radius:8px; color:#38bdf8; font-size:0.85rem;">'
            f'🎨 Synthesizing Nano Banana visual comparison graphic in background...</div>'
        )

    return (
        f'<div class="compare-container" style="overflow-x:auto;">'
        f'{img_html}'
        f'<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">'
        f'{"".join(table_rows)}'
        f'</table>'
        f'{rec_html}'
        f'</div>'
    )
