"""Validando vozes corretas para ensino de inglês."""
import tempfile
import json
import unittest
from pathlib import Path

from iaexpert.audio import VoiceOutput, VOICE_EN_NAME
from iaexpert.config import Settings
from iaexpert.voice import ChatterboxVoice, choose_voice


class EnglishConfigurationTests(unittest.TestCase):
    def test_tutor_is_default_a1(self):
        self.assertEqual(Settings().learning_mode, "english_tutor")
        self.assertEqual(Settings().english_level, "A1")

    def test_piper_uses_english_voice_when_teaching(self):
        voice = choose_voice(Settings(voice_engine="piper"))
        self.assertIsInstance(voice, VoiceOutput)
        self.assertEqual(voice.voice_name, VOICE_EN_NAME)

    def test_chatterbox_uses_english_language(self):
        voice = choose_voice(Settings(voice_engine="chatterbox"))
        self.assertIsInstance(voice, ChatterboxVoice)
        self.assertEqual(voice.language, "en")

    def test_legacy_ptbr_voice_migrates_once_to_english(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "settings.json").write_text(
                json.dumps({"voice_engine": "edge", "voice_name": "pt-BR-FranciscaNeural"}),
                encoding="utf-8",
            )
            value = Settings.load(root)
            self.assertEqual(value.voice_name, "en-US-JennyNeural")

    def test_general_assistant_keeps_portuguese_voice(self):
        voice = choose_voice(Settings(learning_mode="assistant", voice_engine="piper"))
        self.assertEqual(voice.voice_name, "pt_BR-faber-medium")


if __name__ == "__main__":
    unittest.main()
