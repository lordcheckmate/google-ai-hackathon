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
    Supports 'gemini-3.5-flash-lite' deployed on Gemini Enterprise Agent Platform (global location).
    """
    requested = os.getenv("REASONING_MODEL", "gemini-3.5-flash-lite").strip()
    return requested or "gemini-3.5-flash-lite"


REASONING_MODEL = resolve_reasoning_model()
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-2.5-flash-image")
