"""Cliente REST da API local do Ollama, com resposta em streaming."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from urllib import error, request

from .config import Settings


SYSTEM_PROMPT = (
    "Você é IAExpert, um assistente de voz para conversas informais em português do Brasil. "
    "Responda de forma oral, natural e curta: uma a três frases, sem explicações longas. "
    "Nunca use Markdown, listas, números de tópicos, asteriscos, títulos, blocos de código, "
    "abreviações estranhas nem formatação. Responda apenas em texto falado natural. "
    "Use o contexto recente. Se não souber, diga. "
    "Não invente ações realizadas no computador nem pesquisas externas."
)


class Cancelled(Exception):
    """A operação foi interrompida pelo usuário."""


class OllamaError(Exception):
    """Falha de conexão, modelo ausente ou resposta inválida."""


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def preload(self) -> None:
        """Solicita ao Ollama carregar o modelo na memória, sem enviar mensagens."""
        req = request.Request(
            self.settings.ollama_url.rstrip("/") + "/api/generate",
            data=json.dumps({
                "model": self.settings.model, "stream": False,
                "keep_alive": "30m"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with request.urlopen(req, timeout=90) as response:
                response.read(1)
        except (OSError, TimeoutError, ValueError):
            # Chat reportará um erro com instruções caso a conexão falhe.
            pass

    def chat(
        self,
        text: str,
        history: Sequence[dict[str, str]],
        on_delta: Callable[[str], None],
        cancelled: Callable[[], bool] = lambda: False,
    ) -> str:
        if cancelled():
            raise Cancelled()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": text})
        payload = json.dumps(
            {
                "model": self.settings.model,
                "messages": messages,
                "stream": True,
                "think": False,
                "keep_alive": "30m",
                "options": {"temperature": 0.45, "num_ctx": 1536, "num_predict": 104},
            }
        ).encode("utf-8")
        req = request.Request(
            self.settings.ollama_url.rstrip("/") + "/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        parts: list[str] = []
        try:
            with request.urlopen(req, timeout=180) as response:
                for line in response:
                    if cancelled():
                        raise Cancelled()
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise OllamaError(str(event["error"]))
                    delta = event.get("message", {}).get("content", "")
                    if delta:
                        parts.append(delta)
                        on_delta(delta)
                    if event.get("done"):
                        break
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:600]
            if exc.code == 404:
                raise OllamaError(
                    "Modelo não encontrado no Ollama. Execute: ollama pull "
                    + self.settings.model
                ) from exc
            raise OllamaError(f"Ollama respondeu HTTP {exc.code}: {body}") from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(
                "Não foi possível acessar o Ollama. Confirme que ele está instalado "
                "e em execução na porta 11434."
            ) from exc
        except (ValueError, TypeError) as exc:
            raise OllamaError("Resposta inesperada do Ollama.") from exc

        if cancelled():
            raise Cancelled()
        answer = "".join(parts).strip()
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        if not answer:
            raise OllamaError("O modelo não retornou uma resposta.")
        return answer
