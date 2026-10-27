"""Histórico de conversa armazenado somente no computador."""

from __future__ import annotations

import json
from pathlib import Path

from .config import data_directory


class ConversationHistory:
    MAX_MESSAGES = 80

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or data_directory()
        self.path = self.directory / "conversation.json"
        self.messages: list[dict[str, str]] = []
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return
            self.messages = [
                {"role": item["role"], "content": item["content"]}
                for item in data
                if isinstance(item, dict)
                and item.get("role") in {"user", "assistant"}
                and isinstance(item.get("content"), str)
                and item["content"].strip()
            ][-self.MAX_MESSAGES :]
        except (OSError, ValueError, TypeError, KeyError):
            self.messages = []

    def add_turn(self, user_text: str, answer: str) -> None:
        if not user_text.strip() or not answer.strip():
            return
        self.messages.extend(
            [
                {"role": "user", "content": user_text.strip()},
                {"role": "assistant", "content": answer.strip()},
            ]
        )
        self.messages = self.messages[-self.MAX_MESSAGES :]
        self._save()

    def clear(self) -> None:
        self.messages = []
        self._save()

    def _save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / "conversation.json.tmp"
        temporary.write_text(
            json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)
