"""Pasta automática livros/ -> livros/aprendido, sem perder arquivos."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
from types import SimpleNamespace

from iaexpert.book_inbox import BookInbox
from iaexpert.library import BookLibrary


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inbox_path = self.root / "livros"
        self.library = BookLibrary(self.root / "dados")
        self.inbox = BookInbox(self.inbox_path, self.library)

    def tearDown(self):
        self.temp.cleanup()

    def add_book(self, name: str, content: str | None = None) -> Path:
        book = self.inbox_path / name
        book.write_text(content or ("English grammar lessons are useful. " * 25),
                        encoding="utf-8")
        # Os arquivos de teste já terminaram de copiar.
        previous = time.time() - 20
        os.utime(book, (previous, previous))
        return book

    def test_folders_created_and_auto_move_only_after_two_scans(self):
        self.assertTrue(self.inbox.learned.is_dir())
        original = self.add_book("grammar.txt")
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertTrue(original.is_file())
        results = self.inbox.scan_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "aprendido")
        self.assertGreater(results[0].passages, 0)
        self.assertFalse(original.exists())
        self.assertTrue((self.inbox.learned / original.name).is_file())
        self.assertTrue(self.library.search("grammar lessons"))

    def test_duplicate_already_indexed_file_is_archived_without_reindexing(self):
        self.add_book("old.txt")
        self.inbox.scan_once()
        self.inbox.scan_once()
        duplicate = self.add_book("old-again.txt")
        self.inbox.scan_once()
        results = self.inbox.scan_once()
        self.assertEqual(results[0].passages, 0)
        self.assertTrue((self.inbox.learned / duplicate.name).exists())
        self.assertEqual(len(self.library.list_books()), 1)

    def test_same_filename_never_overwrites_learned_book(self):
        original = self.add_book("course.txt")
        self.inbox.scan_once()
        self.inbox.scan_once()
        prior = (self.inbox.learned / original.name).read_text(encoding="utf-8")
        self.add_book("course.txt", "A different English book about vocabulary. " * 35)
        self.inbox.scan_once()
        self.inbox.scan_once()
        self.assertEqual(
            (self.inbox.learned / original.name).read_text(encoding="utf-8"), prior
        )
        self.assertTrue((self.inbox.learned / "course (2).txt").exists())
        self.assertEqual(len(self.library.list_books()), 2)

    def test_invalid_file_remains_in_input_and_reports_error_once(self):
        bad = self.add_book("empty.txt", "x")
        self.inbox.scan_once()
        results = self.inbox.scan_once()
        self.assertEqual(results[0].status, "erro")
        self.assertTrue(bad.exists())
        self.assertEqual(self.library.list_books(), [])
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertIn("empty.txt", (self.inbox_path / "importacao.log").read_text(
            encoding="utf-8"
        ))

    def test_ignores_temporary_files_and_learned_subfolder(self):
        self.add_book("downloading.part", "This cannot be indexed. " * 20)
        self.add_book("book.tmp", "This cannot be indexed. " * 20)
        (self.inbox.learned / "old.txt").write_text(
            "Already archived. " * 20, encoding="utf-8"
        )
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertEqual(self.library.list_books(), [])

    def test_import_waits_for_file_to_stop_changing(self):
        file = self.inbox_path / "incomplete.txt"
        file.write_text("English verbs are useful. " * 15, encoding="utf-8")
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertEqual(self.inbox.scan_once(), [])
        assert file.exists()
        previous = time.time() - 20
        os.utime(file, (previous, previous))
        self.assertEqual(self.inbox.scan_once(), [])
        self.assertEqual(self.inbox.scan_once()[0].status, "aprendido")

    def test_cancelled_index_does_not_archive(self):
        book = self.add_book("course.txt")
        stopped = Event()
        stopped.set()
        self.assertEqual(self.inbox.scan_once(stopped), [])
        self.assertTrue(book.exists())

    def test_pdf_without_text_is_not_moved(self):
        from pypdf import PdfWriter
        pdf = self.inbox_path / "scan.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=400, height=400)
        with pdf.open("wb") as output:
            writer.write(output)
        previous = time.time() - 20
        os.utime(pdf, (previous, previous))
        self.inbox.scan_once()
        outcome = self.inbox.scan_once()
        self.assertEqual(outcome[0].status, "erro")
        self.assertTrue(pdf.exists())
        self.assertFalse((self.inbox.learned / "scan.pdf").exists())

    def test_import_no_longer_rejects_60mb_file_size(self):
        text = self.add_book("large.txt")
        normal_stat = Path.stat

        def custom_stat(path, **kwargs):
            actual = normal_stat(path, **kwargs)
            if path == text:
                return SimpleNamespace(
                    st_mode=actual.st_mode,
                    st_size=75 * 1024 * 1024,
                    st_mtime_ns=actual.st_mtime_ns,
                )
            return actual

        # Simula metadados de um arquivo de 75 MB sem gerar esse volume
        # de dados no teste. A extração ainda lê efetivamente o conteúdo.
        with patch("iaexpert.library.Path.stat", new=custom_stat):
            title, count = self.library.import_book(text)
        self.assertEqual(title, "large")
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
