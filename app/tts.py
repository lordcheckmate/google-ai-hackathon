"""
Text-to-Speech module using Google Cloud Text-to-Speech v1.
Synthesizes spoken replies to MP3 bytes.
"""

import os
import base64
import logging
from typing import Optional

logger = logging.getLogger("tts")

_tts_client = None

def get_tts_client():
    global _tts_client
    if _tts_client is None:
        try:
            from google.cloud import texttospeech
            _tts_client = texttospeech.TextToSpeechClient()
        except Exception as e:
            logger.warning(f"Could not initialize Cloud TTS client: {e}")
    return _tts_client


def synthesize_speech(text: str) -> Optional[str]:
    """
    Synthesizes text into MP3 audio and returns base64-encoded string.
    Returns None if synthesis fails.
    """
    if not text or not text.strip():
        return None

    client = get_tts_client()
    if not client:
        return None

    try:
        from google.cloud import texttospeech

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Journey-F",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.05,
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        return base64.b64encode(response.audio_content).decode("utf-8")

    except Exception as e:
        logger.warning(f"TTS synthesis failed for text: '{text}' ({e})")
        return None
