"""Executa uma conversa fora da thread de interface Qt."""

from __future__ import annotations

from threading import Event

import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from .audio import Microphone, SpeechToText, VoiceOutput
from .config import Settings
from .history import ConversationHistory
from .ollama_client import Cancelled, OllamaClient


class AssistantWorker(QThread):
    state_changed = Signal(str)
    question_ready = Signal(str)
    answer_started = Signal()
    answer_delta = Signal(str)
    answer_finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        settings: Settings,
        history: ConversationHistory,
        typed_text: str | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.history = history
        self.typed_text = typed_text
        self.stop_event = Event()

    def cancel(self) -> None:
        self.stop_event.set()
        # Interrompe a reprodução imediatamente; não interfere com arquivos locais.
        sd.stop()

    def run(self) -> None:
        try:
            stt = SpeechToText(self.settings)
            tts = VoiceOutput()
            client = OllamaClient(self.settings)
            if self.typed_text is not None:
                if self.typed_text.strip():
                    self._respond(self.typed_text.strip(), client, tts)
                return

            microphone = Microphone(self.settings.microphone_threshold)
            while not self.stop_event.is_set():
                self.state_changed.emit("Ouvindo... fale normalmente")
                recording = microphone.record(
                    self.stop_event,
                    wait_seconds=None if self.settings.auto_continue else 15.0,
                )
                if self.stop_event.is_set():
                    break
                if recording is None:
                    self.state_changed.emit("Nenhuma fala detectada.")
                    break

                self.state_changed.emit("Transcrevendo sua fala...")
                transcript = stt.transcribe(recording)
                if self.stop_event.is_set():
                    break
                if not transcript:
                    self.state_changed.emit("Não consegui compreender. Tente novamente.")
                    if not self.settings.auto_continue:
                        break
                    continue

                self.question_ready.emit(transcript)
                self._respond(transcript, client, tts)
                if not self.settings.auto_continue:
                    break
        except Cancelled:
            pass
        except Exception as exc:
            if not self.stop_event.is_set():
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _respond(
        self,
        question: str,
        client: OllamaClient,
        tts: VoiceOutput,
    ) -> None:
        if self.stop_event.is_set():
            raise Cancelled()
        self.state_changed.emit("IAExpert está pensando...")
        self.answer_started.emit()
        reply = client.chat(
            question,
            self.history.messages,
            self.answer_delta.emit,
            self.stop_event.is_set,
        )
        if self.stop_event.is_set():
            raise Cancelled()
        self.history.add_turn(question, reply)
        self.answer_finished.emit(reply)
        if self.settings.speak_answers:
            self.state_changed.emit("IAExpert está falando...")
            tts.speak(reply, self.stop_event)
        self.state_changed.emit("Pronto")
