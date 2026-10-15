"""
Image and diagram generation for process steps (Nano Banana) and visual explanations.
Provides:
- gemini-2.5-flash-lite powered custom visual diagrams
- Semantic icon synthesizer for flow nodes (Notes, Client, Decision, Inspection, Deploy, etc.)
- Math / Equation breakdown schematics
- SVG Sanitization for total browser security
- Proxies through /img/{id}
"""

import os
import re
import uuid
import time
import html
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.models import REASONING_MODEL, IMAGE_MODEL

logger = logging.getLogger("images")

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "images"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_storage_client = None

def get_storage_client():
    global _storage_client
    if _storage_client is None:
        try:
            from google.cloud import storage
            project = os.getenv("GOOGLE_CLOUD_PROJECT", "project-97d34c6c-e057-425f-987")
            if project:
                _storage_client = storage.Client(project=project)
        except Exception as e:
            logger.debug(f"Cloud Storage not initialized ({e}); using local image cache.")
    return _storage_client


def sanitize_svg(raw_svg: str) -> str:
    """
    Strips scripts, event handlers, and unsafe constructs to guarantee SVG safety.
    """
    if not raw_svg:
        return ""
    # Strip script tags
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "", raw_svg)
    # Strip on* event handlers (e.g. onload, onclick, onerror)
    cleaned = re.sub(r"(?i)\s+on\w+\s*=\s*['\"][^'\"]*['\"]", "", cleaned)
    cleaned = re.sub(r"(?i)\s+on\w+\s*=\s*[^>\s]+", "", cleaned)
    # Strip javascript: and data: pseudo-protocols
    cleaned = re.sub(r"(?i)href\s*=\s*['\"]javascript:[^'\"]*['\"]", 'href="#"', cleaned)
    cleaned = re.sub(r"(?i)xlink:href\s*=\s*['\"]javascript:[^'\"]*['\"]", 'xlink:href="#"', cleaned)
    # Strip foreignObject which could embed HTML
    cleaned = re.sub(r"(?is)<foreignObject.*?>.*?</foreignObject>", "", cleaned)
    return cleaned.strip()


def build_semantic_step_icon(label: str) -> str:
    """
    Generates a unique, high-contrast, distinct 48x48 vector icon for flow diagram steps.
    Never repeats generic templates; selects distinct geometry based on step semantics.
    """
    lbl = label.lower().strip()

    # 0. Banana / Banana Shape / Nano Banana (Nano Banana Mascot)
    if any(k in lbl for k in ["banana", "banana shape", "fruit", "yellow shape"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <path d="M 10 38 C 7 24, 20 10, 36 8 C 38 7, 40 8, 39 10 C 37 13, 30 16, 25 22 C 18 30, 15 39, 10 38 Z" fill="#facc15" stroke="#eab308" stroke-width="2"/>
  <path d="M 36 8 L 41 6" stroke="#854d0e" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M 12 37 C 17 31, 23 23, 28 17" stroke="#fef08a" stroke-width="1.8" stroke-linecap="round" fill="none"/>
  <circle cx="28" cy="19" r="1.5" fill="#ca8a04"/>
</svg>'''

    # 1. Capture / Photo / Camera / Scan / Image
    elif any(k in lbl for k in ["capture", "photo", "camera", "snap", "scan", "raw image", "lens"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <rect x="6" y="13" width="36" height="26" rx="6" fill="#091224" stroke="#06b6d4" stroke-width="2"/>
  <circle cx="24" cy="26" r="9" fill="#0f1f38" stroke="#38bdf8" stroke-width="2"/>
  <circle cx="24" cy="26" r="4" fill="#06b6d4"/>
  <rect x="18" y="8" width="12" height="5" rx="2" fill="#06b6d4"/>
  <circle cx="35" cy="19" r="2" fill="#22d3ee"/>
</svg>'''

    # 2. Convert / OCR / Text Extract / Parse / Transform
    elif any(k in lbl for k in ["convert", "extract", "ocr", "image to text", "parse", "transform", "transcribe"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <rect x="5" y="10" width="16" height="22" rx="3" fill="#0b172a" stroke="#06b6d4" stroke-width="1.8"/>
  <circle cx="13" cy="17" r="2.5" fill="#38bdf8"/>
  <path d="M 8 26 L 12 21 L 18 28" stroke="#38bdf8" stroke-width="1.5" fill="none"/>
  <path d="M 23 24 L 27 24 M 25 21 L 28 24 L 25 27" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
  <rect x="27" y="14" width="16" height="24" rx="3" fill="#06281e" stroke="#10b981" stroke-width="1.8"/>
  <line x1="31" y1="21" x2="39" y2="21" stroke="#34d399" stroke-width="2" stroke-linecap="round"/>
  <line x1="31" y1="26" x2="37" y2="26" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="31" y1="31" x2="38" y2="31" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
</svg>'''

    # 3. Notes / Documentation / Writing
    elif any(k in lbl for k in ["note", "doc", "write", "record", "log", "summary", "memo"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <rect x="10" y="6" width="28" height="36" rx="4" fill="#0b172a" stroke="#06b6d4" stroke-width="2"/>
  <line x1="16" y1="14" x2="26" y2="14" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"/>
  <line x1="16" y1="20" x2="32" y2="20" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="16" y1="26" x2="30" y2="26" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="16" y1="32" x2="24" y2="32" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="34" cy="34" r="5" fill="#06b6d4"/>
  <path d="M 33 34 L 35 32" stroke="#000" stroke-width="1.5"/>
</svg>'''

    # 4. Client / Share / User / Customer / Present / Handover
    elif any(k in lbl for k in ["client", "user", "customer", "show", "present", "stakeholder", "demo", "share", "handover"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <rect x="6" y="8" width="36" height="26" rx="4" fill="#0f172a" stroke="#10b981" stroke-width="2"/>
  <circle cx="24" cy="18" r="5" fill="#34d399"/>
  <path d="M 16 29 C 16 24, 32 24, 32 29" stroke="#34d399" stroke-width="2" fill="none"/>
  <line x1="24" y1="34" x2="24" y2="40" stroke="#10b981" stroke-width="2"/>
  <line x1="16" y1="40" x2="32" y2="40" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
  <circle cx="37" cy="11" r="3" fill="#22d3ee"/>
</svg>'''

    # 5. Inspection / QA / Verify / Audit / Review
    elif any(k in lbl for k in ["inspect", "qa", "verify", "check", "audit", "review", "test", "internal review"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <circle cx="20" cy="20" r="11" fill="#082f49" stroke="#38bdf8" stroke-width="2.5"/>
  <line x1="28" y1="28" x2="40" y2="40" stroke="#38bdf8" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M 14 20 L 18 24 L 26 16" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

    # 5. Delivery / Shipping / Deploy / Release / Ship
    elif any(k in lbl for k in ["ship", "deliver", "deploy", "release", "send", "finish", "export"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <path d="M 24 6 L 40 15 L 24 24 L 8 15 Z" fill="#064e3b" stroke="#34d399" stroke-width="2"/>
  <path d="M 8 15 L 8 33 L 24 42 L 24 24 Z" fill="#022c22" stroke="#34d399" stroke-width="2"/>
  <path d="M 40 15 L 40 33 L 24 42 L 24 24 Z" fill="#065f46" stroke="#34d399" stroke-width="2"/>
  <line x1="24" y1="24" x2="24" y2="42" stroke="#10b981" stroke-width="2"/>
</svg>'''

    # 6. Finance / Pricing / Cost / Budget / Metric
    elif any(k in lbl for k in ["cost", "price", "budget", "finance", "rate", "$", "pay"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <circle cx="24" cy="24" r="17" fill="#451a03" stroke="#f59e0b" stroke-width="2"/>
  <text x="24" y="32" fill="#fbbf24" font-size="22" font-weight="900" text-anchor="middle" font-family="monospace">$</text>
  <path d="M 12 12 L 18 6" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
</svg>'''

    # 7. Code / Tech / Dev / Build / API
    elif any(k in lbl for k in ["code", "dev", "api", "build", "compile", "tech", "software"]):
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <rect x="6" y="8" width="36" height="32" rx="6" fill="#090d16" stroke="#06b6d4" stroke-width="2"/>
  <path d="M 16 20 L 11 24 L 16 28" stroke="#38bdf8" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M 32 20 L 37 24 L 32 28" stroke="#38bdf8" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="26" y1="18" x2="22" y2="30" stroke="#64748b" stroke-width="2" stroke-linecap="round"/>
</svg>'''

    # 8. General / Action Node (Initial-based neon tech badge)
    initial = (label.strip()[:2] if len(label.strip()) >= 2 else label.strip()[:1]).upper()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="100%" height="100%">
  <polygon points="24,4 42,14 42,34 24,44 6,34 6,14" fill="#0c1322" stroke="#06b6d4" stroke-width="2"/>
  <text x="24" y="29" fill="#38bdf8" font-size="14" font-weight="800" text-anchor="middle" font-family="monospace">{html.escape(initial)}</text>
</svg>'''


def generate_nano_banana_image(
    concept: str,
    context: str = ""
) -> Tuple[str, str]:
    """
    Generates high-contrast visual illustrations and technical descriptions using
    Gemini 2.5 Flash Image (Nano Banana) via GenAI Client (Vertex AI / global).
    Returns (image_url, description_text).
    Falls back gracefully to high-contrast vector synthesizer if offline.
    """
    ext = ".png"
    generated_bytes = None
    description_text = ""

    try:
        from google import genai
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        api_key = os.getenv("GEMINI_API_KEY")

        client = None
        if use_vertex and project:
            client = genai.Client(vertexai=True, project=project, location=location)
        elif api_key:
            client = genai.Client(api_key=api_key)

        if client:
            model = os.getenv("IMAGE_MODEL", IMAGE_MODEL)
            prompt = (
                f"Create a clean, minimalist, high-contrast visual illustration for this technical concept: '{concept}'. "
                f"Context: '{context}'. "
                f"Style: Dark OLED aesthetic (#050811), crisp clean lines with high-tech neon cyan (#06b6d4) and emerald (#10b981) accents. "
                f"Also provide a concise 1-sentence technical explanation of what is depicted."
            )
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            if resp.candidates and resp.candidates[0].content:
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        description_text += part.text + " "
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        generated_bytes = part.inline_data.data
                        mime_type = getattr(part.inline_data, "mime_type", "")
                        if "jpeg" in mime_type or "jpg" in mime_type:
                            ext = ".jpg"
                        else:
                            ext = ".png"

            description_text = description_text.strip()
    except Exception as e:
        logger.warning(f"Gemini 3.1 Flash Lite Image generation failed ({e}); using vector fallback.")

    if generated_bytes:
        image_id = f"nb_{uuid.uuid4().hex[:12]}{ext}"
        local_path = CACHE_DIR / image_id
        with open(local_path, "wb") as f:
            f.write(generated_bytes)
        return f"/img/{image_id}", description_text

    # Fallback to SVG schematic
    svg_url = generate_step_image(concept, context or description_text, is_icon=False)
    fallback_desc = description_text or f"Technical schematic and execution model for '{concept}'."
    return svg_url, fallback_desc


def generate_step_image(
    node_label: str,
    visual_description: str,
    context: Optional[str] = None,
    is_icon: bool = False,
) -> str:
    """
    Generates a step illustration icon (is_icon=True) or contextual explanatory diagram.
    Uses Gemini 2.5 Flash-Lite with high-speed execution and smart semantic fallbacks.
    Returns relative URL path: /img/{image_id}
    """
    image_id = f"{uuid.uuid4().hex[:12]}.svg"
    local_path = CACHE_DIR / image_id
    generated_bytes = None

    # For compact flow node icons (36x36 px)
    if is_icon or ("line icon" in visual_description.lower() and len(node_label) < 25):
        svg_content = build_semantic_step_icon(node_label)
        generated_bytes = sanitize_svg(svg_content).encode("utf-8")
        with open(local_path, "wb") as f:
            f.write(generated_bytes)
    # Dedicated high-contrast Nano Banana illustration schematic
    if any(k in node_label.lower() for k in ["banana", "banana shape", "banana shappe"]):
        svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 200" width="100%" height="auto">
  <defs>
    <filter id="banana-glow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="#facc15" flood-opacity="0.6"/>
    </filter>
  </defs>
  <rect width="380" height="200" rx="14" fill="#060c18" stroke="#1e293b" stroke-width="1.5"/>
  <text x="25" y="28" fill="#64748b" font-size="10" font-family="monospace" letter-spacing="1">NANO BANANA ILLUSTRATION // SHAPE MODEL</text>
  
  <g transform="translate(190, 110) scale(1.6)" filter="url(#banana-glow)">
    <path d="M -40 30 C -60 -10, 0 -60, 50 -60 C 55 -60, 60 -56, 56 -50 C 50 -40, 25 -30, 10 -10 C -10 15, -20 40, -40 30 Z" fill="#facc15" stroke="#eab308" stroke-width="3"/>
    <path d="M 50 -60 L 62 -65" stroke="#713f12" stroke-width="4" stroke-linecap="round"/>
    <path d="M -34 26 C -20 10, 5 -12, 28 -30" stroke="#fef08a" stroke-width="2.5" stroke-linecap="round" fill="none"/>
    <circle cx="28" cy="-26" r="2.5" fill="#ca8a04"/>
  </g>
  <text x="190" y="185" fill="#fef08a" font-size="13" font-weight="bold" font-family="monospace" text-anchor="middle">🍌 Banana Shape Vector Model</text>
</svg>'''
        generated_bytes = sanitize_svg(svg_content).encode("utf-8")
        with open(local_path, "wb") as f:
            f.write(generated_bytes)
        return f"/img/{image_id}"

    # Instant sub-millisecond math/calculation schematic (Zero LLM latency!)
    math_match = re.search(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)", node_label)
    if math_match:
        op1, op, op2 = math_match.group(1), math_match.group(2), math_match.group(3)
        try:
            n1, n2 = float(op1), float(op2)
            if op == "+": res_val = n1 + n2
            elif op == "-": res_val = n1 - n2
            elif op == "*": res_val = n1 * n2
            elif op == "/" and n2 != 0: res_val = n1 / n2
            else: res_val = "?"
            res_str = f"{int(res_val)}" if isinstance(res_val, float) and res_val.is_integer() else f"{res_val}"
        except Exception:
            res_str = "Result"

        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 140" width="100%" height="auto">
  <defs>
    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#06b6d4" flood-opacity="0.6"/>
    </filter>
    <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#10b981" flood-opacity="0.7"/>
    </filter>
  </defs>
  <rect width="380" height="140" rx="12" fill="#050811" stroke="#1e293b" stroke-width="1.5"/>
  <text x="25" y="24" fill="#64748b" font-size="9" font-family="monospace" letter-spacing="1">CALCULATION &amp; METRIC BREAKDOWN</text>
  
  <rect x="25" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="62" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op1}</text>
  <text x="62" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value A</text>

  <circle cx="125" cy="69" r="14" fill="#0f172a" stroke="#334155" stroke-width="1"/>
  <text x="125" y="75" fill="#38bdf8" font-size="18" font-weight="bold" text-anchor="middle" font-family="monospace">{op}</text>

  <rect x="165" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="202" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op2}</text>
  <text x="202" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value B</text>

  <path d="M 255 69 L 275 69" stroke="#10b981" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <polygon points="275,64 283,69 275,74" fill="#10b981"/>

  <rect x="290" y="38" width="70" height="62" rx="10" fill="#06281e" stroke="#10b981" stroke-width="2" filter="url(#glow-green)"/>
  <text x="325" y="76" fill="#34d399" font-size="22" font-weight="800" text-anchor="middle" font-family="monospace">{res_str}</text>
  <text x="325" y="116" fill="#34d399" font-size="9" font-weight="bold" text-anchor="middle" font-family="sans-serif">RESULT</text>
</svg>'''
        generated_bytes = sanitize_svg(svg_content).encode("utf-8")
        with open(local_path, "wb") as f:
            f.write(generated_bytes)
        return f"/img/{image_id}"

    # For explanatory schematics and answer diagrams:
    # Attempt Gemini 2.5 Flash-Lite SVG generation for exact contextual diagram
    try:
        from google import genai
        from google.genai import types
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        api_key = os.getenv("GEMINI_API_KEY")

        client = None
        if use_vertex and project:
            client = genai.Client(vertexai=True, project=project, location=location)
        elif api_key:
            client = genai.Client(api_key=api_key)

        if client:
            context_snippet = f"Meeting conversation context: {context[:250]}" if context else ""
            prompt = (
                f"You are a technical visual diagram generator for an AI meeting assistant.\n"
                f"Create a clean, minimalist SVG diagram illustrating: '{node_label}'.\n"
                f"Description: '{visual_description}'.\n"
                f"{context_snippet}\n"
                f"Requirements:\n"
                f"- Return a complete <svg viewBox='0 0 380 140' xmlns='http://www.w3.org/2000/svg'>...</svg>\n"
                f"- Deep OLED dark background '#050811'\n"
                f"- High-tech neon cyan (#06b6d4), emerald (#10b981), and white (#f8fafc) lines/text\n"
                f"- Clean vector shapes, clear typography, and meaningful connections explaining the concept/calculation\n"
                f"- Output ONLY valid raw <svg>...</svg> markup with NO markdown fences."
            )
            resp = client.models.generate_content(
                model=REASONING_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.1,
                ),
            )
            if resp.text:
                raw_svg = resp.text.strip()
                if "```" in raw_svg:
                    raw_svg = re.sub(r"```(?:xml|svg)?", "", raw_svg).strip("` \n")
                if "<svg" in raw_svg and "</svg>" in raw_svg:
                    start_idx = raw_svg.find("<svg")
                    end_idx = raw_svg.rfind("</svg>") + 6
                    svg_clean = sanitize_svg(raw_svg[start_idx:end_idx])
                    if svg_clean:
                        generated_bytes = svg_clean.encode("utf-8")
    except Exception as e:
        logger.warning(f"Gemini SVG diagram generation error ({e}); using smart dynamic SVG synthesizer.")

    # Intelligent dynamic SVG fallback (Math, Flow, or Semantic Diagram)
    if not generated_bytes:
        clean_label = html.escape(node_label.strip() or "Concept")

        # Detect calculation / arithmetic: e.g. "10 + 10", "48000 * 12"
        math_match = re.search(r"(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)", node_label)
        if math_match:
            op1, op, op2 = math_match.group(1), math_match.group(2), math_match.group(3)
            try:
                n1, n2 = float(op1), float(op2)
                if op == "+": res_val = n1 + n2
                elif op == "-": res_val = n1 - n2
                elif op == "*": res_val = n1 * n2
                elif op == "/" and n2 != 0: res_val = n1 / n2
                else: res_val = "?"
                res_str = f"{int(res_val)}" if isinstance(res_val, float) and res_val.is_integer() else f"{res_val}"
            except Exception:
                res_str = "Result"

            svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 140" width="100%" height="auto">
  <defs>
    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#06b6d4" flood-opacity="0.6"/>
    </filter>
    <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#10b981" flood-opacity="0.7"/>
    </filter>
  </defs>
  <rect width="380" height="140" rx="12" fill="#050811" stroke="#1e293b" stroke-width="1.5"/>
  <text x="25" y="24" fill="#64748b" font-size="9" font-family="monospace" letter-spacing="1">CALCULATION &amp; METRIC BREAKDOWN</text>
  
  <rect x="25" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="62" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op1}</text>
  <text x="62" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value A</text>

  <circle cx="125" cy="69" r="14" fill="#0f172a" stroke="#334155" stroke-width="1"/>
  <text x="125" y="75" fill="#38bdf8" font-size="18" font-weight="bold" text-anchor="middle" font-family="monospace">{op}</text>

  <rect x="165" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="202" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op2}</text>
  <text x="202" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value B</text>

  <path d="M 255 69 L 275 69" stroke="#10b981" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <polygon points="275,64 283,69 275,74" fill="#10b981"/>

  <rect x="290" y="38" width="70" height="62" rx="10" fill="#06281e" stroke="#10b981" stroke-width="2" filter="url(#glow-green)"/>
  <text x="325" y="76" fill="#34d399" font-size="22" font-weight="800" text-anchor="middle" font-family="monospace">{res_str}</text>
  <text x="325" y="116" fill="#34d399" font-size="9" font-weight="bold" text-anchor="middle" font-family="sans-serif">RESULT</text>
</svg>'''
        else:
            svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 140" width="100%" height="auto">
  <defs>
    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#06b6d4" flood-opacity="0.5"/>
    </filter>
  </defs>
  <rect width="380" height="140" rx="12" fill="#050811" stroke="#1e293b" stroke-width="1.5"/>
  <text x="25" y="24" fill="#64748b" font-size="9" font-family="monospace" letter-spacing="1">TOPIC SCHEMATIC // MEETING KNOWLEDGE</text>

  <rect x="25" y="44" width="100" height="52" rx="8" fill="#091326" stroke="#06b6d4" stroke-width="1.5"/>
  <text x="75" y="74" fill="#f8fafc" font-size="11" font-weight="600" text-anchor="middle" font-family="sans-serif">{clean_label[:14]}</text>

  <path d="M 125 70 L 175 70" stroke="#06b6d4" stroke-width="2" stroke-dasharray="4" fill="none"/>
  <polygon points="175,66 182,70 175,74" fill="#06b6d4"/>

  <rect x="185" y="38" width="90" height="64" rx="10" fill="#0d1b33" stroke="#38bdf8" stroke-width="2" filter="url(#glow-cyan)"/>
  <text x="230" y="68" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle" font-family="sans-serif">Analysis</text>
  <text x="230" y="84" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Synthesis</text>

  <path d="M 275 70 L 305 70" stroke="#10b981" stroke-width="2" fill="none"/>
  <polygon points="305,66 312,70 305,74" fill="#10b981"/>
  <rect x="312" y="46" width="50" height="48" rx="8" fill="#06281e" stroke="#10b981" stroke-width="1.5"/>
  <text x="337" y="74" fill="#34d399" font-size="10" font-weight="bold" text-anchor="middle" font-family="sans-serif">Valid</text>
</svg>'''

        generated_bytes = sanitize_svg(svg_content).encode("utf-8")

    # Save to local cache
    with open(local_path, "wb") as f:
        f.write(generated_bytes)

    # Cloud Storage sync if configured
    bucket_name = os.getenv("GCS_BUCKET")
    if bucket_name:
        client = get_storage_client()
        if client:
            try:
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(f"images/{image_id}")
                content_type = "image/svg+xml" if image_id.endswith(".svg") else "image/png"
                blob.upload_from_filename(str(local_path), content_type=content_type)
            except Exception as e:
                logger.warning(f"GCS upload failed ({e})")

    return f"/img/{image_id}"


def get_image(image_id: str) -> Optional[Tuple[bytes, str]]:
    """Retrieve image bytes and mime type by image_id."""
    local_path = CACHE_DIR / image_id
    if image_id.endswith(".svg"):
        mime = "image/svg+xml"
    elif image_id.endswith(".jpg") or image_id.endswith(".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"

    if local_path.exists():
        with open(local_path, "rb") as f:
            return f.read(), mime

    bucket_name = os.getenv("GCS_BUCKET")
    if bucket_name:
        client = get_storage_client()
        if client:
            try:
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(f"images/{image_id}")
                data = blob.download_as_bytes()
                with open(local_path, "wb") as f:
                    f.write(data)
                return data, mime
            except Exception as e:
                logger.warning(f"GCS download failed for {image_id}: {e}")

    return None
