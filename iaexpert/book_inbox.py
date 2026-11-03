"""Entrada automática de livros: livros/ -> livros/aprendido/.

O arquivo só é movido depois que seu conteúdo está recuperável no SQLite.
Um arquivo inválido fica na entrada; nunca é excluído nem sobrescrito.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event

from .library import BookLibrary, SUPPORTED


def books_folder() -> Path:
    return Path(__file__).resolve().parent.parent / "livros"


@dataclass(frozen=True)
class InboxResult:
    filename: str
    status: str
    passages: int = 0
    detail: str = ""
    destination: Path | None = None


class BookInbox:
    def __init__(
        self,
        directory: Path | None = None,
        library: BookLibrary | None = None,
    ) -> None:
        self.directory = Path(directory) if directory else books_folder()
        self.learned = self.directory / "aprendido"
        self.library = library or BookLibrary()
        self._seen: dict[str, tuple[int, int]] = {}
        self._failed: dict[str, tuple[int, int]] = {}
        self._reported: dict[str, tuple[int, int]] = {}
        self.prepare()

    def prepare(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.learned.mkdir(parents=True, exist_ok=True)

    def _destination(self, filename: str) -> Path:
        base = Path(filename)
        target = self.learned / base.name
        number = 2
        while target.exists():
            target = self.learned / f"{base.stem} ({number}){base.suffix}"
            number += 1
        return target

    def _log_failure(self, filename: str, reason: str) -> None:
        try:
            with (self.directory / "importacao.log").open(
                "a", encoding="utf-8"
            ) as log:
                log.write(
                    f"{datetime.now().isoformat(timespec='seconds')} "
                    f"{filename}: {reason}\n"
                )
        except OSError:
            logging.exception("Não foi possível gravar falha de importação.")

    def scan_once(self, stop: Event | None = None) -> list[InboxResult]:
        """Um arquivo precisa aparecer estável em duas varreduras consecutivas."""
        self.prepare()
        results: list[InboxResult] = []
        for file in sorted(self.directory.iterdir(), key=lambda path: path.name.lower()):
            if stop is not None and stop.is_set():
                break
            if (
                not file.is_file() or file.is_symlink()
                or file.suffix.lower() not in SUPPORTED
            ):
                continue
            try:
                stat = file.stat()
            except OSError:
                continue
            signature = (stat.st_size, stat.st_mtime_ns)
            if self._seen.get(file.name) != signature:
                self._seen[file.name] = signature
                self._failed.pop(file.name, None)
                self._reported.pop(file.name, None)
                continue
            if self._failed.get(file.name) == signature:
                continue

            importing = True
            try:
                try:
                    title, count = self.library.import_book(file, stop=stop)
                except ValueError as exc:
                    # Se o mesmo arquivo já consta no índice, não reindexa.
                    if str(exc) == "Este livro já foi importado." and self.library.has_book(file):
                        title, count = file.stem, 0
                    else:
                        raise

                if stop is not None and stop.is_set():
                    break
                after = file.stat()
                if (after.st_size, after.st_mtime_ns) != signature:
                    raise ValueError(
                        "Arquivo alterado após leitura. Aguarde a cópia terminar."
                    )
                importing = False
                destination = self._destination(file.name)
                file.rename(destination)
                results.append(InboxResult(
                    filename=file.name, status="aprendido",
                    passages=count, detail=title, destination=destination,
                ))
                self._seen.pop(file.name, None)
                self._failed.pop(file.name, None)
                self._reported.pop(file.name, None)
            except InterruptedError:
                break
            except Exception as exc:
                reason = str(exc) or type(exc).__name__
                # Arquivo incompleto ou sem texto: manter na entrada.
                # Erros de disco/movimentação são transitórios e serão tentados
                # novamente. Um erro permanente só é reavaliado se o arquivo mudar.
                if not isinstance(exc, OSError) and importing:
                    self._failed[file.name] = signature
                if self._reported.get(file.name) != signature:
                    self._reported[file.name] = signature
                    self._log_failure(file.name, reason)
                    results.append(InboxResult(
                        filename=file.name, status="erro", detail=reason,
                    ))
        return results

    def run(
        self,
        stop: Event,
        on_result,
        interval: float = 3.0,
    ) -> None:
        """Observação leve: deixa microfone e GUI livres em outra thread."""
        while not stop.is_set():
            try:
                for result in self.scan_once(stop):
                    on_result(result)
            except Exception:
                logging.exception("Falha ao verificar pasta de livros.")
            stop.wait(interval)
