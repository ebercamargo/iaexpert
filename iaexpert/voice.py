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


def choose_voice(settings: Settings):
    if settings.voice_engine == "edge":
        return NaturalVoice(settings.voice_name)
    if settings.voice_engine == "piper":
        return VoiceOutput()
    raise ValueError("Escolha o motor de voz antes de iniciar a conversa.")
