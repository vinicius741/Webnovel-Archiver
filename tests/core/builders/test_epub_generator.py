import unittest
import os
import shutil
import json
import datetime
import ebooklib # Ensure ebooklib itself is imported
from ebooklib import epub
from webnovel_archiver.core.builders.epub_generator import EPUBGenerator
from webnovel_archiver.utils.logger import get_logger # For potential direct use or if generator uses it

# Disable logging for tests to keep output clean, or configure for test-specific output
# import logging
# logging.getLogger('webnovel_archiver').setLevel(logging.CRITICAL)


class TestEPUBGenerator(unittest.TestCase):
    def setUp(self):
        self.test_workspace = "test_workspace_epub_generator"
        self.story_id = "test_story_001"
        self.processed_content_dir = os.path.join(self.test_workspace, "processed_content", self.story_id)
        self.ebooks_dir = os.path.join(self.test_workspace, "ebooks", self.story_id)

        # Clean up before each test
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace)
        os.makedirs(self.processed_content_dir, exist_ok=True)
        os.makedirs(self.ebooks_dir, exist_ok=True)

        self.epub_generator = EPUBGenerator(workspace_root=self.test_workspace)

        self.sample_progress_data = {
            "effective_title": "My Awesome Story", # Changed "title" to "effective_title"
            "author": "Test Author",
            "story_id": self.story_id,
            "downloaded_chapters": []
        }

    def tearDown(self):
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace)

    def _create_dummy_html_file(self, filename_prefix: str, chapter_order: int, title: str, content: str) -> dict:
        """Helper to create a dummy HTML file and return its chapter_info."""
        html_filename = f"{filename_prefix}_{chapter_order}.html"
        filepath = os.path.join(self.processed_content_dir, html_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "title": title,
            "local_processed_filename": html_filename,
            "download_order": chapter_order,
            "source_chapter_id": f"src_{chapter_order}" # Dummy source ID
        }

    def test_generate_single_epub_success(self):
        # 1. Create dummy processed HTML files
        chap1_info = self._create_dummy_html_file(
            "chap", 1, "Chapter 1: The Beginning", "<h1>Chapter 1</h1><p>Once upon a time...</p>"
        )
        chap2_info = self._create_dummy_html_file(
            "chap", 2, "Chapter 2: The Adventure", "<h1>Chapter 2</h1><p>The journey continues.</p>"
        )
        self.sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        # 2. Call generate_epub
        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)

        # 3. Assertions
        self.assertEqual(len(generated_files), 1, "Should generate one EPUB file.")
        epub_filepath = generated_files[0]
        self.assertTrue(os.path.exists(epub_filepath), f"EPUB file should exist at {epub_filepath}")
        self.assertTrue(epub_filepath.endswith(".epub"))
        self.assertIn(self.ebooks_dir, epub_filepath) # Check it's in the correct story's ebook dir

        # 4. Use epub.read_epub() and assert metadata
        book = epub.read_epub(epub_filepath)
        self.assertEqual(book.get_metadata('DC', 'title')[0][0], self.sample_progress_data["effective_title"])
        self.assertEqual(book.get_metadata('DC', 'creator')[0][0], self.sample_progress_data["author"])
        self.assertEqual(book.get_metadata('DC', 'language')[0][0], 'en')
        self.assertEqual(book.get_metadata('DC', 'identifier')[0][0], self.story_id)

        # 5. Assert number of chapters
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(content_chapters), 2, "EPUB should contain two content chapters.")

        # 6. Assert chapter titles and content (simplified check)
        # Note: Order in items might not be guaranteed, but usually is by add_item.
        # For robust check, map by file_name or title if possible.

        # Check chapter 1
        # Assuming content_chapters are now correctly ordered as per addition
        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        # Check for essential parts due to ebooklib HTML formatting
        self.assertIn("<h1>Chapter 1: The Beginning</h1>", epub_chap1_content)
        self.assertIn("<h1>Chapter 1</h1>", epub_chap1_content)
        self.assertIn("<p>Once upon a time...</p>", epub_chap1_content)

        # Check chapter 2
        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        self.assertIn("<h1>Chapter 2: The Adventure</h1>", epub_chap2_content)
        self.assertIn("<h1>Chapter 2</h1>", epub_chap2_content)
        self.assertIn("<p>The journey continues.</p>", epub_chap2_content)

        # Check TOC for titles (more reliable for chapter titles)
        toc_titles = [toc_item.title for toc_item in book.toc]
        self.assertIn("Chapter 1: The Beginning", toc_titles)
        self.assertIn("Chapter 2: The Adventure", toc_titles)


    def test_generate_epub_multiple_volumes(self):
        chap1 = self._create_dummy_html_file("c", 1, "Ch 1", "<p>Vol 1 Chap 1</p>")
        chap2 = self._create_dummy_html_file("c", 2, "Ch 2", "<p>Vol 1 Chap 2</p>")
        chap3 = self._create_dummy_html_file("c", 3, "Ch 3", "<p>Vol 2 Chap 1</p>")
        chap4 = self._create_dummy_html_file("c", 4, "Ch 4", "<p>Vol 2 Chap 2</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1, chap2, chap3, chap4]

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data, chapters_per_volume=2)

        self.assertEqual(len(generated_files), 2, "Should generate two EPUB files for two volumes.")

        sanitized_title = "My_Awesome_Story" # From progress_data["title"]
        expected_vol1_filename = f"{sanitized_title}_vol_1.epub"
        expected_vol2_filename = f"{sanitized_title}_vol_2.epub"

        found_vol1 = any(expected_vol1_filename in f for f in generated_files)
        found_vol2 = any(expected_vol2_filename in f for f in generated_files)
        self.assertTrue(found_vol1, f"Volume 1 EPUB ({expected_vol1_filename}) not found in {generated_files}")
        self.assertTrue(found_vol2, f"Volume 2 EPUB ({expected_vol2_filename}) not found in {generated_files}")

        # Verify Volume 1
        vol1_path = next(f for f in generated_files if expected_vol1_filename in f)
        book1 = epub.read_epub(vol1_path)
        self.assertEqual(book1.get_metadata('DC', 'title')[0][0], f"{self.sample_progress_data['effective_title']} Vol. 1")
        self.assertEqual(book1.get_metadata('DC', 'identifier')[0][0], f"{self.story_id}_vol_1")
        all_vol1_items = list(book1.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        vol1_content_chapters = [item for item in all_vol1_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(vol1_content_chapters), 2, "Volume 1 should have 2 content chapters.")
        vol1_content_chap1 = vol1_content_chapters[0].get_content().decode('utf-8')
        self.assertIn("<h1>Ch 1</h1>", vol1_content_chap1)
        self.assertIn("<p>Vol 1 Chap 1</p>", vol1_content_chap1)
        vol1_content_chap2 = vol1_content_chapters[1].get_content().decode('utf-8')
        self.assertIn("<h1>Ch 2</h1>", vol1_content_chap2)
        self.assertIn("<p>Vol 1 Chap 2</p>", vol1_content_chap2)
        vol1_toc_titles = [toc_item.title for toc_item in book1.toc]
        self.assertIn("Ch 1", vol1_toc_titles)
        self.assertIn("Ch 2", vol1_toc_titles)


        # Verify Volume 2
        vol2_path = next(f for f in generated_files if expected_vol2_filename in f)
        book2 = epub.read_epub(vol2_path)
        self.assertEqual(book2.get_metadata('DC', 'title')[0][0], f"{self.sample_progress_data['effective_title']} Vol. 2")
        self.assertEqual(book2.get_metadata('DC', 'identifier')[0][0], f"{self.story_id}_vol_2")
        all_vol2_items = list(book2.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        vol2_content_chapters = [item for item in all_vol2_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(vol2_content_chapters), 2, "Volume 2 should have 2 content chapters.")
        vol2_content_chap1 = vol2_content_chapters[0].get_content().decode('utf-8') # First chapter of this volume
        self.assertIn("<h1>Ch 3</h1>", vol2_content_chap1)
        self.assertIn("<p>Vol 2 Chap 1</p>", vol2_content_chap1)
        vol2_content_chap2 = vol2_content_chapters[1].get_content().decode('utf-8')
        self.assertIn("<h1>Ch 4</h1>", vol2_content_chap2)
        self.assertIn("<p>Vol 2 Chap 2</p>", vol2_content_chap2)
        vol2_toc_titles = [toc_item.title for toc_item in book2.toc]
        self.assertIn("Ch 3", vol2_toc_titles)
        self.assertIn("Ch 4", vol2_toc_titles)


    def test_generate_epub_no_chapters(self):
        self.sample_progress_data["downloaded_chapters"] = []
        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 0, "Should return an empty list if no chapters.")
        self.assertEqual(len(os.listdir(self.ebooks_dir)), 0, "No EPUB file should be created in ebooks_dir.")

    def test_generate_epub_missing_html_file(self):
        # Ensure this test also uses effective_title if it sets progress_data directly
        # For now, it relies on self.sample_progress_data, which will be fixed by the change above.
        chap1_info = self._create_dummy_html_file(
            "chap", 1, "Chapter 1", "<p>Content 1</p>"
        )
        # Chapter 2's HTML file will intentionally not be created
        chap2_info = {
            "title": "Chapter 2 - Missing",
            "local_processed_filename": "non_existent_chap_2.html", # This file won't exist
            "download_order": 2,
            "source_chapter_id": "src_2_missing"
        }
        chap3_info = self._create_dummy_html_file(
            "chap", 3, "Chapter 3", "<p>Content 3</p>"
        )
        self.sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info, chap3_info]

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)

        self.assertEqual(len(generated_files), 1, "One EPUB should still be generated.")
        epub_filepath = generated_files[0]
        self.assertTrue(os.path.exists(epub_filepath))

        book = epub.read_epub(epub_filepath)
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        # Should contain chapter 1 and chapter 3, skipping chapter 2
        self.assertEqual(len(content_chapters), 2, "EPUB should contain 2 content chapters, skipping the missing one.")

        toc_titles = [toc_item.title for toc_item in book.toc]
        self.assertIn("Chapter 1", toc_titles)
        self.assertNotIn("Chapter 2 - Missing", toc_titles)
        self.assertIn("Chapter 3", toc_titles)

        # Verify content of included chapters
        # Assuming content_chapters are now correctly ordered as per addition
        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        self.assertIn("<h1>Chapter 1</h1>", epub_chap1_content)
        self.assertIn("<p>Content 1</p>", epub_chap1_content)
        epub_chap3_content = content_chapters[1].get_content().decode('utf-8') # Now it's the second item
        self.assertIn("<h1>Chapter 3</h1>", epub_chap3_content)
        self.assertIn("<p>Content 3</p>", epub_chap3_content)


    def test_filename_sanitization(self):
        self.sample_progress_data["effective_title"] = "Story: The \"Best\" Title Ever!?" # Changed "title" to "effective_title"
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        epub_filepath = generated_files[0]

        expected_sanitized_filename_part = "Story__The__Best__Title_Ever__" # Based on current sanitization in EPUBGenerator
        # Full name: Story__The__Best__Title_Ever__.epub
        self.assertIn(expected_sanitized_filename_part, epub_filepath, "EPUB filename should be sanitized.")
        self.assertTrue(epub_filepath.endswith(".epub"))

    def test_generate_epub_one_volume_explicit_chapters_per_volume(self):
        """Test when chapters_per_volume is set but still results in one volume."""
        chap1_info = self._create_dummy_html_file("chap", 1, "Ch 1", "<p>C1</p>")
        chap2_info = self._create_dummy_html_file("chap", 2, "Ch 2", "<p>C2</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        # chapters_per_volume is >= total chapters, should result in one volume
        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data, chapters_per_volume=5)

        self.assertEqual(len(generated_files), 1, "Should generate one EPUB file.")
        epub_filepath = generated_files[0]
        book = epub.read_epub(epub_filepath)
        # Title should not have "Vol. X"
        self.assertEqual(book.get_metadata('DC', 'title')[0][0], self.sample_progress_data["effective_title"])
        # Identifier should not have "_vol_X"
        self.assertEqual(book.get_metadata('DC', 'identifier')[0][0], self.story_id)
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(content_chapters), 2, "EPUB should contain two content chapters.")

    def test_generate_epub_chapters_per_volume_zero_or_none(self):
        """Test that chapters_per_volume=0 or None creates a single volume."""
        chap1 = self._create_dummy_html_file("c", 1, "Ch 1", "<p>C1</p>")
        chap2 = self._create_dummy_html_file("c", 2, "Ch 2", "<p>C2</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1, chap2]

        # Test with chapters_per_volume = 0
        generated_files_zero = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data, chapters_per_volume=0)
        self.assertEqual(len(generated_files_zero), 1)
        book_zero = epub.read_epub(generated_files_zero[0])
        self.assertEqual(book_zero.get_metadata('DC', 'title')[0][0], self.sample_progress_data["effective_title"])
        self.assertEqual(book_zero.get_metadata('DC', 'identifier')[0][0], self.story_id)

        # Test with chapters_per_volume = None (already tested in test_generate_single_epub_success, but good for direct comparison)
        generated_files_none = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data, chapters_per_volume=None)
        self.assertEqual(len(generated_files_none), 1)
        book_none = epub.read_epub(generated_files_none[0])
        self.assertEqual(book_none.get_metadata('DC', 'title')[0][0], self.sample_progress_data["effective_title"])
        self.assertEqual(book_none.get_metadata('DC', 'identifier')[0][0], self.story_id)


if __name__ == '__main__':
    unittest.main()
