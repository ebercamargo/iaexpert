"""Limpeza de texto e emissão incremental de frases para o sintetizador."""

from __future__ import annotations

import re


def spoken_text(text: str) -> str:
    """Remove marcações para não falar 'asterisco' ou 'hashtag'."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+•]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = re.sub(r"[#*_~]", "", text).replace(chr(96), "")
    text = re.sub(r"[\r\n]+", ". ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return text.strip(" ,;:-")


class SentenceBuffer:
    """Emite frases assim que o LLM as produz, sem esperar toda a resposta."""

    def __init__(self, max_chars: int = 165):
        self.buffer = ""
        self.max_chars = max_chars

    def feed(self, token: str) -> list[str]:
        self.buffer += token
        ready: list[str] = []
        while True:
            match = next((item for item in re.finditer(r"(?<=[.!?])\s+", self.buffer)
                          if item.end() >= 16), None)
            if match:
                ready.append(self.buffer[:match.start() + 1])
                self.buffer = self.buffer[match.end():]
                continue
            if len(self.buffer) >= self.max_chars:
                index = self.buffer.rfind(" ", 40, self.max_chars)
                if index > 0:
                    ready.append(self.buffer[:index])
                    self.buffer = self.buffer[index + 1:]
                    continue
            break
        return [part for part in (spoken_text(segment) for segment in ready) if part]

    def finish(self) -> str:
        remaining = spoken_text(self.buffer)
        self.buffer = ""
        return remaining
