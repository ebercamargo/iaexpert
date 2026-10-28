"""Rosto flutuante com transparência real sobre as janelas do Windows."""
from __future__ import annotations

import math
import time
from dataclasses import replace

import sounddevice as sd
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow, QMenu, QMessageBox, QWidget

from .avatar import FacialFrames
from .config import Settings
from .history import ConversationHistory
from .worker import AssistantWorker
from pathlib import Path


class FaceWidget(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.frames = FacialFrames(Path(__file__).resolve().parent.parent / "assets")
        self.start_time = time.monotonic()
        self.audio_level = 0.
        self.level = .05
        self.mode = "idle"
        self.drag_origin = None
        self.window_origin = None
        self.next_blink = time.monotonic() + 3.
        self.blink_start = None
        self.setToolTip("Clique: pausar/escutar | Arrastar: mover | Botão direito: opções")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_state(self, text):
        text = text.lower()
        self.mode = ("speaking" if "falando" in text else
                     "listening" if "ouvindo" in text else
                     "thinking" if "pensando" in text or "reconhecendo" in text else "idle")
        if self.mode != "speaking":
            self.audio_level = 0.
        self.update()

    def set_audio_level(self, level):
        self.audio_level = max(0., min(1., float(level)))

    def _blink(self, now):
        if self.blink_start is None and now >= self.next_blink:
            self.blink_start = now
        if self.blink_start is None:
            return 0.
        phase = (now - self.blink_start)/.23
        if phase >= 1:
            self.blink_start = None
            self.next_blink = now + 2.6 + 2.4*abs(math.sin(now))
            return 0.
        return math.sin(math.pi * phase)**2

    def _tick(self):
        wanted = self.audio_level if self.mode == "speaking" else .05
        self.level += (wanted-self.level)*.45
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        t = time.monotonic()-self.start_time
        blink = self._blink(time.monotonic())
        openness = min(1.0, 0.10 + self.level * 1.1)
        if self.mode != "speaking":
            openness = 0.0
        img=self.frames.frame(openness, blink)
        w,h=self.width(),self.height()
        ratio=self.frames.width/self.frames.height
        draw_h=h-32
        draw_w=draw_h*ratio
        if draw_w > w-32:
            draw_w=w-32
            draw_h=draw_w/ratio
        painter.translate(QPointF(w/2,h/2))
        painter.rotate(0.55*math.sin(t*.67)+.18*math.sin(t*1.21))
        scale=1+.004*math.sin(t*1.4)
        painter.scale(scale,scale)
        painter.translate(QPointF(-w/2,-h/2))
        painter.drawPixmap(QRectF((w-draw_w)/2,(h-draw_h)/2,draw_w,draw_h),
                           img,QRectF(img.rect()))
        painter.end()

    def mousePressEvent(self,event):
        if event.button() == Qt.LeftButton:
            self.drag_origin=event.globalPosition().toPoint()
            self.window_origin=self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.drag_origin is not None:
            delta=event.globalPosition().toPoint()-self.drag_origin
            if delta.manhattanLength()>4:
                self.window().move(self.window_origin+delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button() == Qt.LeftButton and self.drag_origin is not None:
            delta=event.globalPosition().toPoint()-self.drag_origin
            if delta.manhattanLength()<7:
                self.clicked.emit()
            self.drag_origin=None
            self.window_origin=None
        super().mouseReleaseEvent(event)


class IAExpertWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=Settings.load()
        self.history=ConversationHistory()
        self.worker=None
        self.closing=False
        self.setWindowTitle("IAExpert — Avatar de Voz")
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground,True)
        self.face=FaceWidget(self)
        self.setCentralWidget(self.face)
        self.face.clicked.connect(self.toggle)
        self.face.setContextMenuPolicy(Qt.CustomContextMenu)
        self.face.customContextMenuRequested.connect(self._menu)
        bounds=QGuiApplication.primaryScreen().availableGeometry()
        height=min(620,max(340,int(bounds.height()*.63)))
        width=round(height*self.face.frames.width/self.face.frames.height)+32
        self.resize(width,height)
        self.move(bounds.right()-width-35,bounds.bottom()-height-20)
        QTimer.singleShot(350,self._start)

    def _start(self):
        if self.worker is not None or self.closing:
            return
        worker=AssistantWorker(replace(self.settings),self.history)
        worker.state_changed.connect(self.face.set_state)
        worker.level_changed.connect(self.face.set_audio_level)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self.worker=worker
        worker.start()

    def toggle(self):
        if self.worker is None:
            self._start()
        else:
            self.worker.cancel()
            self.face.set_state("Pausado")

    def _finished(self):
        self.worker=None
        self.face.set_state("Pausado")
        if self.closing:
            QTimer.singleShot(0,self.close)

    def _failed(self,error):
        QMessageBox.warning(self,"IAExpert",error)

    def _restart(self):
        self.settings.save()
        if self.worker is not None:
            self.worker.cancel()

    def _choose_mic(self):
        try:
            options=[(None,"Padrão do Windows")]
            options += [(i,f"{dev['name']} [{i}]") for i,dev in enumerate(sd.query_devices())
                        if dev["max_input_channels"]>0]
        except Exception as exc:
            QMessageBox.warning(self,"Microfone",str(exc))
            return
        labels=[text for _,text in options]
        cur=next((i for i,(id_,_) in enumerate(options)
                  if id_ == self.settings.microphone_device),0)
        value,ok=QInputDialog.getItem(self,"Microfone","Dispositivo de entrada",labels,cur,False)
        if ok:
            self.settings.microphone_device=options[labels.index(value)][0]
            self._restart()

    def _menu(self,point):
        menu=QMenu(self)
        toggle=menu.addAction("Pausar" if self.worker else "Ouvir novamente")
        mic=menu.addAction("Selecionar microfone...")
        model=menu.addAction("Modelo de IA...")
        sound=menu.addAction("Desativar voz" if self.settings.speak_answers else "Ativar voz")
        clear=menu.addAction("Limpar histórico local")
        menu.addSeparator()
        quit_=menu.addAction("Sair")
        choice=menu.exec(self.face.mapToGlobal(point))
        if choice == toggle:
            self.toggle()
        elif choice == mic:
            self._choose_mic()
        elif choice == model:
            names=["qwen3.5:2b","qwen3.5:4b","qwen3.5:9b"]
            value,ok=QInputDialog.getItem(self,"Modelo Ollama","Modelo:",names,0,True)
            if ok and value.strip():
                self.settings.model=value.strip()
                self._restart()
        elif choice == sound:
            self.settings.speak_answers=not self.settings.speak_answers
            self._restart()
        elif choice == clear:
            if QMessageBox.question(self,"Histórico","Apagar conversa salva?")==QMessageBox.Yes:
                self.history.clear()
        elif choice == quit_:
            self.close()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:
            self.close()
        elif event.key()==Qt.Key_Space:
            self.toggle()
        else:
            super().keyPressEvent(event)

    def closeEvent(self,event):
        if self.worker is not None:
            self.closing=True
            self.worker.cancel()
            event.ignore()
        else:
            event.accept()


def main():
    app=QApplication([])
    app.setApplicationName("IAExpert")
    window=IAExpertWindow()
    window.show()
    app.exec()
