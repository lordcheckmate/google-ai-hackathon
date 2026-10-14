"""
Pure Python SVG renderer for `flow` blocks.
Strict rule: No model ever emits markup. Deterministic Python layout only.
Features:
- Top-to-bottom fixed grid layout with decision branch offsetting
- Label text wrapping at ~18 characters
- data-ref on wrapping <g> tag for full-node clickability
- Proper CSS drop-shadow filter for highlighted nodes (no gradient url bugs)
- Root aria-label attribute; no <title> or <desc> tags
"""

import html
import textwrap
from typing import Dict, Any, List, Tuple
from app.blocks.schema import FlowBlock, FlowNode, FlowEdge


def wrap_text(text: str, width: int = 18) -> List[str]:
    """Wrap text to roughly specified width."""
    lines = []
    for line in text.split("\n"):
        wrapped = textwrap.wrap(line, width=width)
        lines.extend(wrapped if wrapped else [""])
    return lines or [""]


def render_flow(data: Any) -> str:
    """Render a FlowBlock into an SVG string."""
    if isinstance(data, dict):
        block = FlowBlock.model_validate(data)
    else:
        block = data

    nodes = block.nodes
    edges = block.edges

    if not nodes:
        return "<div class='flow-empty' style='color:#8b949e;padding:1rem;'>No steps recorded yet.</div>"

    node_width = 190
    node_height = 64
    x_center = 320
    x_left = 130
    x_right = 510
    y_start = 40
    y_gap = 105

    # Compute node positions
    positions: Dict[str, Tuple[float, float, float, float]] = {}  # id -> (x, y, w, h)
    curr_y = y_start

    # Track branches
    for i, node in enumerate(nodes):
        x = x_center
        # Offset decision branches if previous was a decision
        if i > 0 and nodes[i - 1].shape == "decision":
            # If there are branches, offset
            x = x_left if i % 2 == 1 else x_right

        positions[node.id] = (x - node_width / 2, curr_y, node_width, node_height)
        curr_y += y_gap

    svg_width = 640
    svg_height = curr_y + 20

    svg_parts = [
        f'<svg class="flow-canvas" aria-label="{html.escape(block.title)}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_width} {svg_height}" width="100%" height="auto" '
        f'style="background: transparent; display: block; overflow: visible;">',
        '<defs>',
        '  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b" />',
        '  </marker>',
        '  <marker id="arrow-highlight" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#38bdf8" />',
        '  </marker>',
        '</defs>'
    ]

    # Render Edges
    for edge in edges:
        from_id = edge.from_node
        to_id = edge.to_node
        if from_id in positions and to_id in positions:
            fx, fy, fw, fh = positions[from_id]
            tx, ty, tw, th = positions[to_id]

            start_x = fx + fw / 2
            start_y = fy + fh
            end_x = tx + tw / 2
            end_y = ty

            # Check if source or target is highlighted
            is_hl = any(n.highlight for n in nodes if n.id in (from_id, to_id))
            stroke_color = "#38bdf8" if is_hl else "#475569"
            marker_id = "arrow-highlight" if is_hl else "arrow"

            # Draw curved path
            control_y = (start_y + end_y) / 2
            path_d = f"M {start_x} {start_y} C {start_x} {control_y}, {end_x} {control_y}, {end_x} {end_y}"
            svg_parts.append(
                f'<path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2" '
                f'marker-end="url(#{marker_id})" stroke-linecap="round" />'
            )

            # Edge label if any
            if edge.label:
                mid_x = (start_x + end_x) / 2
                mid_y = control_y
                label_esc = html.escape(edge.label)
                svg_parts.append(
                    f'<rect x="{mid_x - 30}" y="{mid_y - 10}" width="60" height="18" rx="4" fill="#0f172a" stroke="#334155" stroke-width="1" />'
                )
                svg_parts.append(
                    f'<text x="{mid_x}" y="{mid_y + 3}" text-anchor="middle" fill="#94a3b8" '
                    f'font-size="11" font-family="sans-serif">{label_esc}</text>'
                )

    # Render Nodes
    for node in nodes:
        if node.id not in positions:
            continue
        nx, ny, nw, nh = positions[node.id]

        # Shape styling
        is_hl = node.highlight
        fill_color = "#1e293b" if not is_hl else "#0f233a"
        stroke_color = "#38bdf8" if is_hl else "#334155"
        stroke_width = 3 if is_hl else 1.5
        shadow_style = 'filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.7));' if is_hl else ''

        lines = wrap_text(node.label, width=18)
        line_height = 14
        total_text_h = len(lines) * line_height
        text_start_y = ny + (nh - total_text_h) / 2 + 11

        # Outermost <g> with data-ref
        svg_parts.append(
            f'<g class="flow-node" data-ref="{html.escape(node.id)}" style="cursor: pointer;">'
        )

        # Draw shape
        if node.shape in ("start", "end"):
            # Pill shape
            svg_parts.append(
                f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="{nh/2}" ry="{nh/2}" '
                f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" '
                f'style="{shadow_style}" />'
            )
        elif node.shape == "decision":
            # Diamond shape
            mid_x = nx + nw / 2
            mid_y = ny + nh / 2
            points = f"{mid_x},{ny} {nx + nw},{mid_y} {mid_x},{ny + nh} {nx},{mid_y}"
            svg_parts.append(
                f'<polygon points="{points}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" '
                f'style="{shadow_style}" />'
            )
        else:
            # Rounded step rectangle
            svg_parts.append(
                f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="8" ry="8" '
                f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" '
                f'style="{shadow_style}" />'
            )

        # Optional Nano Banana image
        text_offset_x = 0
        if node.image_url:
            img_size = 36
            img_x = nx + 8
            img_y = ny + (nh - img_size) / 2
            svg_parts.append(
                f'<image href="{html.escape(node.image_url)}" x="{img_x}" y="{img_y}" '
                f'width="{img_size}" height="{img_size}" />'
            )
            text_offset_x = 20

        # Multi-line wrapped text
        center_text_x = nx + nw / 2 + text_offset_x
        for idx, line in enumerate(lines):
            line_y = text_start_y + (idx * line_height)
            font_weight = "600" if is_hl else "500"
            text_color = "#f8fafc" if is_hl else "#e2e8f0"
            svg_parts.append(
                f'<text x="{center_text_x}" y="{line_y}" text-anchor="middle" '
                f'fill="{text_color}" font-weight="{font_weight}" font-size="12" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">'
                f'{html.escape(line)}</text>'
            )

        # Note / badge under title if present
        if node.note:
            note_esc = html.escape(node.note[:24])
            svg_parts.append(
                f'<text x="{center_text_x}" y="{ny + nh - 6}" text-anchor="middle" '
                f'fill="#94a3b8" font-size="9" font-family="sans-serif">{note_esc}</text>'
            )

        svg_parts.append('</g>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)
