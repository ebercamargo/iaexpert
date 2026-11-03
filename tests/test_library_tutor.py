"""RAG SQLite e comportamento de professor, inteiramente offline."""
import tempfile
import unittest
from pathlib import Path

from iaexpert.library import BookLibrary
from iaexpert.tutor import retrieval_needed, tutor_prompt, quick_lesson_reply


class BookLibraryTests(unittest.TestCase):
    def test_import_query_and_remove(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            book = root / "English Grammar Basics.txt"
            book.write_text(
                ("The present perfect tense is used for unfinished time. "
                 "Use have or has plus the past participle. " * 14)
                + "\nThe present continuous is used for actions happening now. " * 12,
                encoding="utf-8"
            )
            library = BookLibrary(root)
            title, parts = library.import_book(book)
            self.assertEqual(title, "English Grammar Basics")
            self.assertGreater(parts, 1)
            matches = library.search("explain present perfect")
            self.assertTrue(matches)
            self.assertTrue(any("present perfect" in passage for _, passage in matches))
            self.assertEqual(matches[0][0], title)
            with self.assertRaisesRegex(ValueError, "já foi importado"):
                library.import_book(book)
            book_id = library.list_books()[0][0]
            self.assertTrue(library.remove_book(book_id))
            self.assertEqual(library.list_books(), [])
            self.assertEqual(library.search("present perfect"), [])

    def test_search_resists_operator_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            lib = BookLibrary(Path(directory))
            book = Path(directory) / "abc.txt"
            book.write_text("English language is fun. " * 20, encoding="utf-8")
            lib.import_book(book)
            self.assertEqual(lib.search('NOT (( OR AND " " ) (', limit=2), [])
            self.assertTrue(lib.search("English?!"))

    def test_rejects_pdf_without_text_stub(self):
        with tempfile.TemporaryDirectory() as directory:
            book = Path(directory) / "empty.txt"
            book.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "texto pesquisável"):
                BookLibrary(Path(directory)).import_book(book)

    def test_accepts_own_md_and_formats(self):
        self.assertIn(".pdf", __import__("iaexpert.library", fromlist=["SUPPORTED"]).SUPPORTED)
        self.assertIn(".epub", __import__("iaexpert.library", fromlist=["SUPPORTED"]).SUPPORTED)
        self.assertIn(".docx", __import__("iaexpert.library", fromlist=["SUPPORTED"]).SUPPORTED)


class TutorPromptTests(unittest.TestCase):
    def test_bilingual_english_teaching_and_short_reply(self):
        prompt = tutor_prompt("A1", [("Grammar 101", "The past is used for yesterday.")])
        self.assertIn("English teacher", prompt)
        self.assertIn("A1", prompt)
        self.assertIn("ONE question", prompt)
        self.assertIn("Grammar 101", prompt)
        self.assertIn("untrusted source text", prompt)

    def test_fixed_greetings_skip_model_wait(self):
        self.assertEqual(
            quick_lesson_reply("Hello!", "A1"),
            "Hello! I'm your English teacher. How are you today?"
        )
        self.assertIn("name", quick_lesson_reply("Vamos começar a aula", "A1"))
        self.assertIsNone(quick_lesson_reply("Explain past perfect", "A1"))

    def test_only_retrieve_for_material_specific_request(self):
        self.assertFalse(retrieval_needed("Hello, how are you?"))
        self.assertTrue(retrieval_needed("Read the book about grammar"))
        self.assertTrue(retrieval_needed("Explique o capítulo do livro"))
        self.assertTrue(retrieval_needed("Teach me the past tense"))


if __name__ == "__main__":
    unittest.main()
