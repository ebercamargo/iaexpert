"""Testes de persistência isolados do áudio, interface e Ollama."""

import json
import tempfile
import unittest
from pathlib import Path

from iaexpert.config import Settings
from iaexpert.history import ConversationHistory


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                model="qwen3.5:2b",
                auto_continue=True,
                microphone_threshold=0.03,
            )
            settings.save(root)
            loaded = Settings.load(root)
            self.assertEqual(loaded, settings)

    def test_invalid_threshold_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "settings.json").write_text(
                json.dumps({"microphone_threshold": 999}), encoding="utf-8"
            )
            self.assertEqual(Settings.load(root).microphone_threshold, 0.008)


class HistoryTests(unittest.TestCase):
    def test_persists_and_clears(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = ConversationHistory(root)
            history.add_turn("Olá", "Oi! Como posso ajudar?")
            self.assertEqual(len(ConversationHistory(root).messages), 2)
            history.clear()
            self.assertEqual(ConversationHistory(root).messages, [])

    def test_keeps_last_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            history = ConversationHistory(Path(directory))
            for index in range(48):
                history.add_turn(str(index), "ok")
            self.assertEqual(len(history.messages), 80)
            self.assertEqual(history.messages[0]["content"], "8")

    def test_rejects_corrupt_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "conversation.json").write_text("{broken", encoding="utf-8")
            self.assertEqual(ConversationHistory(root).messages, [])


if __name__ == "__main__":
    unittest.main()
