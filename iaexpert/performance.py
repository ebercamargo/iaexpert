"""Diagnóstico de lentidão: sem transcrições, mensagens ou dados pessoais."""
from __future__ import annotations

import time
from datetime import datetime
from .config import data_directory


def log_turn(model: str, voice: str, stt_ms: float, start: float,
             first_token: float | None, first_audio: float | None, end: float):
    directory = data_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        values = (
            f"{datetime.now().isoformat(timespec='seconds')}"
            f" model={model} tts={voice}"
            f" stt_ms={stt_ms:.0f}"
            f" first_token_ms={((first_token-start)*1000):.0f}" if first_token else
            f"{datetime.now().isoformat(timespec='seconds')} model={model} tts={voice} stt_ms={stt_ms:.0f} first_token_ms=NA"
        )
        first_audio_text = f"{((first_audio-start)*1000):.0f}" if first_audio else "NA"
        with (directory / "performance.log").open("a", encoding="utf-8") as file:
            file.write(f"{values} first_audio_ms={first_audio_text} "
                       f"total_ms={(end-start)*1000:.0f}\n")
    except OSError:
        pass
