"""Interface gráfica PySide6: conversa, animação e controle por voz."""

from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import Settings
from .history import ConversationHistory
from .worker import AssistantWorker


STYLE = """
QMainWindow, QWidget#root { background: #090d17; color: #eaf3ff; }
QFrame#panel { background: #111929; border: 1px solid #26354a; border-radius: 19px; }
QLabel { color: #eaf3ff; background: transparent; }
QLabel#muted { color: #98adc4; }
QPushButton { color: white; background: #24364e; border: 1px solid #36516c;
              border-radius: 11px; padding: 11px 16px; font-weight: 600; }
QPushButton:hover { background: #2b4867; }
QPushButton:disabled { color: #7d8da0; background: #182435; }
QPushButton#primary { background: #007f9a; border: 1px solid #4de7e4; }
QPushButton#primary:hover { background: #009eb9; }
QLineEdit, QComboBox { color: #eaf3ff; background: #0c1422; border: 1px solid #31465f;
                       border-radius: 9px; padding: 10px; selection-background-color: #227f99; }
QComboBox QAbstractItemView { color: #eaf3ff; background: #162337; }
QCheckBox { color: #c5d5e8; spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #121b2a; width: 8px; }
QScrollBar::handle:vertical { background: #3a526d; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class NeuralOrb(QWidget):
    """Indicador visual vetorial, sem imagem proprietária ou uso de webcam."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(270)
        self.phase = 0.0
        self.mode = "idle"
        timer = QTimer(self)
        timer.timeout.connect(self._animate)
        timer.start(45)
        self.timer = timer

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def _animate(self) -> None:
        self.phase += 0.045 if self.mode == "idle" else 0.11
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        c = QPointF(self.width() / 2, self.height() / 2)
        size = min(self.width(), self.height())
        radius = size * 0.29
        active = self.mode in ("listening", "thinking", "speaking")
        accent = QColor("#53e3f0") if self.mode != "speaking" else QColor("#aa8dff")

        painter.setBrush(Qt.NoBrush)
        for i in range(3):
            r = radius + 14 + i * 18 + (math.sin(self.phase + i) * 4 if active else 0)
            painter.setPen(QPen(QColor(76, 185, 211, 65 - i * 15), 1.3))
            painter.drawEllipse(c, r, r)

        for i in range(70):
            angle = i * math.tau / 70 + self.phase * 0.08
            r = radius + 43 + 5 * math.sin(self.phase + i * 0.3)
            x, y = c.x() + r * math.cos(angle), c.y() + r * math.sin(angle)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(89, 213, 233, 75 + (i % 4) * 25))
            painter.drawEllipse(QPointF(x, y), 1.5, 1.5)

        gradient = QRadialGradient(c - QPointF(radius * 0.23, radius * 0.25), radius * 1.6)
        gradient.setColorAt(0, QColor("#3e9ec2"))
        gradient.setColorAt(0.35, QColor("#143c64"))
        gradient.setColorAt(0.75, QColor("#0b1b34"))
        gradient.setColorAt(1, QColor("#09111d"))
        painter.setPen(QPen(accent, 2.5))
        painter.setBrush(gradient)
        painter.drawEllipse(c, radius, radius)

        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        amplitude = (18 if active else 7) + (3 * math.sin(self.phase))
        count = 95
        for i in range(count):
            x = c.x() - radius * 0.75 + i * radius * 1.5 / (count - 1)
            envelope = math.sin(math.pi * i / (count - 1)) ** 2
            y = c.y() + amplitude * envelope * math.sin(i * 0.65 - self.phase * 3)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.setPen(QPen(accent, 2.3))
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#e0fcff"))
        painter.drawEllipse(c, 5, 5)
        painter.end()


class IAExpertWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.history = ConversationHistory()
        self.worker: AssistantWorker | None = None
        self.pending_close = False
        self.current_answer: QLabel | None = None
        self.answer_text = ""

        self.setWindowTitle("IAExpert — Assistente de Voz")
        self.setMinimumSize(900, 620)
        self.resize(1110, 735)
        self.setStyleSheet(STYLE)
        self._build_interface()
        for message in self.history.messages:
            self._add_message(message["role"], message["content"])
        self._show_status("Pronto para conversar")

    def _build_interface(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 22, 24, 24)
        outer.setSpacing(18)

        heading = QHBoxLayout()
        titles = QVBoxLayout()
        brand = QLabel("◉  IAExpert")
        brand.setFont(QFont("Segoe UI", 23, QFont.Bold))
        subtitle = QLabel("Seu assistente de voz • inteligência artificial local")
        subtitle.setObjectName("muted")
        titles.addWidget(brand)
        titles.addWidget(subtitle)
        heading.addLayout(titles)
        heading.addStretch()
        tag = QLabel("●  EXECUÇÃO LOCAL")
        tag.setStyleSheet("color: #5fdbc5; padding: 12px; font-weight: bold;")
        heading.addWidget(tag)
        outer.addLayout(heading)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        outer.addLayout(columns, stretch=1)

        side = QFrame()
        side.setObjectName("panel")
        side.setFixedWidth(335)
        sidebox = QVBoxLayout(side)
        sidebox.setContentsMargins(20, 22, 20, 23)
        sidebox.setSpacing(13)

        smalltitle = QLabel("ASSISTENTE ATIVO")
        smalltitle.setObjectName("muted")
        smalltitle.setAlignment(Qt.AlignCenter)
        sidebox.addWidget(smalltitle)
        self.orb = NeuralOrb()
        sidebox.addWidget(self.orb)
        self.state_label = QLabel("")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setWordWrap(True)
        self.state_label.setMinimumHeight(35)
        sidebox.addWidget(self.state_label)

        self.microphone_button = QPushButton("🎙  Iniciar conversa")
        self.microphone_button.setObjectName("primary")
        self.microphone_button.clicked.connect(self._toggle_microphone)
        sidebox.addWidget(self.microphone_button)

        self.continue_check = QCheckBox("Conversa contínua (mãos livres)")
        self.continue_check.setChecked(self.settings.auto_continue)
        self.continue_check.toggled.connect(self._save_preferences)
        sidebox.addWidget(self.continue_check)

        self.voice_check = QCheckBox("Responder falando (voz PT-BR)")
        self.voice_check.setChecked(self.settings.speak_answers)
        self.voice_check.toggled.connect(self._save_preferences)
        sidebox.addWidget(self.voice_check)

        model_label = QLabel("Modelo de IA (Ollama)")
        model_label.setObjectName("muted")
        sidebox.addWidget(model_label)
        self.models = QComboBox()
        self.models.setEditable(True)
        for model in ("qwen3.5:4b", "qwen3.5:2b", "qwen3.5:9b"):
            self.models.addItem(model)
        self.models.setCurrentText(self.settings.model)
        self.models.lineEdit().editingFinished.connect(self._save_preferences)
        self.models.currentIndexChanged.connect(self._save_preferences)
        sidebox.addWidget(self.models)

        note = QLabel(
            "Seu microfone e suas conversas são processados neste PC. "
            "Na primeira utilização, os modelos de áudio serão baixados."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        note.setStyleSheet("color: #91a9bf; font-size: 11px;")
        sidebox.addStretch()
        sidebox.addWidget(note)
        columns.addWidget(side)

        conversation = QFrame()
        conversation.setObjectName("panel")
        content = QVBoxLayout(conversation)
        content.setContentsMargins(21, 20, 21, 20)
        content.setSpacing(15)
        chat_header = QHBoxLayout()
        chat_title = QLabel("Conversa")
        chat_title.setFont(QFont("Segoe UI", 17, QFont.DemiBold))
        chat_header.addWidget(chat_title)
        chat_header.addStretch()
        clear = QPushButton("Limpar histórico")
        clear.clicked.connect(self._clear_history)
        self.clear_button = clear
        chat_header.addWidget(clear)
        content.addLayout(chat_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll = scroll
        messages_widget = QWidget()
        messages_widget.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(messages_widget)
        self.messages_layout.setContentsMargins(0, 6, 0, 12)
        self.messages_layout.setSpacing(15)
        self.messages_layout.addStretch()
        scroll.setWidget(messages_widget)
        content.addWidget(scroll, stretch=1)

        entry = QHBoxLayout()
        self.message_entry = QLineEdit()
        self.message_entry.setPlaceholderText("Digite uma pergunta ou use o microfone...")
        self.message_entry.returnPressed.connect(self._send_text)
        entry.addWidget(self.message_entry, stretch=1)
        self.send_button = QPushButton("Enviar")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self._send_text)
        entry.addWidget(self.send_button)
        content.addLayout(entry)
        columns.addWidget(conversation, stretch=1)

    def _save_preferences(self, *_args) -> None:
        self.settings.model = self.models.currentText().strip() or "qwen3.5:4b"
        self.settings.auto_continue = self.continue_check.isChecked()
        self.settings.speak_answers = self.voice_check.isChecked()
        try:
            self.settings.save()
        except OSError as exc:
            self._show_status(f"Erro ao salvar configuração: {exc}")

    def _add_message(self, role: str, content: str) -> QLabel:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 0, 4, 0)
        if role == "user":
            layout.addStretch()

        bubble = QFrame()
        bubble.setMaximumWidth(600)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        color = "#183c56" if role == "user" else "#19263b"
        bubble.setStyleSheet(
            f"QFrame {{ background: {color}; border: 1px solid #344761; "
            "border-radius: 13px; }}"
            "QLabel { background: transparent; border: none; }"
        )
        box = QVBoxLayout(bubble)
        box.setContentsMargins(15, 12, 15, 12)
        who = QLabel("VOCÊ" if role == "user" else "IAEXPERT")
        who.setStyleSheet("color: #78dfe8; font-size: 10px; font-weight: bold;")
        box.addWidget(who)
        message = QLabel(content)
        message.setTextFormat(Qt.PlainText)
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        message.setStyleSheet("color: #e5edf7; font-size: 13px;")
        box.addWidget(message)
        layout.addWidget(bubble, stretch=0)
        if role != "user":
            layout.addStretch()

        index = self.messages_layout.count() - 1
        self.messages_layout.insertWidget(index, row)
        QTimer.singleShot(0, self._scroll_bottom)
        return message

    def _scroll_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _show_status(self, text: str) -> None:
        self.state_label.setText(text)
        lowercase = text.lower()
        mode = "idle"
        if "ouvindo" in lowercase:
            mode = "listening"
        elif "pensando" in lowercase or "transcrevendo" in lowercase:
            mode = "thinking"
        elif "falando" in lowercase:
            mode = "speaking"
        self.orb.set_mode(mode)

    def _read_preferences(self) -> Settings:
        self._save_preferences()
        return replace(self.settings)

    def _start_worker(self, text: str | None) -> None:
        if self.worker is not None:
            return
        prefs = self._read_preferences()
        if not prefs.model:
            self._show_status("Informe um modelo do Ollama.")
            return
        worker = AssistantWorker(prefs, self.history, typed_text=text)
        worker.state_changed.connect(self._show_status)
        worker.question_ready.connect(lambda q: self._add_message("user", q))
        worker.answer_started.connect(self._answer_started)
        worker.answer_delta.connect(self._answer_delta)
        worker.answer_finished.connect(self._answer_finished)
        worker.failed.connect(self._handle_failure)
        worker.finished.connect(self._worker_finished)
        self.worker = worker
        self.microphone_button.setText("■  Interromper")
        self.send_button.setEnabled(False)
        self.message_entry.setEnabled(False)
        self.models.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.continue_check.setEnabled(False)
        self.voice_check.setEnabled(False)
        worker.start()

    def _toggle_microphone(self) -> None:
        if self.worker is not None:
            self._show_status("Interrompendo...")
            self.worker.cancel()
        else:
            self._start_worker(None)

    def _send_text(self) -> None:
        text = self.message_entry.text().strip()
        if not text or self.worker is not None:
            return
        self._add_message("user", text)
        self.message_entry.clear()
        self._start_worker(text)

    def _answer_started(self) -> None:
        self.answer_text = ""
        self.current_answer = self._add_message("assistant", "…")

    def _answer_delta(self, text: str) -> None:
        if self.current_answer is not None:
            self.answer_text += text
            self.current_answer.setText(self.answer_text)
            QTimer.singleShot(0, self._scroll_bottom)

    def _answer_finished(self, answer: str) -> None:
        if self.current_answer is not None:
            self.current_answer.setText(answer)
        self.current_answer = None
        self.answer_text = ""

    def _handle_failure(self, message: str) -> None:
        self._show_status("Falha na operação")
        QMessageBox.warning(self, "IAExpert", message)

    def _worker_finished(self) -> None:
        self.worker = None
        self.microphone_button.setText("🎙  Iniciar conversa")
        self.send_button.setEnabled(True)
        self.message_entry.setEnabled(True)
        self.models.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.continue_check.setEnabled(True)
        self.voice_check.setEnabled(True)
        if self.current_answer is not None:
            self.current_answer.setText(self.answer_text or "(resposta interrompida)")
            self.current_answer = None
        self._show_status("Pronto para conversar")
        self.message_entry.setFocus()
        if self.pending_close:
            QTimer.singleShot(0, self.close)

    def _clear_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Limpar conversa",
            "Deseja apagar permanentemente a conversa salva neste computador?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.history.clear()
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            event.ignore()
            self.pending_close = True
            self.worker.cancel()
            self._show_status("Encerrando...")
            return
        event.accept()


def main() -> None:
    app = QApplication([])
    app.setApplicationName("IAExpert")
    window = IAExpertWindow()
    window.show()
    app.exec()
