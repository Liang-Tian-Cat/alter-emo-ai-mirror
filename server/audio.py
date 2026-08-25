"""Microphone capture, speech-to-text, and text-to-speech services."""

from __future__ import annotations

import io
import os
import threading
import wave
from typing import Any

import numpy as np

from src.runtime_config import create_openai_client, load_settings


class AudioService:
    def __init__(self, client: Any | None = None, *, sample_rate: int = 16000):
        self._client = client
        self.sample_rate = sample_rate
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.RLock()

    @property
    def configured(self) -> bool:
        settings = load_settings()
        return bool(settings.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))

    def _openai(self):
        if self._client is None:
            self._client = create_openai_client(load_settings())
        return self._client

    def start_recording(self) -> dict[str, Any]:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice is not installed; install requirements.txt") from exc
        with self._lock:
            if self._stream is not None:
                raise ValueError("A recording is already in progress")
            self._chunks = []

            def callback(indata, _frames, _time, status):
                if status:
                    # PortAudio status is diagnostic; captured frames remain usable.
                    pass
                self._chunks.append(indata.copy())

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    callback=callback,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                raise RuntimeError(f"Could not start microphone capture: {exc}") from exc
        return {"recording": True, "sample_rate": self.sample_rate}

    def stop_recording(self, *, transcribe: bool = True) -> dict[str, Any]:
        with self._lock:
            if self._stream is None:
                raise ValueError("No recording is in progress")
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                self._stream = None
                self._chunks = []
                raise RuntimeError(f"Could not stop microphone capture: {exc}") from exc
            self._stream = None
            samples = np.concatenate(self._chunks, axis=0) if self._chunks else np.zeros((0, 1), dtype=np.int16)
            self._chunks = []
        audio = self._wav_bytes(samples)
        result: dict[str, Any] = {"recording": False, "audio_bytes": len(audio)}
        if transcribe:
            result["transcript"] = self.transcribe(audio, "recording.wav")
        return result

    def transcribe(self, audio: bytes, filename: str = "recording.wav") -> str:
        if not audio:
            raise ValueError("audio is required")
        upload = io.BytesIO(audio)
        upload.name = filename
        try:
            response = self._openai().audio.transcriptions.create(
                model=os.getenv("ALTER_EMO_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
                file=upload,
            )
        except Exception as exc:
            raise RuntimeError(f"Speech transcription failed: {exc}") from exc
        return str(getattr(response, "text", "")).strip()

    def synthesize(self, text: str, voice: str = "alloy") -> bytes:
        if not text.strip():
            raise ValueError("text is required")
        try:
            response = self._openai().audio.speech.create(
                model=os.getenv("ALTER_EMO_TTS_MODEL", "gpt-4o-mini-tts"),
                voice=voice,
                input=text.strip(),
            )
        except Exception as exc:
            raise RuntimeError(f"Speech synthesis failed: {exc}") from exc
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content
        reader = getattr(response, "read", None)
        if callable(reader):
            return bytes(reader())
        raise RuntimeError("The speech provider returned no audio")

    def _wav_bytes(self, samples: np.ndarray) -> bytes:
        target = io.BytesIO()
        with wave.open(target, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(samples.astype(np.int16).tobytes())
        return target.getvalue()
