"""Preferências locais, incluindo consentimento explícito para TTS on-line."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


def data_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "IAExpert"
    return Path.home() / ".iaexpert"


@dataclass
class Settings:
    model: str = "qwen3.5:2b"
    ollama_url: str = "http://127.0.0.1:11434"
    whisper_model: str = "tiny"
    auto_continue: bool = True
    speak_answers: bool = True
    microphone_threshold: float = 0.008
    microphone_device: int | None = None

    # "ask" evita envio on-line antes da aprovação informada do usuário.
    voice_engine: str = "ask"
    voice_name: str = "pt-BR-FranciscaNeural"
    performance_log: bool = True

    @classmethod
    def load(cls, directory: Path | None = None) -> "Settings":
        path = (directory or data_directory()) / "settings.json"
        if not path.is_file():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return cls()
            allowed = set(cls.__dataclass_fields__)
            data = {k: v for k, v in raw.items() if k in allowed}
            for key in ("model", "ollama_url", "whisper_model", "voice_name"):
                if key in data and not isinstance(data[key], str):
                    raise ValueError(f"{key} inválido")
            if data.get("voice_engine", "ask") not in {"ask", "edge", "piper"}:
                raise ValueError("voice_engine inválido")
            if data.get("voice_name", "pt-BR-FranciscaNeural") not in {
                "pt-BR-FranciscaNeural", "pt-BR-AntonioNeural",
            }:
                raise ValueError("voice_name inválido")
            if data.get("whisper_model", "tiny") not in {"tiny", "base", "small"}:
                raise ValueError("whisper_model inválido")
            for key in ("auto_continue", "speak_answers", "performance_log"):
                if key in data and not isinstance(data[key], bool):
                    raise ValueError(f"{key} inválido")
            if "microphone_threshold" in data:
                data["microphone_threshold"] = float(data["microphone_threshold"])
                if not 0.001 <= data["microphone_threshold"] <= 0.2:
                    raise ValueError("microphone_threshold inválido")
            if "microphone_device" in data:
                device = data["microphone_device"]
                if device is not None and (type(device) is not int or device < 0):
                    raise ValueError("microphone_device inválido")
            return cls(**data)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, directory: Path | None = None) -> None:
        root = directory or data_directory()
        root.mkdir(parents=True, exist_ok=True)
        target = root / "settings.json"
        temporary = root / "settings.json.tmp"
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
