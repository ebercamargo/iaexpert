"""Conversa contínua por voz, TTS em streaming e cancelamento seguro."""

from __future__ import annotations

from queue import Queue
from threading import Event, Thread

import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from .audio import Microphone, SpeechToText, VoiceOutput
from .config import Settings
from .history import ConversationHistory
from .ollama_client import Cancelled, OllamaClient
from .speech import SentenceBuffer


class AssistantWorker(QThread):
    state_changed = Signal(str)
    level_changed = Signal(float)
    question_ready = Signal(str)
    answer_finished = Signal(str)
    failed = Signal(str)

    def __init__(self, settings: Settings, history: ConversationHistory) -> None:
        super().__init__()
        self.settings = settings
        self.history = history
        self.stop_event = Event()

    def cancel(self) -> None:
        self.stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass

    def run(self) -> None:
        try:
            stt = SpeechToText(self.settings)
            tts = VoiceOutput()
            client = OllamaClient(self.settings)
            microphone = Microphone(
                self.settings.microphone_threshold,
                device=self.settings.microphone_device,
            )
            while not self.stop_event.is_set():
                self.state_changed.emit("Ouvindo...")
                samples = microphone.record(self.stop_event, wait_seconds=None)
                if self.stop_event.is_set():
                    break
                if samples is None:
                    continue

                self.state_changed.emit("Reconhecendo a voz...")
                text = stt.transcribe(samples)
                if self.stop_event.is_set():
                    break
                if not text:
                    self.state_changed.emit("Não entendi. Pode repetir?")
                    continue

                self.question_ready.emit(text)
                self._respond(text, client, tts)
                if not self.settings.auto_continue:
                    break
        except Cancelled:
            pass
        except Exception as exc:
            if not self.stop_event.is_set():
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _respond(self, question: str, client: OllamaClient, tts: VoiceOutput) -> None:
        if self.stop_event.is_set():
            raise Cancelled()

        self.state_changed.emit("Pensando...")
        buffer = SentenceBuffer()
        chunks: Queue[str | None] = Queue()
        errors: list[Exception] = []
        speaker: Thread | None = None

        if self.settings.speak_answers:
            def playback() -> None:
                while not self.stop_event.is_set():
                    text = chunks.get()
                    if text is None:
                        return
                    try:
                        self.state_changed.emit("Falando...")
                        tts.speak(text, self.stop_event, on_level=self.level_changed.emit)
                    except Exception as exc:
                        errors.append(exc)
                        return

            speaker = Thread(target=playback, name="IAExpert-TTS", daemon=True)
            speaker.start()

        def on_delta(delta: str) -> None:
            for chunk in buffer.feed(delta):
                if speaker is not None and not self.stop_event.is_set():
                    chunks.put(chunk)

        try:
            answer = client.chat(
                question, self.history.messages, on_delta, self.stop_event.is_set
            )
            remaining = buffer.finish()
            if remaining and speaker is not None and not self.stop_event.is_set():
                chunks.put(remaining)
            if not self.stop_event.is_set():
                self.history.add_turn(question, answer)
                self.answer_finished.emit(answer)
        finally:
            if speaker is not None:
                chunks.put(None)
                # A fala já está ocorrendo em paralelo ao restante da geração.
                while speaker.is_alive():
                    speaker.join(timeout=0.15)
                    if self.stop_event.is_set():
                        try:
                            sd.stop()
                        except Exception:
                            pass

        if errors:
            raise errors[0]
        if self.stop_event.is_set():
            raise Cancelled()
        self.state_changed.emit("Pronto")
