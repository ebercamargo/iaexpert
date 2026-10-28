"""Microfone (VAD simples), transcrição offline e síntese Piper PT-BR."""

from __future__ import annotations

import io
import math
import os
import time
import wave
from collections import deque
from pathlib import Path
from threading import Event
from urllib import request

import numpy as np
import sounddevice as sd

from .config import Settings, data_directory


SAMPLE_RATE = 16_000
BLOCK_SIZE = 480  # 30 ms
VOICE_NAME = "pt_BR-faber-medium"
VOICE_BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "pt/pt_BR/faber/medium/"
)


class Microphone:
    def __init__(self, threshold: float = 0.008, device: int | None = None) -> None:
        self.threshold = threshold
        self.device = device

    def record(self, stop: Event, wait_seconds: float | None = 15.0) -> np.ndarray | None:
        """Detecta a fala, inclui um pré-roll e encerra após silêncio.

        Retorna None se o usuário cancelar ou se não houver fala no período.
        O áudio nunca é enviado a servidores: a transcrição ocorre localmente.
        """
        frames: list[np.ndarray] = []
        preroll: deque[np.ndarray] = deque(maxlen=12)
        speech_started = False
        consecutive = 0
        started_at = time.monotonic()
        speech_at = started_at
        last_loud = started_at

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            device=self.device,
        ) as stream:
            while not stop.is_set():
                block, _ = stream.read(BLOCK_SIZE)
                chunk = block[:, 0].copy()
                loudness = math.sqrt(float(np.mean(chunk * chunk)))
                now = time.monotonic()

                if not speech_started:
                    preroll.append(chunk)
                    consecutive = consecutive + 1 if loudness >= self.threshold else 0
                    if consecutive >= 3:
                        speech_started = True
                        speech_at = now
                        last_loud = now
                        frames.extend(preroll)
                    elif wait_seconds is not None and now - started_at > wait_seconds:
                        return None
                else:
                    frames.append(chunk)
                    if loudness >= self.threshold:
                        last_loud = now
                    # Falas curtas demais costumam ser ruído do ambiente.
                    if now - last_loud > 0.72:
                        if now - speech_at >= 0.35:
                            break
                        speech_started = False
                        preroll.clear()
                        frames.clear()
                    if now - speech_at > 28:
                        break

        if stop.is_set() or not frames:
            return None
        audio = np.concatenate(frames).astype(np.float32)
        return audio if len(audio) >= int(SAMPLE_RATE * 0.4) else None


class SpeechToText:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self.device = 'cpu'

    def transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            from faster_whisper import WhisperModel

            device = self.settings.stt_device
            if device == "auto":
                try:
                    import ctranslate2
                    # Verificação não carrega modelo nem usa rede.
                    ctranslate2.get_supported_compute_types("cuda")
                    device = "cuda"
                except (RuntimeError, OSError, ValueError):
                    device = "cpu"
            self.device = device
            try:
                self._model = WhisperModel(
                    self.settings.whisper_model,
                    device=device,
                    compute_type="float16" if device == "cuda" else "int8",
                )
            except (RuntimeError, OSError, ValueError):
                if device == "cpu" or self.settings.stt_device == "cuda":
                    raise
                self.device = "cpu"
                self._model = WhisperModel(
                    self.settings.whisper_model, device="cpu", compute_type="int8"
                )
        try:
            segments, _ = self._model.transcribe(
                audio, language="pt", beam_size=1,
                vad_filter=False, condition_on_previous_text=False,
            )
            return " ".join(part.text.strip() for part in segments).strip()
        except (RuntimeError, OSError, ValueError):
            if self.device != "cuda" or self.settings.stt_device == "cuda":
                raise
            # Bibliotecas CUDA podem carregar e falhar na primeira inferência.
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.settings.whisper_model, device="cpu", compute_type="int8"
            )
            self.device = "cpu"
            segments, _ = self._model.transcribe(
                audio, language="pt", beam_size=1,
                vad_filter=False, condition_on_previous_text=False,
            )
            return " ".join(part.text.strip() for part in segments).strip()


class VoiceOutput:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = (directory or data_directory()) / "voices"
        self._voice = None

    def _download_file(self, filename: str) -> None:
        destination = self.directory / filename
        if destination.exists() and destination.stat().st_size > 1000:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        req = request.Request(
            VOICE_BASE_URL + filename,
            headers={"User-Agent": "IAExpert/0.1"},
        )
        try:
            with request.urlopen(req, timeout=120) as source, temporary.open("wb") as out:
                while True:
                    chunk = source.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
            if temporary.stat().st_size < 1000:
                raise OSError(f"Arquivo de voz inválido: {filename}")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _load(self):
        if self._voice is None:
            from piper import PiperVoice

            self._download_file(VOICE_NAME + ".onnx")
            self._download_file(VOICE_NAME + ".onnx.json")
            self._voice = PiperVoice.load(str(self.directory / (VOICE_NAME + ".onnx")))
        return self._voice

    def speak(self, text: str, stop: Event, on_level=None) -> None:
        if stop.is_set():
            return
        # Evita que respostas muito longas bloqueiem o próximo turno de conversa.
        passage = text[:1600].strip()
        if not passage:
            return
        voice = self._load()
        if stop.is_set():
            return
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            voice.synthesize_wav(passage, wav)
        if stop.is_set():
            return
        buffer.seek(0)
        with wave.open(buffer, "rb") as wav:
            rate = wav.getframerate()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).copy()
        sd.play(samples, samplerate=rate, blocking=False)
        origin = time.monotonic()
        try:
            while not stop.is_set():
                stream = sd.get_stream()
                if stream is None or not stream.active:
                    break
                if on_level is not None:
                    pos = int((time.monotonic() - origin) * rate)
                    window = samples[pos:pos + max(256, int(rate * 0.045))]
                    if len(window):
                        amplitude = float(np.sqrt(np.mean(window.astype(np.float32) ** 2)))
                        on_level(min(1.0, max(0.0, (amplitude - 240) / 3600)))
                if stop.wait(0.033):
                    break
        finally:
            if on_level is not None:
                on_level(0.0)
            sd.stop()
