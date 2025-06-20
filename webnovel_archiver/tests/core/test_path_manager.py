import unittest
import os
from webnovel_archiver.core.path_manager import PathManager

class TestPathManager(unittest.TestCase):

    def setUp(self):
        self.workspace_root = "test_workspace"
        self.story_id = "test_story_123"
        self.pm = PathManager(self.workspace_root, self.story_id)

    def test_initialization(self):
        self.assertEqual(self.pm.get_workspace_root(), self.workspace_root)
        self.assertEqual(self.pm.get_story_id(), self.story_id)
        with self.assertRaises(ValueError):
            PathManager("", "some_id")
        with self.assertRaises(ValueError):
            PathManager("some_root", "")

    def test_get_raw_content_story_dir(self):
        expected = os.path.join(self.workspace_root, PathManager.RAW_CONTENT_DIR_NAME, self.story_id)
        self.assertEqual(self.pm.get_raw_content_story_dir(), expected)

    def test_get_raw_content_chapter_filepath(self):
        filename = "chapter_raw.html"
        expected = os.path.join(self.workspace_root, PathManager.RAW_CONTENT_DIR_NAME, self.story_id, filename)
        self.assertEqual(self.pm.get_raw_content_chapter_filepath(filename), expected)
        with self.assertRaises(ValueError):
            self.pm.get_raw_content_chapter_filepath("")

    def test_get_processed_content_story_dir(self):
        expected = os.path.join(self.workspace_root, PathManager.PROCESSED_CONTENT_DIR_NAME, self.story_id)
        self.assertEqual(self.pm.get_processed_content_story_dir(), expected)

    def test_get_processed_content_chapter_filepath(self):
        filename = "chapter_processed.html"
        expected = os.path.join(self.workspace_root, PathManager.PROCESSED_CONTENT_DIR_NAME, self.story_id, filename)
        self.assertEqual(self.pm.get_processed_content_chapter_filepath(filename), expected)
        with self.assertRaises(ValueError):
            self.pm.get_processed_content_chapter_filepath("")

    def test_get_archival_status_story_dir(self):
        expected = os.path.join(self.workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME, self.story_id)
        self.assertEqual(self.pm.get_archival_status_story_dir(), expected)

    def test_get_progress_filepath(self):
        expected = os.path.join(self.workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME, self.story_id, PathManager.PROGRESS_FILENAME)
        self.assertEqual(self.pm.get_progress_filepath(), expected)

    def test_get_ebooks_story_dir(self):
        expected = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME, self.story_id)
        self.assertEqual(self.pm.get_ebooks_story_dir(), expected)

    def test_get_epub_filepath(self):
        filename = "story.epub"
        expected = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME, self.story_id, filename)
        self.assertEqual(self.pm.get_epub_filepath(filename), expected)
        with self.assertRaises(ValueError):
            self.pm.get_epub_filepath("")

    def test_get_temp_cover_story_dir(self):
        expected = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME, self.story_id, PathManager.TEMP_COVER_DIR_NAME)
        self.assertEqual(self.pm.get_temp_cover_story_dir(), expected)

    def test_get_cover_image_filepath(self):
        filename = "cover.jpg"
        expected = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME, self.story_id, PathManager.TEMP_COVER_DIR_NAME, filename)
        self.assertEqual(self.pm.get_cover_image_filepath(filename), expected)
        with self.assertRaises(ValueError):
            self.pm.get_cover_image_filepath("")

    def test_get_base_directory(self):
        expected_raw = os.path.join(self.workspace_root, PathManager.RAW_CONTENT_DIR_NAME)
        self.assertEqual(self.pm.get_base_directory(PathManager.RAW_CONTENT_DIR_NAME), expected_raw)

        expected_processed = os.path.join(self.workspace_root, PathManager.PROCESSED_CONTENT_DIR_NAME)
        self.assertEqual(self.pm.get_base_directory(PathManager.PROCESSED_CONTENT_DIR_NAME), expected_processed)

        expected_ebooks = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME)
        self.assertEqual(self.pm.get_base_directory(PathManager.EBOOKS_DIR_NAME), expected_ebooks)

        expected_archival = os.path.join(self.workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME)
        self.assertEqual(self.pm.get_base_directory(PathManager.ARCHIVAL_STATUS_DIR_NAME), expected_archival)

        with self.assertRaises(ValueError):
            self.pm.get_base_directory("invalid_dir_type")

if __name__ == '__main__':
    unittest.main()
