"""Testes da seleção de voz, consentimento e persistência, sem acesso à rede."""
import json
import tempfile
import unittest
from pathlib import Path

from iaexpert.config import Settings
from iaexpert.voice import NaturalVoice, choose_voice


class VoiceSettingsTests(unittest.TestCase):
    def test_voice_never_online_without_consent(self):
        self.assertEqual(Settings().voice_engine, "ask")
        with self.assertRaises(ValueError):
            choose_voice(Settings())

    def test_piper_offline_is_available(self):
        from iaexpert.audio import VoiceOutput
        self.assertIsInstance(choose_voice(Settings(voice_engine="piper")), VoiceOutput)

    def test_online_voice_can_be_explicitly_enabled(self):
        voice = choose_voice(Settings(voice_engine="edge"))
        self.assertIsInstance(voice, NaturalVoice)
        self.assertEqual(voice.voice_name, "pt-BR-FranciscaNeural")

    def test_preferences_persist(self):
        with tempfile.TemporaryDirectory() as root:
            settings = Settings(voice_engine="edge", voice_name="pt-BR-AntonioNeural",
                                whisper_model="tiny")
            settings.save(Path(root))
            self.assertEqual(Settings.load(Path(root)), settings)

    def test_invalid_voice_engine_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "settings.json").write_text(
                json.dumps({"voice_engine": "unapproved"}), encoding="utf-8")
            self.assertEqual(Settings.load(Path(root)).voice_engine, "ask")


if __name__ == "__main__":
    unittest.main()
