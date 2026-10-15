"""
Central model configuration module.
Resolves REASONING_MODEL and IMAGE_MODEL from environment variables.
Provides intelligent validation & fallback for Flash-Lite speed optimizations.
"""

import os
import logging

logger = logging.getLogger("models")


def resolve_reasoning_model() -> str:
    """
    Resolves the fastest flash-lite model available.
    Configured for 'gemini-3.5-flash-lite' with automatic fallback to 'gemini-2.5-flash-lite'
    if the Vertex AI project region does not yet host 3.5.
    """
    requested = os.getenv("REASONING_MODEL", "gemini-3.5-flash-lite").strip()
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"

    if requested in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite") and use_vertex:
        try:
            from google import genai
            project = os.getenv("GOOGLE_CLOUD_PROJECT")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
            client = genai.Client(vertexai=True, project=project, location=location)
            client.models.generate_content(model=requested, contents="test")
            logger.info(f"Successfully connected to Vertex AI model: {requested}")
            return requested
        except Exception:
            logger.info(
                f"Model '{requested}' is not yet enabled on Vertex AI for this project. "
                f"Active high-speed Flash-Lite model: 'gemini-2.5-flash-lite'"
            )
            return "gemini-2.5-flash-lite"

    return requested


REASONING_MODEL = resolve_reasoning_model()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-3.0-generate-002")
