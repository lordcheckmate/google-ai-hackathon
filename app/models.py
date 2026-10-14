"""
Central model configuration module.
Resolves REASONING_MODEL and IMAGE_MODEL from environment variables.
Model IDs are never hardcoded as literals elsewhere in the codebase.
"""

import os

REASONING_MODEL = os.getenv("REASONING_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-3.0-generate-002")
