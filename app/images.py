"""
Image generation and storage for process step illustrations (Nano Banana).
Prompts for flat, single-subject, monochrome-on-transparent line icons.
Stores in GCS (or local cache) and proxies through /img/{id}.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.models import IMAGE_MODEL

logger = logging.getLogger("images")

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "images"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_storage_client = None

def get_storage_client():
    global _storage_client
    if _storage_client is None:
        try:
            from google.cloud import storage
            project = os.getenv("GOOGLE_CLOUD_PROJECT")
            if project:
                _storage_client = storage.Client(project=project)
        except Exception as e:
            logger.debug(f"Cloud Storage not initialized ({e}); using local image cache.")
    return _storage_client


def generate_step_image(node_label: str, visual_description: str, context: Optional[str] = None) -> str:
    """
    Generates a step illustration icon or contextual explanatory diagram.
    Uses Gemini 2.5 Flash for custom SVG synthesis, with a smart dynamic fallback.
    Returns relative URL path: /img/{image_id}
    """
    image_id = f"{uuid.uuid4().hex[:12]}.svg"
    local_path = CACHE_DIR / image_id
    generated_bytes = None

    # Step 1: Attempt Gemini 2.5 Flash SVG generation for exact contextual diagram
    try:
        from google import genai
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
            context_snippet = f"Meeting conversation context: {context[:200]}" if context else ""
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
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if resp.text:
                raw_svg = resp.text.strip()
                import re
                if "```" in raw_svg:
                    raw_svg = re.sub(r"```(?:xml|svg)?", "", raw_svg).strip("` \n")
                if "<svg" in raw_svg and "</svg>" in raw_svg:
                    start_idx = raw_svg.find("<svg")
                    end_idx = raw_svg.rfind("</svg>") + 6
                    svg_clean = raw_svg[start_idx:end_idx]
                    generated_bytes = svg_clean.encode("utf-8")
    except Exception as e:
        logger.warning(f"Gemini SVG diagram generation error ({e}); using smart dynamic SVG synthesizer.")

    # Step 2: Intelligent dynamic SVG fallback (Context-aware: Math, Flow, or Concept)
    if not generated_bytes:
        import html
        import re

        clean_label = html.escape(node_label.strip() or "Concept")
        clean_desc = html.escape((visual_description or "")[:40])

        # Detect calculation / arithmetic: e.g. "10 + 10", "48000 * 12", "A + B"
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
  
  <!-- Operand 1 -->
  <rect x="25" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="62" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op1}</text>
  <text x="62" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value A</text>

  <!-- Operator -->
  <circle cx="125" cy="69" r="14" fill="#0f172a" stroke="#334155" stroke-width="1"/>
  <text x="125" y="75" fill="#38bdf8" font-size="18" font-weight="bold" text-anchor="middle" font-family="monospace">{op}</text>

  <!-- Operand 2 -->
  <rect x="165" y="42" width="75" height="54" rx="8" fill="#0a1224" stroke="#06b6d4" stroke-width="1.5" filter="url(#glow-cyan)"/>
  <text x="202" y="76" fill="#f8fafc" font-size="20" font-weight="700" text-anchor="middle" font-family="monospace">{op2}</text>
  <text x="202" y="112" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Value B</text>

  <!-- Arrow -->
  <path d="M 255 69 L 275 69" stroke="#10b981" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <polygon points="275,64 283,69 275,74" fill="#10b981"/>

  <!-- Result -->
  <rect x="290" y="38" width="70" height="62" rx="10" fill="#06281e" stroke="#10b981" stroke-width="2" filter="url(#glow-green)"/>
  <text x="325" y="76" fill="#34d399" font-size="22" font-weight="800" text-anchor="middle" font-family="monospace">{res_str}</text>
  <text x="325" y="116" fill="#34d399" font-size="9" font-weight="bold" text-anchor="middle" font-family="sans-serif">RESULT</text>
</svg>'''
        else:
            # Multi-Node Schematic Diagram
            svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 140" width="100%" height="auto">
  <defs>
    <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#06b6d4" flood-opacity="0.5"/>
    </filter>
  </defs>
  <rect width="380" height="140" rx="12" fill="#050811" stroke="#1e293b" stroke-width="1.5"/>
  <text x="25" y="24" fill="#64748b" font-size="9" font-family="monospace" letter-spacing="1">TOPIC SCHEMATIC // MEETING KNOWLEDGE</text>

  <!-- Input / Context Node -->
  <rect x="25" y="44" width="100" height="52" rx="8" fill="#091326" stroke="#06b6d4" stroke-width="1.5"/>
  <text x="75" y="74" fill="#f8fafc" font-size="11" font-weight="600" text-anchor="middle" font-family="sans-serif">{clean_label[:14]}</text>

  <!-- Connector -->
  <path d="M 125 70 L 175 70" stroke="#06b6d4" stroke-width="2" stroke-dasharray="4" fill="none"/>
  <polygon points="175,66 182,70 175,74" fill="#06b6d4"/>

  <!-- Core Process / Engine Node -->
  <rect x="185" y="38" width="90" height="64" rx="10" fill="#0d1b33" stroke="#38bdf8" stroke-width="2" filter="url(#glow-cyan)"/>
  <text x="230" y="68" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle" font-family="sans-serif">Analysis</text>
  <text x="230" y="84" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="sans-serif">Synthesis</text>

  <!-- Output Node -->
  <path d="M 275 70 L 305 70" stroke="#10b981" stroke-width="2" fill="none"/>
  <polygon points="305,66 312,70 305,74" fill="#10b981"/>
  <rect x="312" y="46" width="50" height="48" rx="8" fill="#06281e" stroke="#10b981" stroke-width="1.5"/>
  <text x="337" y="74" fill="#34d399" font-size="10" font-weight="bold" text-anchor="middle" font-family="sans-serif">Valid</text>
</svg>'''

        generated_bytes = svg_content.encode("utf-8")

    # Save to local cache
    with open(local_path, "wb") as f:
        f.write(generated_bytes)

    # If GCS_BUCKET is configured, upload to Cloud Storage
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
    mime = "image/svg+xml" if image_id.endswith(".svg") else "image/png"

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
