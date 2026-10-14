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

    return (
        f'<div class="compare-container" style="overflow-x:auto;">'
        f'<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">'
        f'{"".join(table_rows)}'
        f'</table>'
        f'{rec_html}'
        f'</div>'
    )
