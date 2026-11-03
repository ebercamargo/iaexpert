"""Biblioteca local: leitura de livros e recuperação rápida com SQLite FTS5.

Os arquivos são importados pelo próprio usuário, nunca enviados a um serviço.
Isso é indexação RAG, não treinamento/fine-tuning do modelo.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import data_directory

MAX_FILE_BYTES = 60 * 1024 * 1024
MAX_TEXT_CHARS = 5_000_000
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


def _read_content(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("Formato não suportado. Utilize PDF, EPUB, TXT, MD ou DOCX.")

    if suffix in {".txt", ".md"}:
        raw = path.read_bytes()
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("cp1252", errors="replace")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Biblioteca pypdf ausente. Reexecute IAExpert.cmd.") from exc
        document = PdfReader(str(path))
        if document.is_encrypted:
            raise ValueError("PDF protegido por senha não pode ser importado.")
        pages = []
        length = 0
        for page in document.pages:
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 20 * 1024 * 1024:
                raise ValueError("Página PDF muito grande para extração segura.")
            text = page.extract_text() or ""
            length += len(text)
            if length > MAX_TEXT_CHARS:
                raise ValueError("Livro muito grande: limite de 5 milhões de caracteres.")
            pages.append(text)
        return "\n".join(pages)

    with zipfile.ZipFile(path) as archive:
        # EPUB e DOCX são ZIPs; nunca extraímos arquivos no disco.
        contents = []
        length = 0
        for info in archive.infolist():
            name = info.filename.lower()
            if info.file_size > 8 * 1024 * 1024:
                continue
            if suffix == ".docx" and name != "word/document.xml":
                continue
            if suffix == ".epub" and not name.endswith((".xhtml", ".html", ".htm")):
                continue
            try:
                raw = archive.read(info)
                if suffix == ".docx":
                    root = ET.fromstring(raw)
                    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                    text = "\n".join(
                        "".join(node.text or "" for node in paragraph.iter(ns + "t"))
                        for paragraph in root.iter(ns + "p")
                    )
                else:
                    parser = _TextOnly()
                    parser.feed(raw.decode("utf-8", errors="replace"))
                    text = "".join(parser.parts)
            except (ET.ParseError, UnicodeDecodeError, ValueError) as exc:
                raise ValueError(f"Não foi possível ler o conteúdo de {path.name}.") from exc
            length += len(text)
            if length > MAX_TEXT_CHARS:
                raise ValueError("Livro muito grande: limite de 5 milhões de caracteres.")
            contents.append(text)
        return "\n".join(contents)


def _chunks(text: str, size: int = 760, overlap: int = 110):
    normalized = re.sub(r"\s+", " ", text).strip()
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        if end < len(normalized):
            word_boundary = normalized.rfind(" ", start + size // 2, end)
            if word_boundary != -1:
                end = word_boundary
        fragment = normalized[start:end].strip()
        if len(fragment) >= 25:
            yield fragment
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)


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

    def import_book(self, filename: str | Path) -> tuple[str, int]:
        path = Path(filename)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() not in SUPPORTED:
            raise ValueError("Formato não suportado. Utilize PDF, EPUB, TXT, MD ou DOCX.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Arquivo maior que o limite de 60 MB.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        with self._open() as db:
            if db.execute("SELECT id FROM books WHERE sha256=?", (digest.hexdigest(),)).fetchone():
                raise ValueError("Este livro já foi importado.")
        text = _read_content(path)
        if len(text) > MAX_TEXT_CHARS:
            raise ValueError("Livro muito grande para a biblioteca local.")
        fragments = list(_chunks(text))
        if not fragments:
            raise ValueError(
                "Não encontrei texto pesquisável. Um PDF digitalizado exige OCR."
            )
        with self._open() as db:
            cursor = db.execute(
                "INSERT INTO books(title,sha256) VALUES (?,?)",
                (path.stem[:180], digest.hexdigest()),
            )
            db.executemany(
                "INSERT INTO passages(book_id,content) VALUES (?,?)",
                ((cursor.lastrowid, passage) for passage in fragments),
            )
        return path.stem, len(fragments)

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
