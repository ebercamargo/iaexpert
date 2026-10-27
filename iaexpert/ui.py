"""Avatar de tela inteira: interação por voz, sem chat nem bordas."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QPointF, Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QRadialGradient, QLinearGradient, QPen, QAction
from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow, QMenu, QMessageBox, QWidget

from .config import Settings
from .history import ConversationHistory
from .worker import AssistantWorker


class AvatarCanvas(QWidget):
    """O rosto é o único elemento visual; controles por clique e menu de contexto."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.phase = 0.0
        self.mode = "idle"
        self.message = "Iniciando..."
        path = Path(__file__).resolve().parent.parent / "assets" / "avatar.webp"
        self.avatar = QPixmap(str(path))
        self.setCursor(Qt.PointingHandCursor)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.animate)
        self.tick.start(45)

    def animate(self) -> None:
        self.phase += 0.06
        self.update()

    def set_status(self, message: str) -> None:
        self.message = message
        status = message.lower()
        if "ouvindo" in status:
            self.mode = "listening"
        elif "pensando" in status or "reconhecendo" in status:
            self.mode = "thinking"
        elif "falando" in status:
            self.mode = "speaking"
        elif "interromp" in status:
            self.mode = "stopping"
        else:
            self.mode = "idle"
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor("#040911"))

        center = QPointF(w / 2, h * 0.48)
        halo = QRadialGradient(center, min(w, h) * 0.71)
        halo.setColorAt(0, QColor(27, 95, 151, 85))
        halo.setColorAt(0.55, QColor(7, 36, 69, 52))
        halo.setColorAt(1, QColor(4, 9, 17, 0))
        painter.fillRect(self.rect(), halo)

        if not self.avatar.isNull():
            ratio = self.avatar.width() / max(self.avatar.height(), 1)
            face_h = min(h * 0.91, w / max(ratio, 0.01) * 0.92)
            breathing = 1 + 0.006 * math.sin(self.phase * 0.55)
            face_h *= breathing
            face_w = face_h * ratio
            top = h * 0.47 - face_h * 0.48
            rect = QRectF((w - face_w) / 2, top, face_w, face_h)
            painter.setOpacity(1.0)
            painter.drawPixmap(rect, self.avatar, QRectF(self.avatar.rect()))
        else:
            painter.setPen(QColor("#63d3eb"))
            painter.setFont(QFont("Segoe UI", 16))
            painter.drawText(self.rect(), Qt.AlignCenter, "Imagem do avatar não encontrada")

        color = QColor("#55e0eb")
        if self.mode == "speaking":
            color = QColor("#ae9cff")
        elif self.mode in ("idle", "stopping"):
            color = QColor("#7a8b9d")

        if self.mode in ("listening", "thinking", "speaking"):
            alpha = 85 + int(75 * (0.5 + 0.5 * math.sin(self.phase * 2.3)))
            color.setAlpha(alpha)
            painter.setPen(QPen(color, 2))
            # Indicador de atividade discreto, sem moldura ou painel.
            y = h * 0.935
            for i in range(15):
                x = w / 2 + (i - 7) * 10
                bar = (4 + 16 * abs(math.sin(self.phase * 2 + i * 0.66)))
                painter.drawLine(QPointF(x, y - bar / 2), QPointF(x, y + bar / 2))

        painter.setPen(QColor("#a7dbea"))
        painter.setFont(QFont("Segoe UI", max(10, min(16, int(h * 0.018)))))
        painter.drawText(QRectF(0, h - 48, w, 22), Qt.AlignCenter, self.message)
        painter.end()


class IAExpertWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        # Migração para modelo mais leve; o usuário pode voltar ao 4B pelo menu.
        if self.settings.model == "qwen3.5:4b":
            self.settings.model = "qwen3.5:2b"
            self.settings.save()
        self.history = ConversationHistory()
        self.worker: AssistantWorker | None = None
        self.pending_close = False

        self.setWindowTitle("IAExpert — Assistente de Voz")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.canvas = AvatarCanvas(self)
        self.setCentralWidget(self.canvas)
        self.canvas.setToolTip(
            "Clique: pausar/retomar a escuta. Botão direito: configurações. Esc: sair."
        )
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._menu)
        self.canvas.mouseReleaseEvent = self._face_clicked
        self.showMaximized()
        QTimer.singleShot(600, self._start)

    def _face_clicked(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle_listening()

    def _start(self) -> None:
        if self.worker is not None or self.pending_close:
            return
        self.canvas.set_status("Preparando microfone...")
        worker = AssistantWorker(replace(self.settings), self.history)
        worker.state_changed.connect(self.canvas.set_status)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self.worker = worker
        worker.start()

    def _toggle_listening(self) -> None:
        if self.worker is None:
            self._start()
        else:
            self.canvas.set_status("Interrompendo...")
            self.worker.cancel()

    def _finished(self) -> None:
        self.worker = None
        if self.pending_close:
            QTimer.singleShot(0, self.close)
        else:
            self.canvas.set_status("Pausado — clique no rosto para ouvir")

    def _failed(self, message: str) -> None:
        self.canvas.set_status("Erro no áudio")
        QMessageBox.warning(self, "IAExpert — problema na conversa", message)

    def _menu(self, point) -> None:
        menu = QMenu(self)
        toggle = menu.addAction("Pausar escuta" if self.worker else "Voltar a ouvir")
        microphone = menu.addAction("Escolher microfone...")
        model = menu.addAction("Escolher modelo de IA...")
        voice = menu.addAction(
            "Desativar voz" if self.settings.speak_answers else "Ativar voz"
        )
        clear = menu.addAction("Apagar histórico local")
        menu.addSeparator()
        fullscreen = menu.addAction("Alternar tela inteira (F11)")
        leave = menu.addAction("Sair (Esc)")
        chosen = menu.exec(self.canvas.mapToGlobal(point))
        if chosen == toggle:
            self._toggle_listening()
        elif chosen == microphone:
            self._microphone_settings()
        elif chosen == model:
            self._model_settings()
        elif chosen == voice:
            self.settings.speak_answers = not self.settings.speak_answers
            self.settings.save()
            self._restart_if_active()
        elif chosen == clear:
            if QMessageBox.question(self, "Apagar conversa", "Apagar o histórico salvo neste PC?") == QMessageBox.Yes:
                self.history.clear()
        elif chosen == fullscreen:
            self._toggle_fullscreen()
        elif chosen == leave:
            self.close()

    def _microphone_settings(self) -> None:
        devices = [(None, "Padrão do Windows")]
        try:
            devices.extend(
                (idx, f"{dev['name']} [{idx}]")
                for idx, dev in enumerate(sd.query_devices())
                if dev["max_input_channels"] > 0
            )
        except Exception as exc:
            QMessageBox.warning(self, "Microfone", str(exc))
            return
        names = [label for _, label in devices]
        current = next((i for i, (id_, _) in enumerate(devices)
                        if id_ == self.settings.microphone_device), 0)
        selection, ok = QInputDialog.getItem(
            self, "Microfone", "Dispositivo de entrada", names, current, False
        )
        if ok:
            self.settings.microphone_device = devices[names.index(selection)][0]
            self.settings.save()
            self._restart_if_active()

    def _model_settings(self) -> None:
        names = ["qwen3.5:2b", "qwen3.5:4b", "qwen3.5:9b"]
        selection, ok = QInputDialog.getItem(
            self, "Modelo local", "Modelo instalado no Ollama",
            names, names.index(self.settings.model) if self.settings.model in names else 0, True
        )
        if ok and selection.strip():
            self.settings.model = selection.strip()
            self.settings.save()
            self._restart_if_active()

    def _restart_if_active(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.canvas.set_status(
                "Configuração salva. Clique no rosto para retomar após parar."
            )

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Space:
            self._toggle_listening()
        elif event.key() == Qt.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key_M and event.modifiers() & Qt.ControlModifier:
            self._microphone_settings()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            event.ignore()
            self.pending_close = True
            self.worker.cancel()
            self.canvas.set_status("Encerrando...")
        else:
            event.accept()


def main() -> None:
    app = QApplication([])
    app.setApplicationName("IAExpert")
    window = IAExpertWindow()
    window.show()
    app.exec()
