"""Conversa contínua por voz, TTS em streaming e cancelamento seguro."""

from __future__ import annotations

from queue import Queue
from threading import Event, Thread
import time

import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from .audio import Microphone, SpeechToText
from .voice import choose_voice
from .performance import log_turn
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

    def _prepare_voice(self, tts) -> None:
        try:
            tts.preload()
        except Exception:
            # A falha será mostrada ao usuário ao tentar sintetizar a resposta.
            pass

    def cancel(self) -> None:
        self.stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass

    def run(self) -> None:
        try:
            stt = SpeechToText(self.settings)
            tts = choose_voice(self.settings)
            if hasattr(tts, "preload"):
                Thread(target=self._prepare_voice, args=(tts,), daemon=True).start()
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
                stt_started = time.monotonic()
                text = stt.transcribe(samples)
                stt_ms = (time.monotonic()-stt_started)*1000
                if self.stop_event.is_set():
                    break
                if not text:
                    self.state_changed.emit("Não entendi. Pode repetir?")
                    continue

                self.question_ready.emit(text)
                self._respond(text, client, tts, stt_ms)
                if not self.settings.auto_continue:
                    break
        except Cancelled:
            pass
        except Exception as exc:
            if not self.stop_event.is_set():
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _respond(self, question: str, client: OllamaClient, tts, stt_ms: float = 0) -> None:
        if self.stop_event.is_set():
            raise Cancelled()

        self.state_changed.emit("Pensando...")
        requested = time.monotonic()
        times = {"first_token": None, "first_audio": None}
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
                        def audio_level(level: float) -> None:
                            if times["first_audio"] is None and level > 0:
                                times["first_audio"] = time.monotonic()
                            self.level_changed.emit(level)
                        tts.speak(text, self.stop_event, on_level=audio_level)
                    except Exception as exc:
                        errors.append(exc)
                        return

            speaker = Thread(target=playback, name="IAExpert-TTS", daemon=True)
            speaker.start()

        def on_delta(delta: str) -> None:
            if times["first_token"] is None:
                times["first_token"] = time.monotonic()
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
        if self.settings.performance_log:
            log_turn(self.settings.model, self.settings.voice_engine, stt_ms,
                     requested, times["first_token"], times["first_audio"],
                     time.monotonic())
        self.state_changed.emit("Pronto")
