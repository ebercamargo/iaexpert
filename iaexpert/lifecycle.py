"""Recebe Ctrl+C no terminal sem injetar KeyboardInterrupt na thread Qt.

Qt processa sinais enquanto seus slots e paintEvent estão rodando.
O handler Python APENAS sinaliza uma variável. Um QTimer no thread
principal faz o pedido de fechamento entre eventos, sem reentrância.
"""
from __future__ import annotations

import signal
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


class ConsoleShutdown(QObject):
    def __init__(self, close_window: Callable[[], None], parent: QObject | None = None):
        super().__init__(parent)
        self._close_window = close_window
        self._pending = False
        self._handled = False
        self._previous: dict[signal.Signals, object] = {}
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self.poll)

    def install(self) -> None:
        """Chamar na thread principal, depois de criar QApplication."""
        for name in ("SIGINT", "SIGBREAK"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            self._previous[sig] = signal.getsignal(sig)
            signal.signal(sig, self._on_interrupt)
        # Mantém o event loop do Qt retornando periodicamente ao Python.
        self._poll_timer.start()

    def _on_interrupt(self, _signum: int, _frame: object) -> None:
        # Não acessar widgets aqui: pode chegar no meio de _tick/paintEvent.
        self._pending = True

    def poll(self) -> None:
        if not self._pending or self._handled:
            return
        self._pending = False
        self._handled = True
        self._poll_timer.stop()
        self._close_window()

    def uninstall(self) -> None:
        self._poll_timer.stop()
        for sig, old_handler in self._previous.items():
            signal.signal(sig, old_handler)
        self._previous.clear()
