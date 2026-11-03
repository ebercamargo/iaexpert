"""Biblioteca local: leitura de livros e recuperação rápida com SQLite FTS5.

Os arquivos são importados pelo próprio usuário, nunca enviados a um serviço.
Isso é indexação RAG, não treinamento/fine-tuning do modelo.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import zipfile
from contextlib import closing
from threading import Event
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import data_directory

# A leitura dos livros é incremental: não há limite fixo de 60 MB por arquivo.
# Há limites apenas para entradas individuais de arquivos ZIP (proteção
# contra descompressão excessiva e documentos maliciosos).
MAX_ZIP_MEMBER_BYTES = 64 * 1024 * 1024
SUPPORTED = {".pdf", ".epub", ".txt", ".md", ".docx"}
STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "can", "do", "for", "from", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to", "what",
    "when", "where", "why", "with", "you", "your",
    "a", "as", "como", "com", "da", "das", "de", "do", "dos", "em", "eu",
    "essa", "esse", "estou", "me", "meu", "minha", "na", "no", "o", "os",
    "para", "por", "qual", "que", "se", "sobre", "um", "uma", "você",
    "explique", "explain", "ensine", "teach", "fale", "tell", "please",
}


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "svg"}:
            self.ignored += 1
        elif tag in {"p", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "svg"} and self.ignored:
            self.ignored -= 1
        elif tag in {"p", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def _iter_content(path: Path):
    """Extrai texto aos poucos, sem reter um PDF inteiro na RAM."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("Formato não suportado. Utilize PDF, EPUB, TXT, MD ou DOCX.")

    if suffix in {".txt", ".md"}:
        with path.open("rb") as raw:
            prefix = raw.read(16 * 1024)
        try:
            prefix.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            encoding = "cp1252"
        with path.open("r", encoding=encoding, errors="replace") as stream:
            while piece := stream.read(64 * 1024):
                yield piece
        return

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Biblioteca pypdf ausente. Reexecute IAExpert.cmd.") from exc
        document = PdfReader(str(path), strict=False)
        if document.is_encrypted:
            raise ValueError("PDF protegido por senha não pode ser importado.")
        for page in document.pages:
            text = page.extract_text() or ""
            if len(text) > 8_000_000:
                raise ValueError("Página PDF com texto extraído excessivamente grande.")
            if text.strip():
                yield text
        return

    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = info.filename.lower()
                if suffix == ".docx" and name != "word/document.xml":
                    continue
                if suffix == ".epub" and not name.endswith((".xhtml", ".html", ".htm")):
                    continue
                if info.file_size > MAX_ZIP_MEMBER_BYTES:
                    raise ValueError(
                        "Capítulo ou documento XML muito grande para processamento seguro."
                    )
                with archive.open(info) as stream:
                    if suffix == ".docx":
                        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                        # XML iterparse não mantém o documento inteiro em memória.
                        try:
                            for _event, node in ET.iterparse(stream, events=("end",)):
                                if node.tag == namespace + "p":
                                    text = " ".join(
                                        part.text or "" for part in node.iter(namespace + "t")
                                    )
                                    if text:
                                        yield text
                                    node.clear()
                        except ET.ParseError as exc:
                            raise ValueError("DOCX contém XML inválido.") from exc
                    else:
                        parser = _TextOnly()
                        while block := stream.read(64 * 1024):
                            parser.feed(block.decode("utf-8", errors="replace"))
                            if parser.parts:
                                yield "".join(parser.parts)
                                parser.parts.clear()
                        parser.close()
                        if parser.parts:
                            yield "".join(parser.parts)
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("Arquivo de livro compactado inválido ou danificado.") from exc


def _chunks(text: str, size: int = 760, overlap: int = 110):
    """Fragmentação compatível com versões anteriores."""
    yield from _chunks_from_parts((text,), size=size, overlap=overlap)


def _chunks_from_parts(parts, size: int = 760, overlap: int = 110):
    """Converte textos de páginas/capítulos em trechos indexáveis com overlap."""
    pending = ""
    for part in parts:
        if not part:
            continue
        # O maior objeto em RAM é uma página PDF ou um trecho de capítulo.
        pending += " " + re.sub(r"\s+", " ", part)
        while len(pending) > size:
            end = pending.rfind(" ", size // 2, size)
            if end < 0:
                end = size
            fragment = pending[:end].strip()
            if len(fragment) >= 25:
                yield fragment
            pending = pending[max(1, end - overlap):]
    if len(pending.strip()) >= 25:
        yield pending.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _search_query(question: str) -> str:
    tokens = re.findall(r"[^\W_]{2,}", question.lower(), re.UNICODE)
    words = list(dict.fromkeys(token for token in tokens if token not in STOPWORDS))
    # FTS5 receives only quoted escaped tokens; no raw query operators.
    return " OR ".join('"' + word.replace('"', '""') + '"' for word in words[:8])


class BookLibrary:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or data_directory()
        self.db_path = self.directory / "books.sqlite3"

    def _open(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(
                book_id UNINDEXED,
                content,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        return db

    def has_book(self, path: str | Path) -> bool:
        """Permite arquivar livros já indexados, sem duplicar trechos."""
        path = Path(path)
        if not path.is_file() or not self.db_path.is_file():
            return False
        digest = _sha256(path)
        with closing(self._open()) as db:
            return db.execute(
                "SELECT 1 FROM books WHERE sha256=?", (digest,)
            ).fetchone() is not None

    def import_book(
        self, filename: str | Path, stop: Event | None = None
    ) -> tuple[str, int]:
        path = Path(filename)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() not in SUPPORTED:
            raise ValueError("Formato não suportado. Utilize PDF, EPUB, TXT, MD ou DOCX.")
        initial = path.stat()
        digest = _sha256(path)
        with closing(self._open()) as db:
            if db.execute(
                "SELECT id FROM books WHERE sha256=?", (digest,)
            ).fetchone():
                raise ValueError("Este livro já foi importado.")
            # Um INSERT e seus trechos são uma única transação:
            # PDF sem texto ou arquivo parcialmente copiado NÃO é "aprendido".
            with db:
                book = db.execute(
                    "INSERT INTO books(title,sha256) VALUES (?,?)",
                    (path.stem[:180], digest),
                )
                book_id = book.lastrowid
                batch: list[tuple[int, str]] = []
                count = 0
                for fragment in _chunks_from_parts(_iter_content(path)):
                    if stop is not None and stop.is_set():
                        raise InterruptedError("Importação cancelada.")
                    batch.append((book_id, fragment))
                    count += 1
                    if len(batch) >= 150:
                        db.executemany(
                            "INSERT INTO passages(book_id,content) VALUES (?,?)",
                            batch
                        )
                        batch.clear()
                if batch:
                    db.executemany(
                        "INSERT INTO passages(book_id,content) VALUES (?,?)", batch
                    )
                if count == 0:
                    raise ValueError(
                        "Não encontrei texto pesquisável. Um PDF digitalizado exige OCR."
                    )
                current = path.stat()
                if (
                    current.st_size != initial.st_size
                    or current.st_mtime_ns != initial.st_mtime_ns
                    or _sha256(path) != digest
                ):
                    raise ValueError(
                        "O arquivo foi alterado durante a importação. Aguarde a cópia terminar."
                    )
                if stop is not None and stop.is_set():
                    raise InterruptedError("Importação cancelada.")
        return path.stem, count

    def list_books(self) -> list[tuple[int, str]]:
        if not self.db_path.is_file():
            return []
        with self._open() as db:
            return db.execute(
                "SELECT id,title FROM books ORDER BY title"
            ).fetchall()

    def remove_book(self, book_id: int) -> bool:
        if not self.db_path.is_file():
            return False
        with self._open() as db:
            found = db.execute("SELECT id FROM books WHERE id=?", (book_id,)).fetchone()
            if not found:
                return False
            db.execute("DELETE FROM passages WHERE book_id=?", (book_id,))
            db.execute("DELETE FROM books WHERE id=?", (book_id,))
        return True

    def search(self, question: str, limit: int = 2) -> list[tuple[str, str]]:
        if not self.db_path.is_file():
            return []
        query = _search_query(question)
        if not query:
            return []
        with self._open() as db:
            try:
                return db.execute(
                    """SELECT books.title, passages.content
                       FROM passages JOIN books ON books.id = passages.book_id
                       WHERE passages MATCH ?
                       ORDER BY bm25(passages)
                       LIMIT ?""",
                    (query, min(3, max(1, limit))),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
