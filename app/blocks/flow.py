"""
Pure Python SVG renderer for `flow` blocks.
Features:
- Deterministic layout with animated energy pulses and slide-in transitions
- Dynamic width & height calculation with NO text truncation
- Staggered card entrance animations and neon glow effects
- Animated connector particles running along flow paths
- Auto-sized edge label badges
"""

import html
import textwrap
from typing import Dict, Any, List, Tuple
from app.blocks.schema import FlowBlock, FlowNode, FlowEdge


def wrap_text(text: str, width: int = 24) -> List[str]:
    """Wrap text to roughly specified width."""
    if not text:
        return []
    lines = []
    for line in text.split("\n"):
        wrapped = textwrap.wrap(line.strip(), width=width)
        lines.extend(wrapped if wrapped else [""])
    return lines


def render_flow(data: Any) -> str:
    """Render a FlowBlock into an animated SVG string with no text clipping."""
    if isinstance(data, dict):
        block = FlowBlock.model_validate(data)
    else:
        block = data

    nodes = block.nodes
    edges = block.edges

    if not nodes:
        return "<div class='flow-empty' style='color:#8b949e;padding:1rem;'>No steps recorded yet.</div>"

    node_width = 300
    node_height = 84
    x_center = 360
    x_left = 180
    x_right = 540
    y_start = 45
    y_gap = 135

    # Compute node positions
    positions: Dict[str, Tuple[float, float, float, float]] = {}  # id -> (x, y, w, h)
    curr_y = y_start

    for i, node in enumerate(nodes):
        x = x_center
        # Offset decision branches if previous was a decision
        if i > 0 and nodes[i - 1].shape == "decision":
            x = x_left if i % 2 == 1 else x_right

        positions[node.id] = (x - node_width / 2, curr_y, node_width, node_height)
        curr_y += y_gap

    svg_width = 720
    svg_height = curr_y + 35

    svg_parts = [
        f'<svg class="flow-canvas" aria-label="{html.escape(block.title)}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_width} {svg_height}" width="100%" height="auto" '
        f'style="background: transparent; display: block; overflow: visible;">',
        '<defs>',
        '  <style>',
        '    @keyframes flowDash {',
        '      to { stroke-dashoffset: -28; }',
        '    }',
        '    @keyframes slideInCard {',
        '      0% { opacity: 0; transform: translateY(22px) scale(0.96); }',
        '      100% { opacity: 1; transform: translateY(0) scale(1); }',
        '    }',
        '    @keyframes neonGlowPulse {',
        '      0%, 100% { filter: drop-shadow(0 0 6px rgba(6, 182, 212, 0.7)) drop-shadow(0 0 16px rgba(6, 182, 212, 0.4)); }',
        '      50% { filter: drop-shadow(0 0 14px rgba(56, 189, 248, 0.95)) drop-shadow(0 0 28px rgba(56, 189, 248, 0.7)); }',
        '    }',
        '    .flow-node-group {',
        '      animation: slideInCard 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;',
        '      transform-origin: center;',
        '      transition: transform 0.25s ease;',
        '    }',
        '    .flow-node-group:hover {',
        '      transform: translateY(-3px) scale(1.02);',
        '    }',
        '    .flow-edge-path {',
        '      stroke-dasharray: 8 6;',
        '      animation: flowDash 1.4s linear infinite;',
        '    }',
        '    .flow-highlighted {',
        '      animation: neonGlowPulse 2.2s ease-in-out infinite, slideInCard 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;',
        '    }',
        '  </style>',
        '  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b" />',
        '  </marker>',
        '  <marker id="arrow-highlight" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#38bdf8" />',
        '  </marker>',
        '  <filter id="particle-glow" x="-50%" y="-50%" width="200%" height="200%">',
        '    <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#38bdf8" flood-opacity="0.9"/>',
        '  </filter>',
        '</defs>'
    ]

    # Render Edges with dynamic label width and animated energy pulses
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

            is_hl = any(n.highlight for n in nodes if n.id in (from_id, to_id))
            stroke_color = "#38bdf8" if is_hl else "#475569"
            marker_id = "arrow-highlight" if is_hl else "arrow"
            control_y = (start_y + end_y) / 2
            path_d = f"M {start_x} {start_y} C {start_x} {control_y}, {end_x} {control_y}, {end_x} {end_y}"

            # Static base track
            svg_parts.append(
                f'<path d="{path_d}" fill="none" stroke="#1e293b" stroke-width="3" stroke-linecap="round" />'
            )
            # Animated flowing beam
            svg_parts.append(
                f'<path class="flow-edge-path" d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2.5" '
                f'marker-end="url(#{marker_id})" stroke-linecap="round" />'
            )
            # Animated particle beacon
            svg_parts.append(
                f'<circle r="3.5" fill="#38bdf8" filter="url(#particle-glow)">'
                f'  <animateMotion dur="2.4s" repeatCount="indefinite" path="{path_d}"/>'
                f'</circle>'
            )

            # Edge label badge with dynamic sizing to prevent text clipping
            if edge.label:
                mid_x = (start_x + end_x) / 2
                mid_y = control_y
                label_esc = html.escape(edge.label)
                pill_w = max(76, len(edge.label) * 8 + 18)
                svg_parts.append(
                    f'<rect x="{mid_x - pill_w / 2}" y="{mid_y - 11}" width="{pill_w}" height="22" rx="6" '
                    f'fill="#0a101d" stroke="#334155" stroke-width="1.2" />'
                )
                svg_parts.append(
                    f'<text x="{mid_x}" y="{mid_y + 4}" text-anchor="middle" fill="#94a3b8" '
                    f'font-size="11" font-weight="600" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">{label_esc}</text>'
                )

    # Render Nodes with staggered animations and full multi-line text
    for i, node in enumerate(nodes):
        if node.id not in positions:
            continue
        nx, ny, nw, nh = positions[node.id]

        is_hl = node.highlight
        fill_color = "#0e172a" if not is_hl else "#0c233c"
        stroke_color = "#06b6d4" if is_hl else "#334155"
        stroke_width = 2.5 if is_hl else 1.5
        group_class = "flow-node-group flow-highlighted" if is_hl else "flow-node-group"
        anim_delay = f"{i * 0.12:.2f}s"

        svg_parts.append(
            f'<g class="{group_class}" data-ref="{html.escape(node.id)}" '
            f'style="cursor: pointer; animation-delay: {anim_delay};">'
        )

        # Draw card shape
        if node.shape in ("start", "end"):
            rx = 26
            svg_parts.append(
                f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="{rx}" ry="{rx}" '
                f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />'
            )
        elif node.shape == "decision":
            mid_x = nx + nw / 2
            mid_y = ny + nh / 2
            points = f"{mid_x},{ny} {nx + nw},{mid_y} {mid_x},{ny + nh} {nx},{mid_y}"
            svg_parts.append(
                f'<polygon points="{points}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />'
            )
        else:
            svg_parts.append(
                f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="12" ry="12" '
                f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}" />'
            )

        # Nano Banana image or icon
        has_img = bool(node.image_url)
        if has_img:
            img_size = 48
            img_x = nx + 14
            img_y = ny + (nh - img_size) / 2
            svg_parts.append(
                f'<rect x="{img_x - 2}" y="{img_y - 2}" width="{img_size + 4}" height="{img_size + 4}" rx="10" '
                f'fill="#050811" stroke="#1e293b" stroke-width="1" />'
            )
            svg_parts.append(
                f'<image href="{html.escape(node.image_url)}" x="{img_x}" y="{img_y}" '
                f'width="{img_size}" height="{img_size}" />'
            )
            text_x = nx + 74
            text_anchor = "start"
            max_title_w = 23
            max_note_w = 30
        else:
            text_x = nx + nw / 2
            text_anchor = "middle"
            max_title_w = 26
            max_note_w = 34

        # Wrap Title without clipping
        title_lines = wrap_text(node.label, width=max_title_w)
        # Wrap Note without clipping (NO TRUNCATION!)
        note_lines = wrap_text(node.note, width=max_note_w) if node.note else []

        total_lines = len(title_lines) + len(note_lines)
        line_height = 16
        start_y = ny + (nh - (total_lines * line_height)) / 2 + 13

        curr_text_y = start_y
        for t_line in title_lines:
            svg_parts.append(
                f'<text x="{text_x}" y="{curr_text_y}" text-anchor="{text_anchor}" '
                f'fill="#f8fafc" font-weight="700" font-size="13" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">'
                f'{html.escape(t_line)}</text>'
            )
            curr_text_y += line_height

        for n_line in note_lines:
            svg_parts.append(
                f'<text x="{text_x}" y="{curr_text_y}" text-anchor="{text_anchor}" '
                f'fill="#94a3b8" font-size="10.5" font-weight="500" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">'
                f'{html.escape(n_line)}</text>'
            )
            curr_text_y += line_height

        svg_parts.append('</g>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)
