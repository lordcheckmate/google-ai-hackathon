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
    Resolves the fastest available flash-lite model.
    Defaults to 'gemini-2.5-flash-lite' which is verified and instant on Vertex AI.
    """
    requested = os.getenv("REASONING_MODEL", "gemini-2.5-flash-lite").strip()
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"

    # Known models requiring Gemini Developer API rather than Vertex AI in current region
    if use_vertex and requested in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
        logger.info(
            f"Model '{requested}' is designated for Gemini Developer API. "
            f"Using active high-speed Vertex AI model: 'gemini-2.5-flash-lite'"
        )
        return "gemini-2.5-flash-lite"

    return requested or "gemini-2.5-flash-lite"


REASONING_MODEL = resolve_reasoning_model()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-3.0-generate-002")
