"""O avatar usa canal alfa e imagens de boca diferentes em vários quadros."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from iaexpert.avatar import FacialFrames
from iaexpert.ui import IAExpertWindow


class AvatarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_frames_are_different_and_transparent(self):
        asset_dir = Path(__file__).resolve().parents[1] / "assets"
        avatar = FacialFrames(asset_dir)
        self.assertEqual(len(avatar.frames), 13)
        self.assertGreaterEqual(avatar.width, 700)
        self.assertGreaterEqual(avatar.height, 1000)
        self.assertTrue(avatar.frames[0].hasAlphaChannel())
        first = avatar.frames[0].toImage().pixelColor(0, 0).alpha()
        self.assertEqual(first, 0)
        self.assertNotEqual(
            avatar.frames[0].toImage(),
            avatar.frames[12].toImage(),
        )

    def test_blink_does_not_replace_mouth_frame(self):
        asset_dir = Path(__file__).resolve().parents[1] / "assets"
        avatar = FacialFrames(asset_dir)
        from PySide6.QtCore import QRect
        mouth = QRect(
            int(avatar.width * .43), int(avatar.height * .70),
            int(avatar.width * .14), int(avatar.height * .06)
        )
        normal = avatar.frame(.95, 0).toImage().copy(mouth)
        blinking = avatar.frame(.95, 1.0).toImage().copy(mouth)
        self.assertEqual(normal, blinking)

    def test_audio_levels_use_scheduled_dac_timestamp(self):
        import time
        from iaexpert.ui import FaceWidget

        widget = FaceWidget()
        widget.set_state("Falando...")
        due = time.monotonic() - .01
        widget.set_audio_level(.8, due)
        widget._tick()
        self.assertGreater(widget.level, .4)
        widget.set_state("Ouvindo...")
        widget._tick()
        self.assertEqual(widget.audio_level, 0)
        widget.timer.stop()
        widget.close()

    def test_window_has_real_transparency(self):
        window = IAExpertWindow()
        try:
            self.assertTrue(window.testAttribute(Qt.WA_TranslucentBackground))
            self.assertTrue(bool(window.windowFlags() & Qt.FramelessWindowHint))
            self.assertTrue(bool(window.windowFlags() & Qt.WindowStaysOnTopHint))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
