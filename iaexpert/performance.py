"""Registra somente métricas técnicas, sem mensagens e sem dados pessoais."""
from __future__ import annotations
from datetime import datetime
from .config import data_directory


def log_turn(model: str, voice: str, stt_ms: float, start: float,
             first_token: float | None, first_audio: float | None, end: float):
    try:
        directory = data_directory()
        directory.mkdir(parents=True, exist_ok=True)
        first_token_text = (f"{(first_token-start)*1000:.0f}"
                            if first_token is not None else "NA")
        first_audio_text = (f"{(first_audio-start)*1000:.0f}"
                            if first_audio is not None else "NA")
        record = (
            f"{datetime.now().isoformat(timespec='seconds')} "
            f"model={model} voice={voice} stt_ms={stt_ms:.0f} "
            f"first_token_ms={first_token_text} "
            f"first_audio_ms={first_audio_text} "
            f"total_ms={(end-start)*1000:.0f}\n"
        )
        with (directory / "performance.log").open("a", encoding="utf-8") as out:
            out.write(record)
    except OSError:
        pass
