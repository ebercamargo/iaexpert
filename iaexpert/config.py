"""Configuração local sem segredos nem telemetria."""

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
    model: str = "qwen3.5:4b"
    ollama_url: str = "http://127.0.0.1:11434"
    whisper_model: str = "base"
    auto_continue: bool = False
    speak_answers: bool = True
    microphone_threshold: float = 0.014

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
            if not isinstance(data.get("model", "qwen3.5:4b"), str):
                raise ValueError("modelo inválido")
            if not isinstance(data.get("ollama_url", "http://127.0.0.1:11434"), str):
                raise ValueError("URL inválida")
            for name in ("auto_continue", "speak_answers"):
                if name in data and not isinstance(data[name], bool):
                    raise ValueError(name)
            if "microphone_threshold" in data:
                value = float(data["microphone_threshold"])
                if not 0.001 <= value <= 0.2:
                    raise ValueError("limiar inválido")
                data["microphone_threshold"] = value
            return cls(**data)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, directory: Path | None = None) -> None:
        root = directory or data_directory()
        root.mkdir(parents=True, exist_ok=True)
        target = root / "settings.json"
        temp = root / "settings.json.tmp"
        temp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(target)
