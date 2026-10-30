"""Ctrl+C deve fechar via loop Qt, nunca lançar KeyboardInterrupt em _tick."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import signal
import unittest
from unittest.mock import Mock

from PySide6.QtWidgets import QApplication

from iaexpert.lifecycle import ConsoleShutdown


class GracefulShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_interrupt_is_handled_between_qt_events(self):
        close = Mock()
        bridge = ConsoleShutdown(close)
        try:
            bridge.install()
            bridge._on_interrupt(signal.SIGINT, None)
            close.assert_not_called()
            bridge.poll()
            close.assert_called_once_with()
            bridge.poll()
            close.assert_called_once_with()
        finally:
            bridge.uninstall()

    def test_restores_previous_python_handler(self):
        original = signal.getsignal(signal.SIGINT)
        bridge = ConsoleShutdown(lambda: None)
        try:
            bridge.install()
            self.assertNotEqual(signal.getsignal(signal.SIGINT), original)
        finally:
            bridge.uninstall()
        self.assertEqual(signal.getsignal(signal.SIGINT), original)

    def test_no_close_when_no_signal_received(self):
        close = Mock()
        bridge = ConsoleShutdown(close)
        try:
            bridge.install()
            bridge.poll()
            close.assert_not_called()
        finally:
            bridge.uninstall()


if __name__ == "__main__":
    unittest.main()
