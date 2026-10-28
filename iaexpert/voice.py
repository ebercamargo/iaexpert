"""Voz natural on-line opcional, com reprodução no PC e lip-sync aproximado.

A API usada por edge-tts é um serviço de terceiros, sem garantias de disponibilidade.
Esta classe não envia microfone nem histórico: transmite apenas a frase da resposta
para síntese de voz, somente após a escolha expressa do usuário na interface.
"""
from __future__ import annotations

import asyncio
import time
from threading import Event
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from .config import Settings
from .audio import VoiceOutput
from threading import Lock
import logging


NATURAL_VOICES = {
    "pt-BR-FranciscaNeural": "Francisca — feminina",
    "pt-BR-AntonioNeural": "Antônio — masculina",
}


def play_pcm(
    samples: np.ndarray,
    rate: int,
    stop: Event,
    on_level: Callable[[float], None] | None = None,
) -> None:
    """Reproduz PCM com cancelamento e medição de amplitude para o avatar."""
    if stop.is_set() or samples.size == 0:
        return
    sd.play(samples, samplerate=rate, blocking=False)
    start = time.monotonic()
    try:
        while not stop.is_set():
            stream = sd.get_stream()
            if stream is None or not stream.active:
                break
            if on_level is not None:
                start_frame = int((time.monotonic() - start) * rate)
                chunk = samples[start_frame : start_frame + max(256, int(rate * .05))]
                if chunk.size:
                    rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                    on_level(min(1., max(0., (rms - 160.) / 3100.)))
            if stop.wait(.035):
                break
    finally:
        if on_level is not None:
            on_level(0.)
        sd.stop()


class NaturalVoice:
    """Edge neural voice: texto em serviço on-line, áudio devolvido em MP3."""

    def __init__(self, voice_name: str = "pt-BR-FranciscaNeural") -> None:
        if voice_name not in NATURAL_VOICES:
            raise ValueError("Voz natural não reconhecida.")
        self.voice_name = voice_name

    async def _synthesize(self, text: str, stop: Event) -> bytes:
        import edge_tts

        communicator = edge_tts.Communicate(text, voice=self.voice_name, rate="+6%")
        chunks = []
        async for data in communicator.stream():
            if stop.is_set():
                return b""
            if data["type"] == "audio":
                chunks.append(data["data"])
        return b"".join(chunks)

    def speak(self, text: str, stop: Event, on_level=None) -> None:
        if stop.is_set() or not text.strip():
            return
        try:
            audio = asyncio.run(self._synthesize(text[:1100].strip(), stop))
            if stop.is_set():
                return
            if not audio:
                raise RuntimeError("O serviço de voz não retornou áudio.")
            import miniaudio

            decoded = miniaudio.mp3_read_s16(audio)
            pcm = np.frombuffer(decoded.samples, dtype=np.int16).copy()
            if decoded.nchannels > 1:
                pcm = pcm.reshape((-1, decoded.nchannels))
            play_pcm(pcm, decoded.sample_rate, stop, on_level)
        except Exception as exc:
            if stop.is_set():
                return
            raise RuntimeError(
                "A voz neural online falhou. Verifique a internet ou escolha "
                "'Piper local' clicando com o botão direito no rosto. "
                f"Detalhe: {exc}"
            ) from exc



class ChatterboxVoice:
    """Voz neural multilíngue PT-BR na GPU. Dependência opcional, nunca na CPU."""

    def __init__(self) -> None:
        self._model = None
        self._lock = Lock()

    def preload(self) -> None:
        self._load()

    def _load(self):
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                import torch
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            except ImportError as exc:
                raise RuntimeError(
                    "Instale a voz GPU opcional pelo script Instalar-Voz-GPU.ps1."
                ) from exc
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "O Chatterbox requer GPU NVIDIA com PyTorch CUDA. "
                    "Escolha Francisca online ou Piper local no menu."
                )
            self._model = ChatterboxMultilingualTTS.from_pretrained(
                device="cuda", t3_model="v3"
            )
            return self._model

    def speak(self, text: str, stop: Event, on_level=None) -> None:
        if stop.is_set() or not text.strip():
            return
        import torch

        model = self._load()
        if stop.is_set():
            return
        with self._lock, torch.inference_mode():
            wav = model.generate(text[:650].strip(), language_id="pt")
        if stop.is_set():
            return
        signal = wav.detach().float().cpu().numpy().reshape(-1)
        pcm = np.clip(signal, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)
        play_pcm(pcm, model.sr, stop, on_level)

def choose_voice(settings: Settings):
    if settings.voice_engine == "edge":
        return NaturalVoice(settings.voice_name)
    if settings.voice_engine == "chatterbox":
        return ChatterboxVoice()
    if settings.voice_engine == "piper":
        return VoiceOutput()
    raise ValueError("Escolha o motor de voz antes de iniciar a conversa.")
