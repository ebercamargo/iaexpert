"""Conversa contínua por voz, TTS em streaming e cancelamento seguro."""

from __future__ import annotations

from queue import Queue
from threading import Event, Thread
import time

from PySide6.QtCore import QThread, Signal

from .audio import Microphone, SpeechToText
from .voice import choose_voice
from .performance import log_turn
from .config import Settings
from .history import ConversationHistory
from .ollama_client import Cancelled, OllamaClient
from .speech import SentenceBuffer
from .library import BookLibrary
from .tutor import tutor_prompt, retrieval_needed, quick_lesson_reply


class AssistantWorker(QThread):
    state_changed = Signal(str)
    level_changed = Signal(float, float)
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
        # Sem sd.stop() no thread gráfico: o callback do OutputStream
        # detecta stop_event e interrompe a reprodução imediatamente.
        self.stop_event.set()

    def run(self) -> None:
        try:
            stt = SpeechToText(self.settings)
            tts = choose_voice(self.settings)
            if hasattr(tts, "preload"):
                Thread(target=self._prepare_voice, args=(tts,), daemon=True).start()
            client = OllamaClient(self.settings)
            Thread(target=client.preload, daemon=True, name="IAExpert-Ollama-preload").start()
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
        source_material = (
            BookLibrary().search(question) if self.settings.learning_mode == "english_tutor"
            and retrieval_needed(question) else []
        )
        prompt = (
            tutor_prompt(self.settings.english_level, source_material)
            if self.settings.learning_mode == "english_tutor" else None
        )
        buffer = SentenceBuffer(max_chars=95 if prompt else 165)
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
                        def audio_level(level: float, presentation_time: float) -> None:
                            if times["first_audio"] is None and level > 0:
                                times["first_audio"] = presentation_time
                            self.level_changed.emit(level, presentation_time)
                        tts.speak(text, self.stop_event, on_level=audio_level)
                    except Exception as exc:
                        if self.settings.voice_engine != "piper" and not self.stop_event.is_set():
                            try:
                                from .audio import VoiceOutput
                                self.state_changed.emit("Voz neural indisponível; usando Piper local...")
                                VoiceOutput(language="en" if self.settings.learning_mode == "english_tutor" else "pt").speak(
                                    text, self.stop_event, on_level=self.level_changed.emit
                                )
                                continue
                            except Exception as fallback_exc:
                                errors.append(fallback_exc)
                        else:
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
            quick = (quick_lesson_reply(question, self.settings.english_level)
                     if prompt else None)
            if quick:
                on_delta(quick + " ")
                answer = quick
            else:
                answer = client.chat(
                    question, self.history.messages[-6:] if prompt else self.history.messages,
                    on_delta, self.stop_event.is_set,
                    system_prompt=prompt, max_tokens=85 if prompt else None,
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
                        # O callback recebe stop_event e encerra o stream.
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
