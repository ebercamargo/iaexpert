"""Testes unitários da leitura de texto por voz."""

import tempfile
import unittest
from pathlib import Path

from iaexpert.config import Settings
from iaexpert.speech import SentenceBuffer, spoken_text


class SpeechTests(unittest.TestCase):
    def test_strips_markdown(self):
        text = "**Olá**, *tudo bem*? #Título e __exemplo__"
        self.assertEqual(spoken_text(text), "Olá, tudo bem? Título e exemplo")

    def test_intonation_punctuation(self):
        self.assertEqual(spoken_text("Como você está?"), "Como você está?")
        self.assertEqual(spoken_text("Que ótimo!"), "Que ótimo!")

    def test_bullets_and_links(self):
        self.assertNotIn("*", spoken_text("1. **Olá**\n- *Tudo* bem?"))
        self.assertEqual(spoken_text("[site](https://example.com)"), "site")

    def test_incremental_speech(self):
        buffer = SentenceBuffer()
        self.assertEqual(buffer.feed("Olá! Como vai você hoje? "), ["Olá! Como vai você hoje?"])
        self.assertEqual(buffer.feed("Estou aqui para ajudar. "), ["Estou aqui para ajudar."])
        self.assertEqual(buffer.finish(), "")

    def test_long_phrase(self):
        buffer = SentenceBuffer(max_chars=75)
        parts = buffer.feed("Esta é uma explicação um pouco longa que deve começar a falar antes da geração completa terminar.")
        self.assertTrue(parts)
        self.assertTrue(buffer.finish())

    def test_microphone_prefs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Settings(microphone_device=4).save(root)
            self.assertEqual(Settings.load(root).microphone_device, 4)


if __name__ == "__main__":
    unittest.main()
