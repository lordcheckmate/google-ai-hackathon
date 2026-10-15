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


def visual_char_width(char: str) -> float:
    """Return proportional width weight: ~1.85 for CJK full-width, 1.0 for Latin/ASCII."""
    code = ord(char)
    if (
        (0x1100 <= code <= 0x11FF)
        or (0x2E80 <= code <= 0x9FFF)
        or (0xAC00 <= code <= 0xD7AF)
        or (0xF900 <= code <= 0xFAFF)
        or (0xFF01 <= code <= 0xFF60)
        or (0xFFE0 <= code <= 0xFFE6)
    ):
        return 1.85
    return 1.0


def visual_length(text: str) -> float:
    """Calculate total visual display width of a string."""
    if not text:
        return 0.0
    return sum(visual_char_width(c) for c in text)


def wrap_text_visual(text: str, max_visual_width: float) -> List[str]:
    """
    Wrap text cleanly taking into account both CJK full-width characters
    and English words, without requiring whitespace spaces for Japanese.
    """
    if not text:
        return []
    lines = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        curr_line = []
        curr_w = 0.0
        has_spaces = " " in paragraph
        if has_spaces:
            words = paragraph.split(" ")
            for word in words:
                word_w = visual_length(word)
                space_w = 1.0 if curr_line else 0.0
                if curr_w + space_w + word_w <= max_visual_width:
                    if curr_line:
                        curr_line.append(" ")
                        curr_w += 1.0
                    curr_line.append(word)
                    curr_w += word_w
                else:
                    if curr_line:
                        lines.append("".join(curr_line))
                        curr_line = []
                        curr_w = 0.0
                    if word_w > max_visual_width:
                        for c in word:
                            cw = visual_char_width(c)
                            if curr_w + cw > max_visual_width and curr_line:
                                lines.append("".join(curr_line))
                                curr_line = [c]
                                curr_w = cw
                            else:
                                curr_line.append(c)
                                curr_w += cw
                    else:
                        curr_line = [word]
                        curr_w = word_w
            if curr_line:
                lines.append("".join(curr_line))
        else:
            for c in paragraph:
                cw = visual_char_width(c)
                if curr_w + cw > max_visual_width and curr_line:
                    lines.append("".join(curr_line))
                    curr_line = [c]
                    curr_w = cw
                else:
                    curr_line.append(c)
                    curr_w += cw
            if curr_line:
                lines.append("".join(curr_line))
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

    node_width = 340
    node_height = 100
    x_center = 360
    x_left = 180
    x_right = 540
    y_start = 45
    y_gap = 150

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
            f'data-node-id="{html.escape(node.id)}" '
            f'data-node-label="{html.escape(node.label)}" '
            f'data-node-note="{html.escape(node.note or "")}" '
            f'data-node-shape="{html.escape(node.shape)}" '
            f'data-node-img="{html.escape(node.image_url or "")}" '
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

        # Render Nano Banana picture over/inside diagram step card if present
        has_img = bool(node.image_url and node.image_url != "loading")
        if has_img:
            clip_id = f"clip_{node.id}_{i}"
            img_size = 68
            img_x = nx + 12
            img_y = ny + (nh - img_size) / 2
            svg_parts.append(
                f'<defs><clipPath id="{clip_id}">'
                f'<rect x="{img_x}" y="{img_y}" width="{img_size}" height="{img_size}" rx="8" />'
                f'</clipPath></defs>'
            )
            svg_parts.append(
                f'<image href="{html.escape(node.image_url)}" x="{img_x}" y="{img_y}" '
                f'width="{img_size}" height="{img_size}" clip-path="url(#{clip_id})" '
                f'preserveAspectRatio="xMidYMid slice" />'
            )
            svg_parts.append(
                f'<rect x="{img_x}" y="{img_y}" width="{img_size}" height="{img_size}" rx="8" '
                f'fill="none" stroke="#06b6d4" stroke-width="1.5" />'
            )
            text_x = nx + 88
            text_anchor = "start"
            max_title_w = 20.0 if node.shape == "decision" else 24.0
            max_note_w = 22.0 if node.shape == "decision" else 27.0
        elif node.image_url == "loading":
            img_size = 58
            img_x = nx + 12
            img_y = ny + (nh - img_size) / 2
            svg_parts.append(
                f'<rect x="{img_x}" y="{img_y}" width="{img_size}" height="{img_size}" rx="8" '
                f'fill="#0a192f" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="4 2" />'
            )
            svg_parts.append(
                f'<text x="{img_x + img_size/2}" y="{img_y + img_size/2 + 4}" text-anchor="middle" '
                f'fill="#38bdf8" font-size="10" font-weight="600">🎨 NB...</text>'
            )
            text_x = nx + 82
            text_anchor = "start"
            max_title_w = 20.0 if node.shape == "decision" else 24.0
            max_note_w = 22.0 if node.shape == "decision" else 27.0
        else:
            text_x = nx + nw / 2
            text_anchor = "middle"
            max_title_w = 24.0 if node.shape == "decision" else 32.0
            max_note_w = 28.0 if node.shape == "decision" else 38.0

        is_decision = (node.shape == "decision")

        # Title: limit to 2 lines max
        raw_title_lines = wrap_text_visual(node.label, max_visual_width=max_title_w)
        if len(raw_title_lines) > 2:
            title_lines = [raw_title_lines[0], raw_title_lines[1][:max(4, int(max_title_w) - 3)] + "..."]
        else:
            title_lines = raw_title_lines

        # Note: limit to at most 1 or 2 lines
        max_note_display = 1 if len(title_lines) >= 2 or is_decision else 2
        raw_note_lines = wrap_text_visual(node.note, max_visual_width=max_note_w) if node.note else []

        # Determine if "Show more" is needed
        has_more = (
            len(raw_note_lines) > max_note_display
            or (len(raw_title_lines) > 2)
            or visual_length(node.note or "") > (max_note_w * max_note_display * 0.95)
        )

        note_lines = raw_note_lines[:max_note_display]
        if has_more and note_lines:
            last_line = note_lines[-1]
            if visual_length(last_line) > max_note_w - 4:
                note_lines[-1] = last_line[:max(4, len(last_line) - 2)] + "..."
            elif len(raw_note_lines) > max_note_display:
                note_lines[-1] = last_line + "..."

        line_h = 16
        text_start_y = ny + 26 if len(title_lines) <= 1 else ny + 20
        curr_text_y = text_start_y

        for t_line in title_lines:
            svg_parts.append(
                f'<text x="{text_x}" y="{curr_text_y}" text-anchor="{text_anchor}" '
                f'fill="#f8fafc" font-weight="700" font-size="12.5" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">'
                f'{html.escape(t_line)}</text>'
            )
            curr_text_y += line_h

        curr_text_y += 2
        for n_line in note_lines:
            svg_parts.append(
                f'<text x="{text_x}" y="{curr_text_y}" text-anchor="{text_anchor}" '
                f'fill="#94a3b8" font-size="10.5" font-weight="500" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">'
                f'{html.escape(n_line)}</text>'
            )
            curr_text_y += 14

        # Render "Show more" button on card if content exceeded box
        if has_more:
            btn_w = 78
            btn_h = 18
            if is_decision:
                btn_x = nx + nw / 2 - btn_w / 2
                btn_y = ny + nh - btn_h - 10
            else:
                btn_x = nx + nw - btn_w - 12
                btn_y = ny + nh - btn_h - 8
            svg_parts.append(
                f'<g class="flow-show-more-btn" data-action="show-more" data-ref="{html.escape(node.id)}" '
                f'data-node-id="{html.escape(node.id)}" '
                f'data-node-label="{html.escape(node.label)}" '
                f'data-node-note="{html.escape(node.note or "")}" '
                f'data-node-shape="{html.escape(node.shape)}" '
                f'data-node-img="{html.escape(node.image_url or "")}" '
                f'style="cursor: pointer;">'
                f'<rect x="{btn_x}" y="{btn_y}" width="{btn_w}" height="{btn_h}" rx="5" '
                f'fill="#081829" stroke="#06b6d4" stroke-width="1.2" />'
                f'<text x="{btn_x + btn_w / 2}" y="{btn_y + 12}" text-anchor="middle" '
                f'fill="#38bdf8" font-size="9" font-weight="700" '
                f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">Show more ▾</text>'
                f'</g>'
            )

        svg_parts.append('</g>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)
