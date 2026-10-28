"""Verifica pré-carregamento Ollama e registro sem conteúdo de conversas."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from iaexpert.config import Settings
from iaexpert.ollama_client import OllamaClient
from iaexpert.performance import log_turn


class PerformanceTests(unittest.TestCase):
    def test_preload_no_conversation_sent(self):
        with patch("iaexpert.ollama_client.request.urlopen") as open_url:
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b""
            open_url.return_value = response
            OllamaClient(Settings()).preload()
            req = open_url.call_args.args[0]
            import json
            payload = json.loads(req.data)
            self.assertEqual(payload["model"], "qwen3.5:2b")
            self.assertNotIn("messages", payload)
            self.assertNotIn("prompt", payload)

    def test_performance_log_no_text(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("iaexpert.performance.data_directory", return_value=Path(root)):
                log_turn("qwen3.5:2b", "piper", 40., 100., 100.1, 100.2, 100.4)
            contents = (Path(root) / "performance.log").read_text(encoding="utf-8")
            self.assertIn("first_audio_ms=200", contents)
            self.assertNotIn("messages", contents)


if __name__ == "__main__":
    unittest.main()
