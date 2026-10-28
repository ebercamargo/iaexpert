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
