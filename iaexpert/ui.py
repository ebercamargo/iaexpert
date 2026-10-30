"""Rosto flutuante com transparência real sobre as janelas do Windows."""
from __future__ import annotations

import math
import time
import os
import sys
from collections import deque
from threading import Thread
from dataclasses import replace

import sounddevice as sd
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QIcon
from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow, QMenu, QMessageBox, QWidget, QSystemTrayIcon

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
        self.level = 0.0
        self.audio_events = deque(maxlen=200)
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
            self.audio_events.clear()
            self.audio_level = 0.0
            self.level = 0.0
        self.update()

    def set_audio_level(self, level: float, play_time: float):
        # O timestamp vem diretamente do buffer entregue ao PortAudio.
        # A fila fica no thread Qt e acompanha a saída efetiva do dispositivo.
        self.audio_events.append(
            (float(play_time), max(0.0, min(1.0, float(level))))
        )

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
        now = time.monotonic()
        while self.audio_events and self.audio_events[0][0] <= now:
            _, self.audio_level = self.audio_events.popleft()
        wanted = self.audio_level if self.mode == "speaking" else 0.0
        smoothing = 0.80 if wanted >= self.level else 0.66
        self.level += (wanted - self.level) * smoothing
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
        self.restart_requested=False
        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self._force_exit)
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
        self._add_tray_icon()
        self._watch_launcher()
        QTimer.singleShot(350,self._initialize_voice)

    def _initialize_voice(self):
        if self.settings.voice_engine == "ask":
            dialog = QMessageBox(self)
            dialog.setWindowTitle("IAExpert — qualidade da voz")
            dialog.setIcon(QMessageBox.Question)
            dialog.setText("Deseja usar uma voz brasileira mais natural?")
            dialog.setInformativeText(
                "A voz neural online pode soar mais humana e começar mais rápido. "
                "Para gerar a fala, o texto das respostas será enviado ao serviço "
                "online de voz da Microsoft. O microfone e o histórico permanecem "
                "processados localmente. Essa integração pode parar de funcionar "
                "sem aviso e exige internet.\n\n"
                "Sim: Francisca Neural (online).\n"
                "Não: Piper (voz atual, totalmente local)."
            )
            dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dialog.setDefaultButton(QMessageBox.No)
            choice = dialog.exec()
            self.settings.voice_engine = "edge" if choice == QMessageBox.Yes else "piper"
            self.settings.save()
        self._start()

    def _choose_voice(self):
        options = [
            ("Neural feminina — Francisca (online)", "edge", "pt-BR-FranciscaNeural"),
            ("Neural masculina — Antônio (online)", "edge", "pt-BR-AntonioNeural"),
            ("Piper — voz local, sem internet", "piper", self.settings.voice_name),
            ("Chatterbox — neural local NVIDIA GPU", "chatterbox", self.settings.voice_name),
        ]
        names = [option[0] for option in options]
        current = next((
            index for index, (_, engine, name) in enumerate(options)
            if engine == self.settings.voice_engine
            and (engine == "piper" or name == self.settings.voice_name)
        ), 0)
        chosen, ok = QInputDialog.getItem(
            self, "Voz do IAExpert", "Escolha a voz:", names, current, False
        )
        if not ok:
            return
        _, engine, name = options[names.index(chosen)]
        if engine == "edge" and self.settings.voice_engine != "edge":
            answer = QMessageBox.question(
                self, "Voz online", "Autoriza enviar o texto das respostas "
                "ao serviço online de voz da Microsoft? "
                "O microfone e o histórico não são enviados por esse recurso.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
        if engine == "chatterbox":
            try:
                import importlib.util
                import torch
                if importlib.util.find_spec("chatterbox") is None or not torch.cuda.is_available():
                    QMessageBox.information(
                        self, "Voz GPU", "A voz Chatterbox requer uma GPU NVIDIA "
                        "compatível e instalação adicional. Execute Instalar-Voz-GPU.ps1 "
                        "na pasta do projeto e reinicie."
                    )
                    return
            except ImportError:
                QMessageBox.information(
                    self, "Voz GPU", "Instale o PyTorch CUDA e a voz Chatterbox "
                    "com Instalar-Voz-GPU.ps1 antes de selecionar esta opção."
                )
                return
        self.settings.voice_engine = engine
        self.settings.voice_name = name
        self._restart()

    def _choose_gpu(self):
        names = ["Automático (GPU NVIDIA se disponível)", "Somente CPU", "Forçar CUDA"]
        values = ["auto", "cpu", "cuda"]
        selected = values.index(self.settings.stt_device)
        label, accepted = QInputDialog.getItem(
            self, "Aceleração de voz", "Dispositivo Whisper:", names, selected, False
        )
        if accepted:
            self.settings.stt_device = values[names.index(label)]
            self._restart()

    def _choose_recognition(self):
        options = ["tiny — rápido (menor precisão)", "base — equilibrado",
                   "small — mais preciso (mais lento)"]
        keys = ["tiny", "base", "small"]
        index = keys.index(self.settings.whisper_model) if self.settings.whisper_model in keys else 0
        name, ok = QInputDialog.getItem(
            self, "Reconhecimento de voz", "Velocidade/precisão:", options, index, False
        )
        if ok:
            self.settings.whisper_model = keys[options.index(name)]
            self._restart()

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
            QTimer.singleShot(0, self.close)
        elif self.restart_requested:
            self.restart_requested=False
            QTimer.singleShot(50, self._start)

    def _failed(self,error):
        QMessageBox.warning(self,"IAExpert",error)

    def _restart(self):
        self.settings.save()
        if self.worker is not None:
            self.restart_requested=True
            self.worker.cancel()
        else:
            self._start()

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
        neural=menu.addAction("Voz e naturalidade...")
        recognition=menu.addAction("Reconhecimento: velocidade...")
        gpu=menu.addAction("Reconhecimento: GPU/CPU...")
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
        elif choice == neural:
            self._choose_voice()
        elif choice == recognition:
            self._choose_recognition()
        elif choice == gpu:
            self._choose_gpu()
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

    def _add_tray_icon(self):
        """Permite encerrar mesmo se o rosto não estiver com o foco."""
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(QIcon(self.face.frames.frames[0]), self)
        tray.setToolTip("IAExpert — assistente de voz")
        menu = QMenu()
        listen = menu.addAction("Pausar / voltar a ouvir")
        listen.triggered.connect(self.toggle)
        quit_action = menu.addAction("Encerrar IAExpert")
        quit_action.triggered.connect(self.close)
        tray.setContextMenu(menu)
        tray.show()
        self.tray = tray
        self._tray_menu = menu

    @staticmethod
    def _watch_parent_process(parent_pid: int):
        """Quando o PowerShell iniciador morre, evita processo GUI órfão."""
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.WaitForSingleObject.restype = ctypes.c_uint32
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            process = kernel32.OpenProcess(0x00100000, False, parent_pid)
            if not process:
                return
            try:
                result = kernel32.WaitForSingleObject(process, 0xFFFFFFFF)
                if result == 0:
                    os._exit(0)
            finally:
                kernel32.CloseHandle(process)
        except Exception:
            return

    def _watch_launcher(self):
        launcher = os.environ.get("IAEXPERT_LAUNCHER_PID", "")
        if sys.platform == "win32" and launcher.isdecimal():
            Thread(
                target=self._watch_parent_process,
                args=(int(launcher),),
                daemon=True,
                name="IAExpert-launcher-watch",
            ).start()

    def _force_exit(self):
        """Fallback para inferências externas que ignorem cancelamento."""
        if self.closing:
            os._exit(0)

    def closeEvent(self,event):
        if self.worker is not None:
            if not self.closing:
                self.closing = True
                self.worker.cancel()
                # Nunca deixar uma síntese neural travada impedir sair.
                self._exit_timer.start(3000)
            event.ignore()
        else:
            self._exit_timer.stop()
            if self.tray is not None:
                self.tray.hide()
            event.accept()


def main():
    app=QApplication([])
    app.setApplicationName("IAExpert")
    window=IAExpertWindow()
    window.show()
    app.exec()
