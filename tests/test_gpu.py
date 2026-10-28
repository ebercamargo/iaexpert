"""Seleção de GPU com fallback seguro sem GPU física."""
import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from iaexpert.audio import SpeechToText
from iaexpert.config import Settings
from iaexpert.voice import ChatterboxVoice, choose_voice


class GpuTests(unittest.TestCase):
    def test_defaults_to_auto(self):
        self.assertEqual(Settings().stt_device, "auto")

    def test_gpu_voice_opt_in(self):
        self.assertIsInstance(choose_voice(
            Settings(voice_engine="chatterbox")), ChatterboxVoice)

    def test_stt_automatic_cpu_fallback(self):
        model = MagicMock()
        model.transcribe.return_value = (iter([MagicMock(text="olá")]), None)
        with patch.dict(sys.modules, {
            "faster_whisper": MagicMock(WhisperModel=MagicMock(return_value=model)),
            "ctranslate2": MagicMock(
                get_supported_compute_types=MagicMock(side_effect=RuntimeError("no CUDA"))
            )
        }):
            stt = SpeechToText(Settings(stt_device="auto", whisper_model="tiny"))
            self.assertEqual(stt.transcribe(np.zeros(16000, np.float32)), "olá")
            self.assertEqual(stt.device, "cpu")


if __name__ == "__main__":
    unittest.main()
