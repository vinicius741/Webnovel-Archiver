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
import unittest.mock # Ensure unittest.mock is imported for patching
# import logging
# logging.getLogger('webnovel_archiver').setLevel(logging.CRITICAL)

# Mock requests.get for cover download
class MockResponse: # Already defined, no change
    def __init__(self, content, status_code, headers=None):
        self.content = content
        self.raw = content
        self.status_code = status_code
        self.headers = headers if headers else {'content-type': 'image/jpeg'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

def mock_requests_get(url, stream=False):
    if "valid_cover.jpg" in url:
        # Simulate a successful image download
        image_content = b"dummy_image_bytes" # Simulate image data
        return MockResponse(image_content, 200, {'content-type': 'image/jpeg'})
    elif "valid_cover.png" in url:
        image_content = b"dummy_png_bytes"
        return MockResponse(image_content, 200, {'content-type': 'image/png'})
    elif "download_fails" in url:
        raise requests.exceptions.RequestException("Simulated download failure")
    elif "http_error" in url:
        return MockResponse(None, 404)
    return MockResponse(None, 404) # Default to 404 for unknown URLs


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
            "downloaded_chapters": [],
            "synopsis": None, # Ensure it's part of the base sample data
            "cover_image_url": None # Ensure it's part of the base sample data
        }

        # Patch requests.get for cover download tests
        self.patcher = unittest.mock.patch('requests.get', side_effect=mock_requests_get)
        self.mock_get = self.patcher.start()


    def tearDown(self):
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace)
        self.patcher.stop() # Stop the patcher

    def _create_dummy_html_file(self, filename_prefix: str, chapter_order: int, title: str, content: str, status: str = "active") -> dict:
        """Helper to create a dummy HTML file and return its chapter_info."""
        html_filename = f"{filename_prefix}_{chapter_order}.html"
        filepath = os.path.join(self.processed_content_dir, html_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "title": title,
            "local_processed_filename": html_filename,
            "download_order": chapter_order,
            "source_chapter_id": f"src_{chapter_order}", # Dummy source ID
            "status": status
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


    def test_generate_epub_with_archived_chapters(self):
        chap1_info = self._create_dummy_html_file(
            "chap", 1, "Chapter 1 Title", "<h1>Chapter 1</h1><p>Active content.</p>", status="active"
        )
        chap2_info = self._create_dummy_html_file(
            "chap", 2, "Chapter 2 Title", "<h1>Chapter 2</h1><p>Archived content.</p>", status="archived"
        )
        chap3_info = self._create_dummy_html_file(
            "chap", 3, "Chapter 3 Title", "<h1>Chapter 3</h1><p>More active content.</p>", status="active"
        )
        self.sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info, chap3_info]

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)

        self.assertEqual(len(generated_files), 1, "Should generate one EPUB file.")
        epub_filepath = generated_files[0]
        self.assertTrue(os.path.exists(epub_filepath))

        book = epub.read_epub(epub_filepath)
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(content_chapters), 3, "EPUB should contain three content chapters.")

        toc_titles = {item.title: item for item in book.toc} # Use dict for easier lookup

        self.assertIn("Chapter 1 Title", toc_titles)
        self.assertIn("[Archived] Chapter 2 Title", toc_titles)
        self.assertIn("Chapter 3 Title", toc_titles)

        # Check H1 tags in content
        # Order of content_chapters should match download_order
        # Chapter 1
        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        self.assertIn("<h1>Chapter 1 Title</h1>", epub_chap1_content) # Original title in H1
        self.assertNotIn("[Archived]", epub_chap1_content)

        # Chapter 2
        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        self.assertIn("<h1>[Archived] Chapter 2 Title</h1>", epub_chap2_content) # Archived title in H1

        # Chapter 3
        epub_chap3_content = content_chapters[2].get_content().decode('utf-8')
        self.assertIn("<h1>Chapter 3 Title</h1>", epub_chap3_content) # Original title in H1
        self.assertNotIn("[Archived]", epub_chap3_content)


    def test_generate_epub_active_only_chapters(self):
        chap1_info = self._create_dummy_html_file(
            "chap", 1, "Active Chapter 1", "<p>Content 1</p>", status="active"
        )
        chap2_info = self._create_dummy_html_file(
            "chap", 2, "Active Chapter 2", "<p>Content 2</p>", status="active"
        )
        self.sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)

        self.assertEqual(len(generated_files), 1)
        epub_filepath = generated_files[0]
        book = epub.read_epub(epub_filepath)

        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        self.assertEqual(len(content_chapters), 2)

        toc_titles = [item.title for item in book.toc]
        self.assertIn("Active Chapter 1", toc_titles)
        self.assertNotIn("[Archived] Active Chapter 1", toc_titles)
        self.assertIn("Active Chapter 2", toc_titles)
        self.assertNotIn("[Archived] Active Chapter 2", toc_titles)

        # Check H1 tags
        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        self.assertIn("<h1>Active Chapter 1</h1>", epub_chap1_content)
        self.assertNotIn("[Archived]", epub_chap1_content)

        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        self.assertIn("<h1>Active Chapter 2</h1>", epub_chap2_content)
        self.assertNotIn("[Archived]", epub_chap2_content)


    def test_generate_epub_with_synopsis(self):
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content 1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["synopsis"] = "This is a test synopsis."

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        epub_filepath = generated_files[0]
        book = epub.read_epub(epub_filepath)

        # Check for synopsis in TOC
        toc_links = {link.title: link for link in book.toc}
        self.assertIn("Synopsis", toc_links, "Synopsis should be in TOC.")

        # Check for synopsis in spine (order)
        # Spine items are EpubItem objects, check their file_name
        spine_file_names = [item.file_name for item in book.spine]
        self.assertIn("synopsis.xhtml", spine_file_names, "Synopsis xhtml should be in spine.")
        nav_index = spine_file_names.index("nav.xhtml") # nav.xhtml is from ebooklib
        synopsis_index = spine_file_names.index("synopsis.xhtml")
        chapter_index = spine_file_names.index("chap_1.xhtml")

        self.assertTrue(nav_index < synopsis_index < chapter_index, "Synopsis should be after nav and before chapters in spine.")

        # Check synopsis content
        synopsis_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml"), None)
        self.assertIsNotNone(synopsis_item, "Synopsis XHTML item not found.")
        synopsis_content = synopsis_item.get_content().decode('utf-8')
        self.assertIn("<h1>Synopsis</h1>", synopsis_content)
        self.assertIn("<p>This is a test synopsis.</p>", synopsis_content)


    def test_generate_epub_with_cover_image(self):
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content 1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.jpg" # Mocked to succeed

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        epub_filepath = generated_files[0]
        book = epub.read_epub(epub_filepath)

        # Check cover metadata
        cover_meta = book.get_metadata('OPF', 'cover')
        self.assertTrue(len(cover_meta) > 0, "Cover metadata should exist.")
        # ebooklib < 0.18 uses ('OPF', 'cover'), id='cover-image', content='cover.jpg'
        # ebooklib >= 0.18 might use other forms or rely on guide items.
        # A more robust check is to look for the cover image item itself.

        cover_image_item = book.get_item_with_id('cover') # Default ID by set_cover if not specified
        if not cover_image_item: # try common filename if ID 'cover' is not used
            cover_image_item = book.get_item_with_href('cover.jpg') # if filename is cover.jpg

        self.assertIsNotNone(cover_image_item, "Cover image item not found in EPUB.")
        self.assertEqual(cover_image_item.get_media_type(), 'image/jpeg')

        # Check if cover.xhtml (created by set_cover create_page=True) exists
        # Note: The prompt did not explicitly ask for create_page=True to be tested,
        # but the implementation uses it.
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        self.assertIsNotNone(cover_xhtml_item, "cover.xhtml page was not created by set_cover.")

        # Check temp cover directory is cleaned up
        temp_cover_dir = os.path.join(self.ebooks_dir, self.epub_generator.temp_cover_dir_name)
        self.assertFalse(os.path.exists(temp_cover_dir), "Temporary cover directory should be cleaned up.")


    def test_generate_epub_with_synopsis_and_cover(self):
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["synopsis"] = "A great story indeed."
        self.sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.png" # Use PNG

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        book = epub.read_epub(generated_files[0])

        # Synopsis checks
        self.assertIn("Synopsis", [link.title for link in book.toc])
        synopsis_item = next(item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml")
        self.assertIn("<h1>Synopsis</h1>", synopsis_item.get_content().decode('utf-8'))
        self.assertIn("<p>A great story indeed.</p>", synopsis_item.get_content().decode('utf-8'))

        # Cover checks
        cover_image_item = book.get_item_with_id('cover')
        if not cover_image_item:
             cover_image_item = book.get_item_with_href('cover.png')
        self.assertIsNotNone(cover_image_item)
        self.assertEqual(cover_image_item.get_media_type(), 'image/png')
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        self.assertIsNotNone(cover_xhtml_item, "cover.xhtml page was not created by set_cover.")


        # Spine order: nav, (optional cover.xhtml), synopsis, chapter
        spine_file_names = [item.file_name for item in book.spine]
        nav_idx = spine_file_names.index('nav.xhtml')
        # cover_xhtml_idx = spine_file_names.index('cover.xhtml') # If set_cover creates it AND it's added to spine
        synopsis_idx = spine_file_names.index('synopsis.xhtml')
        chap_idx = spine_file_names.index('chap_1.xhtml')

        self.assertTrue(nav_idx < synopsis_idx < chap_idx)
        # If cover.xhtml is part of spine: self.assertTrue(nav_idx < cover_xhtml_idx < synopsis_idx < chap_idx)
        # Current implementation does not add cover.xhtml to spine explicitly, relies on set_cover behavior.

        temp_cover_dir = os.path.join(self.ebooks_dir, self.epub_generator.temp_cover_dir_name)
        self.assertFalse(os.path.exists(temp_cover_dir), "Temp cover dir should be gone.")


    def test_cover_download_failure_http_error(self):
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["cover_image_url"] = "http://example.com/http_error" # Mocked to cause HTTP error

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        book = epub.read_epub(generated_files[0])

        # No cover should be set
        self.assertIsNone(book.get_item_with_id('cover'))
        self.assertIsNone(book.get_item_with_href('cover.jpg')) # Or any other cover name
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        self.assertIsNone(cover_xhtml_item, "cover.xhtml page should not have been created on download failure.")

        temp_cover_dir = os.path.join(self.ebooks_dir, self.epub_generator.temp_cover_dir_name, "cover.jpg") # specific file
        self.assertFalse(os.path.exists(temp_cover_dir), "Temporary cover file should not exist on download failure.")


    def test_cover_download_failure_request_exception(self):
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["cover_image_url"] = "http://example.com/download_fails" # Mocked to raise RequestException

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1) # EPUB should still be generated
        book = epub.read_epub(generated_files[0])

        self.assertIsNone(book.get_item_with_id('cover'))
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        self.assertIsNone(cover_xhtml_item, "cover.xhtml page should not have been created on request exception.")


    def test_no_synopsis_no_cover(self):
        """Test basic EPUB generation when synopsis and cover_image_url are None (default)."""
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        # "synopsis" and "cover_image_url" are already None in self.sample_progress_data by default setUp

        generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)
        self.assertEqual(len(generated_files), 1)
        book = epub.read_epub(generated_files[0])

        # No synopsis page
        self.assertNotIn("Synopsis", [link.title for link in book.toc])
        synopsis_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml"), None)
        self.assertIsNone(synopsis_item)

        # No cover
        self.assertIsNone(book.get_item_with_id('cover'))
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        self.assertIsNone(cover_xhtml_item)

        # Spine should just have nav and chapter
        spine_file_names = [item.file_name for item in book.spine]
        self.assertEqual(spine_file_names, ['nav.xhtml', 'chap_1.xhtml'])


    def test_epub_generation_continues_if_cover_save_fails(self):
        # This test requires mocking open() to simulate an IOError during cover saving
        # This is a bit more involved.
        chap1_info = self._create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        self.sample_progress_data["downloaded_chapters"] = [chap1_info]
        self.sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.jpg"

        original_open = open
        def mock_open_failure(*args, **kwargs):
            if 'cover.jpg' in args[0] and 'wb' in args[1]: # Target the cover image write
                raise IOError("Simulated failed to save cover")
            return original_open(*args, **kwargs)

        with unittest.mock.patch('builtins.open', side_effect=mock_open_failure):
            with unittest.mock.patch('os.makedirs'): # Mock makedirs as it might be called before open
                generated_files = self.epub_generator.generate_epub(self.story_id, self.sample_progress_data)

        self.assertEqual(len(generated_files), 1, "EPUB should still be generated even if cover saving fails.")
        book = epub.read_epub(generated_files[0])
        self.assertIsNone(book.get_item_with_id('cover'), "Cover should not be set if saving failed.")
        # Check that the temporary cover directory is cleaned up or doesn't exist
        temp_cover_file = os.path.join(self.ebooks_dir, self.epub_generator.temp_cover_dir_name, "cover.jpg")
        self.assertFalse(os.path.exists(temp_cover_file), "Temp cover file should not exist if save failed.")
