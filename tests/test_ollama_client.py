"""Ollama simulado: nenhum servidor externo é necessário para testar."""

import json
import unittest
from unittest.mock import patch

from iaexpert.config import Settings
from iaexpert.ollama_client import Cancelled, OllamaClient, OllamaError


class FakeResponse:
    def __init__(self, events):
        self.events = [
            json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n"
            for event in events
        ]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self.events)


class OllamaTests(unittest.TestCase):
    def test_stream_and_context(self):
        data = [
            {"message": {"content": "Olá, "}, "done": False},
            {"message": {"content": "mundo!"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        fragments = []
        with patch(
            "iaexpert.ollama_client.request.urlopen", return_value=FakeResponse(data)
        ) as mock:
            result = OllamaClient(Settings()).chat(
                "Como vai?", [{"role": "user", "content": "Olá"}], fragments.append
            )
        self.assertEqual(result, "Olá, mundo!")
        self.assertEqual(fragments, ["Olá, ", "mundo!"])
        payload = json.loads(mock.call_args.args[0].data)
        self.assertEqual(payload["messages"][-1]["content"], "Como vai?")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertFalse(payload["think"])

    def test_early_cancel_skips_request(self):
        with self.assertRaises(Cancelled):
            OllamaClient(Settings()).chat("teste", [], lambda _: None, lambda: True)

    def test_server_error(self):
        with patch(
            "iaexpert.ollama_client.request.urlopen",
            return_value=FakeResponse([{"error": "servidor indisponível"}]),
        ):
            with self.assertRaises(OllamaError):
                OllamaClient(Settings()).chat("teste", [], lambda _: None)


if __name__ == "__main__":
    unittest.main()
