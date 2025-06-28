import pytest
import os
import shutil
import json
import datetime
import ebooklib
from ebooklib import epub
import io
import requests # Import requests for mocking
from pathlib import Path

from webnovel_archiver.core.builders.epub_generator import EPUBGenerator
from webnovel_archiver.core.path_manager import PathManager

# Mock requests.get for cover download
class MockResponse:
    def __init__(self, content, status_code, headers=None):
        self.content = content
        self.raw = io.BytesIO(content) # Make raw a file-like object
        self.status_code = status_code
        self.headers = headers if headers else {'content-type': 'image/jpeg'}

    def iter_content(self, chunk_size=8192):
        # Simulate yielding content in chunks
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("HTTP Error")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

def mock_requests_get_side_effect(url, stream=False):
    if "valid_cover.jpg" in url:
        image_content = b"dummy_image_bytes"
        return MockResponse(image_content, 200, {'content-type': 'image/jpeg'})
    elif "valid_cover.png" in url:
        image_content = b"dummy_png_bytes"
        return MockResponse(image_content, 200, {'content-type': 'image/png'})
    elif "download_fails" in url:
        raise requests.exceptions.RequestException("Simulated download failure")
    elif "http_error" in url:
        return MockResponse(None, 404)
    return MockResponse(None, 404)

@pytest.fixture
def setup_epub_generator(tmp_path, mocker):
    """
    Fixture to set up PathManager, EPUBGenerator, and mock requests.get.
    Uses tmp_path for isolated test directories.
    """
    test_workspace = tmp_path / "test_workspace_epub_generator"
    story_id = "test_story_001"
    path_manager = PathManager(str(test_workspace), story_id)

    # Ensure directories exist for the generator
    Path(path_manager.get_processed_content_story_dir()).mkdir(parents=True, exist_ok=True)
    Path(path_manager.get_ebooks_story_dir()).mkdir(parents=True, exist_ok=True)

    epub_generator = EPUBGenerator(path_manager)

    # Mock requests.get for cover download tests
    mocker.patch('requests.get', side_effect=mock_requests_get_side_effect)

    return {
        "path_manager": path_manager,
        "epub_generator": epub_generator,
        "test_workspace": test_workspace,
        "story_id": story_id
    }

@pytest.fixture
def sample_progress_data():
    """Fixture for a base sample progress data dictionary."""
    return {
        "effective_title": "My Awesome Story",
        "author": "Test Author",
        "story_id": "test_story_001",
        "downloaded_chapters": [],
        "synopsis": None,
        "cover_image_url": None
    }

@pytest.fixture
def create_dummy_html_file(setup_epub_generator):
    """Helper fixture to create a dummy HTML file and return its chapter_info."""
    processed_content_dir = setup_epub_generator["path_manager"].get_processed_content_story_dir()

    def _creator(filename_prefix: str, chapter_order: int, title: str, content: str, status: str = "active") -> dict:
        html_filename = f"{filename_prefix}_{chapter_order}.html"
        filepath = Path(processed_content_dir) / html_filename
        filepath.write_text(content, encoding="utf-8")
        return {
            "title": title,
            "local_processed_filename": html_filename,
            "download_order": chapter_order,
            "source_chapter_id": f"src_{chapter_order}",
            "status": status
        }
    return _creator

class TestEPUBGenerator:
    def test_generate_single_epub_success(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        chap1_info = create_dummy_html_file(
            "chap", 1, "Chapter 1: The Beginning", "<h1>Chapter 1</h1><p>Once upon a time...</p>"
        )
        chap2_info = create_dummy_html_file(
            "chap", 2, "Chapter 2: The Adventure", "<h1>Chapter 2</h1><p>The journey continues.</p>"
        )
        sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)

        assert len(generated_files) == 1, "Should generate one EPUB file."
        epub_filepath = Path(generated_files[0])
        assert epub_filepath.exists(), f"EPUB file should exist at {epub_filepath}"
        assert epub_filepath.suffix == ".epub"
        assert Path(ebooks_dir) in epub_filepath.parents # Check it's in the correct story's ebook dir

        book = epub.read_epub(str(epub_filepath))
        assert book.get_metadata('DC', 'title')[0][0] == sample_progress_data["effective_title"]
        assert book.get_metadata('DC', 'creator')[0][0] == sample_progress_data["author"]
        assert book.get_metadata('DC', 'language')[0][0] == 'en'
        assert book.get_metadata('DC', 'identifier')[0][0] == sample_progress_data["story_id"]

        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        assert len(content_chapters) == 2, "EPUB should contain two content chapters."

        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Chapter 1: The Beginning</h1>" in epub_chap1_content
        assert "<h1>Chapter 1</h1>" in epub_chap1_content
        assert "<p>Once upon a time...</p>" in epub_chap1_content

        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        assert "<h1>Chapter 2: The Adventure</h1>" in epub_chap2_content
        assert "<h1>Chapter 2</h1>" in epub_chap2_content
        assert "<p>The journey continues.</p>" in epub_chap2_content

        toc_titles = [toc_item.title for toc_item in book.toc]
        assert "Chapter 1: The Beginning" in toc_titles
        assert "Chapter 2: The Adventure" in toc_titles

    def test_generate_epub_multiple_volumes(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        story_id = setup_epub_generator["story_id"]

        chap1 = create_dummy_html_file("c", 1, "Ch 1", "<p>Vol 1 Chap 1</p>")
        chap2 = create_dummy_html_file("c", 2, "Ch 2", "<p>Vol 1 Chap 2</p>")
        chap3 = create_dummy_html_file("c", 3, "Ch 3", "<p>Vol 2 Chap 1</p>")
        chap4 = create_dummy_html_file("c", 4, "Ch 4", "<p>Vol 2 Chap 2</p>")
        sample_progress_data["downloaded_chapters"] = [chap1, chap2, chap3, chap4]

        generated_files = epub_generator.generate_epub(sample_progress_data, chapters_per_volume=2)

        assert len(generated_files) == 2, "Should generate two EPUB files for two volumes."

        sanitized_title = "My_Awesome_Story"
        expected_vol1_filename = f"{sanitized_title}_vol_1.epub"
        expected_vol2_filename = f"{sanitized_title}_vol_2.epub"

        found_vol1 = any(expected_vol1_filename in f for f in generated_files)
        found_vol2 = any(expected_vol2_filename in f for f in generated_files)
        assert found_vol1, f"Volume 1 EPUB ({expected_vol1_filename}) not found in {generated_files}"
        assert found_vol2, f"Volume 2 EPUB ({expected_vol2_filename}) not found in {generated_files}"

        vol1_path = Path(next(f for f in generated_files if expected_vol1_filename in f))
        book1 = epub.read_epub(str(vol1_path))
        assert book1.get_metadata('DC', 'title')[0][0] == f"{sample_progress_data['effective_title']} Vol. 1"
        assert book1.get_metadata('DC', 'identifier')[0][0] == f"{story_id}_vol_1"
        all_vol1_items = list(book1.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        vol1_content_chapters = [item for item in all_vol1_items if item.get_name() != 'nav.xhtml']
        assert len(vol1_content_chapters) == 2, "Volume 1 should have 2 content chapters."
        vol1_content_chap1 = vol1_content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Ch 1</h1>" in vol1_content_chap1
        assert "<p>Vol 1 Chap 1</p>" in vol1_content_chap1
        vol1_content_chap2 = vol1_content_chapters[1].get_content().decode('utf-8')
        assert "<h1>Ch 2</h1>" in vol1_content_chap2
        assert "<p>Vol 1 Chap 2</p>" in vol1_content_chap2
        vol1_toc_titles = [toc_item.title for toc_item in book1.toc]
        assert "Ch 1" in vol1_toc_titles
        assert "Ch 2" in vol1_toc_titles

        vol2_path = Path(next(f for f in generated_files if expected_vol2_filename in f))
        book2 = epub.read_epub(str(vol2_path))
        assert book2.get_metadata('DC', 'title')[0][0] == f"{sample_progress_data['effective_title']} Vol. 2"
        assert book2.get_metadata('DC', 'identifier')[0][0] == f"{story_id}_vol_2"
        all_vol2_items = list(book2.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        vol2_content_chapters = [item for item in all_vol2_items if item.get_name() != 'nav.xhtml']
        assert len(vol2_content_chapters) == 2, "Volume 2 should have 2 content chapters."
        vol2_content_chap1 = vol2_content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Ch 3</h1>" in vol2_content_chap1
        assert "<p>Vol 2 Chap 1</p>" in vol2_content_chap1
        vol2_content_chap2 = vol2_content_chapters[1].get_content().decode('utf-8')
        assert "<h1>Ch 4</h1>" in vol2_content_chap2
        assert "<p>Vol 2 Chap 2</p>" in vol2_content_chap2
        vol2_toc_titles = [toc_item.title for toc_item in book2.toc]
        assert "Ch 3" in vol2_toc_titles
        assert "Ch 4" in vol2_toc_titles

    def test_generate_epub_no_chapters(self, setup_epub_generator, sample_progress_data):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        sample_progress_data["downloaded_chapters"] = []
        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 0, "Should return an empty list if no chapters."
        assert len(list(Path(ebooks_dir).iterdir())) == 0, "No EPUB file should be created in ebooks_dir."

    def test_generate_epub_missing_html_file(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file(
            "chap", 1, "Chapter 1", "<p>Content 1</p>"
        )
        chap2_info = {
            "title": "Chapter 2 - Missing",
            "local_processed_filename": "non_existent_chap_2.html",
            "download_order": 2,
            "source_chapter_id": "src_2_missing"
        }
        chap3_info = create_dummy_html_file(
            "chap", 3, "Chapter 3", "<p>Content 3</p>"
        )
        sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info, chap3_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)

        assert len(generated_files) == 1, "One EPUB should still be generated."
        epub_filepath = Path(generated_files[0])
        assert epub_filepath.exists()

        book = epub.read_epub(str(epub_filepath))
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        assert len(content_chapters) == 2, "EPUB should contain 2 content chapters, skipping the missing one."

        toc_titles = [toc_item.title for toc_item in book.toc]
        assert "Chapter 1" in toc_titles
        assert "Chapter 2 - Missing" not in toc_titles
        assert "Chapter 3" in toc_titles

        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Chapter 1</h1>" in epub_chap1_content
        assert "<p>Content 1</p>" in epub_chap1_content
        epub_chap3_content = content_chapters[1].get_content().decode('utf-8')
        assert "<h1>Chapter 3</h1>" in epub_chap3_content
        assert "<p>Content 3</p>" in epub_chap3_content

    def test_filename_sanitization(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        sample_progress_data["effective_title"] = "Story: The \"Best\" Title Ever!?"
        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        epub_filepath = Path(generated_files[0])

        expected_sanitized_filename_part = "Story__The__Best__Title_Ever__"
        assert expected_sanitized_filename_part in str(epub_filepath), "EPUB filename should be sanitized."
        assert epub_filepath.suffix == ".epub"

    def test_generate_epub_one_volume_explicit_chapters_per_volume(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        story_id = setup_epub_generator["story_id"]

        chap1_info = create_dummy_html_file("chap", 1, "Ch 1", "<p>C1</p>")
        chap2_info = create_dummy_html_file("chap", 2, "Ch 2", "<p>C2</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        generated_files = epub_generator.generate_epub(sample_progress_data, chapters_per_volume=5)

        assert len(generated_files) == 1, "Should generate one EPUB file."
        epub_filepath = Path(generated_files[0])
        book = epub.read_epub(str(epub_filepath))
        assert book.get_metadata('DC', 'title')[0][0] == sample_progress_data["effective_title"]
        assert book.get_metadata('DC', 'identifier')[0][0] == story_id
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        assert len(content_chapters) == 2, "EPUB should contain two content chapters."

    def test_generate_epub_chapters_per_volume_zero_or_none(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        story_id = setup_epub_generator["story_id"]

        chap1 = create_dummy_html_file("c", 1, "Ch 1", "<p>C1</p>")
        chap2 = create_dummy_html_file("c", 2, "Ch 2", "<p>C2</p>")
        sample_progress_data["downloaded_chapters"] = [chap1, chap2]

        generated_files_zero = epub_generator.generate_epub(sample_progress_data, chapters_per_volume=0)
        assert len(generated_files_zero) == 1
        book_zero = epub.read_epub(str(generated_files_zero[0]))
        assert book_zero.get_metadata('DC', 'title')[0][0] == sample_progress_data["effective_title"]
        assert book_zero.get_metadata('DC', 'identifier')[0][0] == story_id

        generated_files_none = epub_generator.generate_epub(sample_progress_data, chapters_per_volume=None)
        assert len(generated_files_none) == 1
        book_none = epub.read_epub(str(generated_files_none[0]))
        assert book_none.get_metadata('DC', 'title')[0][0] == sample_progress_data["effective_title"]
        assert book_none.get_metadata('DC', 'identifier')[0][0] == story_id

    def test_generate_epub_with_archived_chapters(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file(
            "chap", 1, "Chapter 1 Title", "<h1>Chapter 1</h1><p>Active content.</p>", status="active"
        )
        chap2_info = create_dummy_html_file(
            "chap", 2, "Chapter 2 Title", "<h1>Chapter 2</h1><p>Archived content.</p>", status="archived"
        )
        chap3_info = create_dummy_html_file(
            "chap", 3, "Chapter 3 Title", "<h1>Chapter 3</h1><p>More active content.</p>", status="active"
        )
        sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info, chap3_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)

        assert len(generated_files) == 1, "Should generate one EPUB file."
        epub_filepath = Path(generated_files[0])
        assert epub_filepath.exists()

        book = epub.read_epub(str(epub_filepath))
        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        assert len(content_chapters) == 3, "EPUB should contain three content chapters."

        toc_titles = {item.title: item for item in book.toc}
        assert "Chapter 1 Title" in toc_titles
        assert "[Archived] Chapter 2 Title" in toc_titles
        assert "Chapter 3 Title" in toc_titles

        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Chapter 1 Title</h1>" in epub_chap1_content
        assert "[Archived]" not in epub_chap1_content

        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        assert "<h1>[Archived] Chapter 2 Title</h1>" in epub_chap2_content

        epub_chap3_content = content_chapters[2].get_content().decode('utf-8')
        assert "<h1>Chapter 3 Title</h1>" in epub_chap3_content
        assert "[Archived]" not in epub_chap3_content

    def test_generate_epub_active_only_chapters(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file(
            "chap", 1, "Active Chapter 1", "<p>Content 1</p>", status="active"
        )
        chap2_info = create_dummy_html_file(
            "chap", 2, "Active Chapter 2", "<p>Content 2</p>", status="active"
        )
        sample_progress_data["downloaded_chapters"] = [chap1_info, chap2_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)

        assert len(generated_files) == 1
        epub_filepath = Path(generated_files[0])
        book = epub.read_epub(str(epub_filepath))

        all_items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
        content_chapters = [item for item in all_items if item.get_name() != 'nav.xhtml']
        assert len(content_chapters) == 2

        toc_titles = [item.title for item in book.toc]
        assert "Active Chapter 1" in toc_titles
        assert "[Archived] Active Chapter 1" not in toc_titles
        assert "Active Chapter 2" in toc_titles
        assert "[Archived] Active Chapter 2" not in toc_titles

        epub_chap1_content = content_chapters[0].get_content().decode('utf-8')
        assert "<h1>Active Chapter 1</h1>" in epub_chap1_content
        assert "[Archived]" not in epub_chap1_content

        epub_chap2_content = content_chapters[1].get_content().decode('utf-8')
        assert "<h1>Active Chapter 2</h1>" in epub_chap2_content
        assert "[Archived]" not in epub_chap2_content

    def test_generate_epub_with_synopsis(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content 1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["synopsis"] = "This is a test synopsis."

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        epub_filepath = Path(generated_files[0])
        book = epub.read_epub(str(epub_filepath))

        toc_links = {link.title: link for link in book.toc}
        assert "Synopsis" in toc_links, "Synopsis should be in TOC."

        toc_links = {link.title: link for link in book.toc}
        assert "Synopsis" in toc_links, "Synopsis should be in TOC."

        synopsis_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml"), None)
        assert synopsis_item is not None, "Synopsis XHTML item not found."
        synopsis_content = synopsis_item.get_content().decode('utf-8')
        assert "<h1>Synopsis</h1>" in synopsis_content
        assert "<p>This is a test synopsis.</p>" in synopsis_content

    def test_generate_epub_with_cover_image(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>Content 1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.jpg"

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        epub_filepath = Path(generated_files[0])
        book = epub.read_epub(str(epub_filepath))

        cover_meta = book.get_metadata('OPF', 'cover')
        assert len(cover_meta) > 0, "Cover metadata should exist."

        # Debugging: Print all items to see their IDs and media types
        # for item in book.get_items():
        #     print(f"Item ID: {item.id}, File Name: {item.file_name}, Media Type: {item.media_type}")

        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        assert cover_xhtml_item is not None, "cover.xhtml page was not created by set_cover."
        cover_xhtml_content = cover_xhtml_item.get_content().decode('utf-8')
        assert '<img src="../images/cover.jpg"' in cover_xhtml_content or '<img src="cover.jpg"' in cover_xhtml_content, "Cover image not referenced in cover.xhtml"

        temp_cover_dir = Path(ebooks_dir) / PathManager.TEMP_COVER_DIR_NAME
        assert not temp_cover_dir.exists(), "Temporary cover directory should be cleaned up."

    def test_generate_epub_with_synopsis_and_cover(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["synopsis"] = "A great story indeed."
        sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.png"

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        book = epub.read_epub(str(generated_files[0]))

        assert "Synopsis" in [link.title for link in book.toc]
        synopsis_item = next(item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml")
        assert "<h1>Synopsis</h1>" in synopsis_item.get_content().decode('utf-8')
        assert "<p>A great story indeed.</p>" in synopsis_item.get_content().decode('utf-8')

        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        assert cover_xhtml_item is not None, "cover.xhtml page was not created by set_cover."
        cover_xhtml_content = cover_xhtml_item.get_content().decode('utf-8')
        assert '<img src="../images/cover.png"' in cover_xhtml_content or '<img src="cover.png"' in cover_xhtml_content, "Cover image not referenced in cover.xhtml"

        temp_cover_dir = Path(ebooks_dir) / PathManager.TEMP_COVER_DIR_NAME
        assert not temp_cover_dir.exists(), "Temp cover dir should be gone."

    def test_cover_download_failure_http_error(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["cover_image_url"] = "http://example.com/http_error"

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        book = epub.read_epub(str(generated_files[0]))

        assert book.get_item_with_id('cover') is None
        assert book.get_item_with_href('cover.jpg') is None
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        assert cover_xhtml_item is None, "cover.xhtml page should not have been created on download failure."

        temp_cover_file = Path(ebooks_dir) / PathManager.TEMP_COVER_DIR_NAME / "cover.jpg"
        assert not temp_cover_file.exists(), "Temporary cover file should not exist on download failure."

    def test_cover_download_failure_request_exception(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["cover_image_url"] = "http://example.com/download_fails"

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        book = epub.read_epub(str(generated_files[0]))

        assert book.get_item_with_id('cover') is None
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        assert cover_xhtml_item is None, "cover.xhtml page should not have been created on request exception."

    def test_no_synopsis_no_cover(self, setup_epub_generator, sample_progress_data, create_dummy_html_file):
        epub_generator = setup_epub_generator["epub_generator"]

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]

        generated_files = epub_generator.generate_epub(sample_progress_data)
        assert len(generated_files) == 1
        book = epub.read_epub(str(generated_files[0]))

        assert "Synopsis" not in [link.title for link in book.toc]
        synopsis_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if item.get_name() == "synopsis.xhtml"), None)
        assert synopsis_item is None

        assert book.get_item_with_id('cover') is None
        cover_xhtml_item = next((item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT) if 'cover' in item.get_name().lower() and item.get_name().endswith('.xhtml')), None)
        assert cover_xhtml_item is None

        spine_file_names = [item[0] if isinstance(item[0], str) else item[0].uid for item in book.spine]
        assert spine_file_names == ['nav', 'chapter_1']

    def test_epub_generation_continues_if_cover_save_fails(self, setup_epub_generator, sample_progress_data, create_dummy_html_file, mocker):
        epub_generator = setup_epub_generator["epub_generator"]
        ebooks_dir = setup_epub_generator["path_manager"].get_ebooks_story_dir()

        chap1_info = create_dummy_html_file("chap", 1, "Chapter 1", "<p>C1</p>")
        sample_progress_data["downloaded_chapters"] = [chap1_info]
        sample_progress_data["cover_image_url"] = "http://example.com/valid_cover.jpg"

        # Mock open to raise IOError when writing the cover file
        original_open = open # Store original open
        def mock_open_side_effect(file, mode='r', *args, **kwargs):
            if 'cover.jpg' in str(file) and 'wb' in mode:
                raise IOError("Simulated failed to save cover")
            return original_open(file, mode, *args, **kwargs)
        mocker.patch('builtins.open', side_effect=mock_open_side_effect)

        # Mock os.makedirs as it might be called before open
        mocker.patch('os.makedirs')

        generated_files = epub_generator.generate_epub(sample_progress_data)

        assert len(generated_files) == 1, "EPUB should still be generated even if cover saving fails."
        book = epub.read_epub(str(generated_files[0]))
        assert book.get_item_with_id('cover') is None, "Cover should not be set if saving failed."

        temp_cover_file = Path(ebooks_dir) / PathManager.TEMP_COVER_DIR_NAME / "cover.jpg"
        assert not temp_cover_file.exists(), "Temporary cover file should not exist if save failed."