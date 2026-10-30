"""Saída de áudio única: avatar e som derivados dos mesmos frames PCM.

A posição do buffer é determinada pelo callback do PortAudio, e cada amostra
de amplitude recebe um instante previsto de execução no dispositivo de saída.
Isso remove o relógio simulado baseado em sd.play() e time.monotonic().
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from threading import Event

import numpy as np
import sounddevice as sd

# Valor e instante monotônico de apresentação esperado no DAC do sistema.
LevelCallback = Callable[[float, float], None]


def mouth_level(pcm: np.ndarray) -> float:
    """Envelope normalizado; usa exatamente as amostras enviadas ao alto-falante."""
    if pcm.size == 0:
        return 0.0
    rms = math.sqrt(float(np.mean(pcm.astype(np.float32) ** 2)))
    if rms <= 160.0:
        return 0.0
    return min(1.0, max(0.0, ((rms - 160.0) / 2800.0) ** 0.78))


def play_pcm(
    samples: np.ndarray,
    rate: int,
    stop: Event,
    on_level: LevelCallback | None = None,
) -> None:
    """Reproduz PCM sem relógio paralelo. O callback é cancelável.

    on_level(volume, instante) informa quando o quadro deve ser exibido.
    A estimativa do instante vem de outputBufferDacTime do PortAudio.
    """
    pcm = np.asarray(samples, dtype=np.int16)
    if pcm.ndim == 1:
        pcm = pcm.reshape(-1, 1)
    if pcm.ndim != 2 or pcm.shape[1] not in (1, 2):
        raise ValueError("Áudio precisa ser mono ou estéreo PCM16.")
    if rate <= 0:
        raise ValueError("Taxa de amostragem inválida.")
    if pcm.shape[0] == 0 or stop.is_set():
        return

    done = Event()
    frame_index = 0
    count = len(pcm)

    def audio_callback(outdata, frames, time_info, status):
        nonlocal frame_index
        if stop.is_set():
            outdata.fill(0)
            raise sd.CallbackAbort

        actual = min(frames, count - frame_index)
        if actual:
            chunk = pcm[frame_index:frame_index + actual]
            outdata[:actual] = chunk
            if actual < frames:
                outdata[actual:] = 0
            frame_index += actual

            if on_level is not None:
                # PortAudio usa o mesmo relógio para as duas propriedades.
                # Converter para timestamp monotônico conserva o atraso DAC,
                # evitando confundir "enfileirado" com "já audível".
                delay = max(
                    0.0,
                    float(time_info.outputBufferDacTime - time_info.currentTime),
                )
                due = time.monotonic() + min(delay, 0.5)
                on_level(mouth_level(chunk), due)
        else:
            outdata.fill(0)

        if frame_index >= count:
            raise sd.CallbackStop

    stream = sd.OutputStream(
        samplerate=rate,
        channels=pcm.shape[1],
        dtype="int16",
        blocksize=0,
        latency="low",
        callback=audio_callback,
        finished_callback=done.set,
    )
    try:
        with stream:
            while not done.wait(0.025):
                if stop.is_set():
                    stream.abort()
                    break
    finally:
        if on_level is not None:
            on_level(0.0, time.monotonic())
