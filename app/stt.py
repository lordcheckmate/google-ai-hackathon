"""
Speech-to-Text v2 Streaming Module.
Bridges Google Cloud Speech-to-Text v2 streaming_recognize with asyncio WebSockets.
Features:
- LINEAR16, 16000Hz, 1 channel
- Thread-safe bridging between gRPC request generator and asyncio loop
- Dynamic phrase hints adaptation
- Auto-reconnect for Google's ~5 minute stream limit
- Echo suppression window (for TTS playback)
"""

import os
import time
import queue
import logging
import threading
import asyncio
from typing import Callable, List, Optional

logger = logging.getLogger("stt")

# Echo suppression timestamp: discard transcripts received before this time
_echo_suppression_until = 0.0

def suppress_echo(duration_seconds: float = 0.7):
    """Suppress transcripts for a given duration after TTS playback."""
    global _echo_suppression_until
    _echo_suppression_until = max(_echo_suppression_until, time.time() + duration_seconds)

def is_echo_suppressed() -> bool:
    """Check if current time is within echo suppression window."""
    return time.time() < _echo_suppression_until


class STTSession:
    """Manages a single streaming STT session for a connected client."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        on_transcript: Callable[[str, bool], None],
        phrase_hints: Optional[List[str]] = None,
        language_code: str = "en-US",
    ):
        self.loop = loop
        self.on_transcript = on_transcript
        self.phrase_hints = phrase_hints or []
        self.language_code = language_code
        self.audio_queue: queue.Queue = queue.Queue(maxsize=500)
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "project-97d34c6c-e057-425f-987"

    def update_phrase_hints(self, hints: List[str]):
        """Update domain phrase hints when canvas blocks change."""
        self.phrase_hints = hints

    def push_audio(self, chunk: bytes):
        """Enqueue PCM chunk from WebSocket into audio queue."""
        if not self.stop_event.is_set():
            try:
                self.audio_queue.put_nowait(chunk)
            except queue.Full:
                logger.warning("Audio queue full, dropping chunk")

    def start(self):
        """Start the background streaming thread."""
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_stream_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop streaming and terminate thread."""
        self.stop_event.set()
        try:
            self.audio_queue.put_nowait(None)
        except Exception:
            pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def _run_stream_loop(self):
        """Outer loop that transparently restarts the stream when 5-min limit is reached."""
        while not self.stop_event.is_set():
            try:
                self._stream_recognize()
            except Exception as e:
                if self.stop_event.is_set():
                    break
                logger.warning(f"STT stream encountered error or ended: {e}. Reconnecting in 0.5s...")
                time.sleep(0.5)

    def _stream_recognize(self):
        """Inner synchronous gRPC streaming session."""
        try:
            from google.cloud import speech_v2
            from google.cloud.speech_v2.types import cloud_speech
        except ImportError:
            logger.error("google-cloud-speech is not installed.")
            time.sleep(2.0)
            return

        project = self.project_id
        if not project:
            # Fallback for local testing without project ID configured
            logger.info("GOOGLE_CLOUD_PROJECT not set. STT waiting for configuration.")
            time.sleep(2.0)
            return

        client = speech_v2.SpeechClient()
        recognizer = f"projects/{project}/locations/global/recognizers/_"

        # Explicit decoding configuration for LINEAR16 16kHz Mono
        decoding_config = cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            audio_channel_count=1,
        )

        # Build phrase hints adaptation
        adaptation = None
        if self.phrase_hints:
            phrases = [
                cloud_speech.PhraseSet.Phrase(value=hint, boost=10.0)
                for hint in self.phrase_hints[:500]
            ]
            phrase_set = cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                inline_phrase_set=cloud_speech.PhraseSet(phrases=phrases)
            )
            adaptation = cloud_speech.SpeechAdaptation(phrase_sets=[phrase_set])

        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=decoding_config,
            language_codes=[self.language_code],
            model="long",
            adaptation=adaptation,
        )

        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=cloud_speech.StreamingRecognitionFeatures(
                interim_results=True,
            ),
        )

        # Wait for actual audio before opening the gRPC connection
        first_chunk = None
        while not self.stop_event.is_set():
            try:
                first_chunk = self.audio_queue.get(timeout=0.5)
                if first_chunk is not None:
                    break
            except queue.Empty:
                continue

        if not first_chunk or self.stop_event.is_set():
            return

        def request_generator():
            # First request must supply config
            yield cloud_speech.StreamingRecognizeRequest(
                recognizer=recognizer,
                streaming_config=streaming_config,
            )
            # Yield the first audio chunk
            yield cloud_speech.StreamingRecognizeRequest(audio=first_chunk)

            # Subsequent requests supply audio chunks
            while not self.stop_event.is_set():
                try:
                    chunk = self.audio_queue.get(timeout=5.0)
                    if chunk is None:
                        break
                    yield cloud_speech.StreamingRecognizeRequest(audio=chunk)
                except queue.Empty:
                    # Idle for 5 seconds; close stream cleanly
                    break

        responses = client.streaming_recognize(requests=request_generator())

        for response in responses:
            if self.stop_event.is_set():
                break

            for result in response.results:
                if not result.alternatives:
                    continue

                # Check echo suppression
                if is_echo_suppressed():
                    continue

                transcript = result.alternatives[0].transcript.strip()
                is_final = result.is_final

                if transcript:
                    # Bridge safely back into the asyncio event loop
                    self.loop.call_soon_threadsafe(
                        self.on_transcript, transcript, is_final
                    )
