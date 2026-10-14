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


def generate_step_image(node_label: str, visual_description: str) -> str:
    """
    Generates a step illustration icon.
    Returns the relative URL path: /img/{image_id}
    """
    image_id = f"{uuid.uuid4().hex[:12]}.png"
    local_path = CACHE_DIR / image_id

    # Strict icon prompt as required by Section 11
    prompt = (
        f"A flat, single-subject, monochrome black-and-white line icon on pure transparent background. "
        f"Concept: {node_label}. Description: {visual_description}. Minimalist, vector style outline, no shading, no background."
    )

    generated_bytes = None

    try:
        from google import genai
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

        client = None
        if use_vertex and project:
            client = genai.Client(vertexai=True, project=project, location=location)

        if client:
            result = client.models.generate_images(
                model=IMAGE_MODEL,
                prompt=prompt,
                config=dict(
                    number_of_images=1,
                    output_mime_type="image/png",
                    aspect_ratio="1:1"
                ),
            )
            if result.generated_images:
                generated_bytes = result.generated_images[0].image.image_bytes
    except Exception as e:
        logger.warning(f"Vertex image generation failed ({e}); generating crisp deterministic line SVG icon.")

    if not generated_bytes:
        # Fallback SVG line icon saved as PNG or SVG placeholder
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="16" fill="#f1f5f9"/>
  <circle cx="50" cy="50" r="32" fill="none" stroke="#2563eb" stroke-width="4" stroke-dasharray="4 2"/>
  <path d="M40 50 L47 57 L62 42" fill="none" stroke="#2563eb" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
        generated_bytes = svg_content.encode("utf-8")
        image_id = f"{uuid.uuid4().hex[:12]}.svg"
        local_path = CACHE_DIR / image_id

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
