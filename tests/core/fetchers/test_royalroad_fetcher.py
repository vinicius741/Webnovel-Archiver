import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

from webnovel_archiver.core.fetchers.royalroad_fetcher import (
    RoyalRoadFetcher,
    StoryMetadata,
    ChapterInfo,
    EXAMPLE_STORY_PAGE_HTML # Import for direct use if needed, though fetcher handles it
)
import logging

# Suppress warnings from the fetcher during tests (e.g., "Chapter content not found")
logging.getLogger("webnovel_archiver.core.fetchers.royalroad_fetcher").setLevel(logging.ERROR)


class TestRoyalRoadFetcherParsing(unittest.TestCase):

    def setUp(self):
        self.fetcher = RoyalRoadFetcher()
        # This URL is specifically handled by RoyalRoadFetcher._fetch_html_content
        # to return EXAMPLE_STORY_PAGE_HTML, so no actual HTTP request is made.
        self.example_story_url = "https://www.royalroad.com/fiction/117255/rend"
        # We don't strictly need to parse self.example_soup here if tests rely on fetcher methods,
        # as the fetcher's _fetch_html_content will handle returning the parsed example soup.

    def test_get_story_metadata_from_example(self):
        metadata = self.fetcher.get_story_metadata(self.example_story_url)

        self.assertIsInstance(metadata, StoryMetadata)
        self.assertEqual(metadata.original_title, "REND")
        self.assertEqual(metadata.original_author, "Temple")
        self.assertEqual(metadata.cover_image_url, "https://www.royalroadcdn.com/public/covers-large/117255-rend.jpg?time=1748727569")
        self.assertIn("Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast", metadata.synopsis)
        self.assertEqual(metadata.story_url, self.example_story_url)
        self.assertEqual(metadata.estimated_total_chapters_source, 12)

    def test_get_chapter_urls_from_example(self):
        chapters = self.fetcher.get_chapter_urls(self.example_story_url)

        self.assertIsInstance(chapters, list)
        self.assertEqual(len(chapters), 12)

        # Sample checks for the first chapter
        if len(chapters) > 0:
            first_chapter = chapters[0]
            self.assertIsInstance(first_chapter, ChapterInfo)
            self.assertEqual(first_chapter.source_chapter_id, "2291798")
            self.assertEqual(first_chapter.download_order, 1)
            self.assertEqual(first_chapter.chapter_url, "https://www.royalroad.com/fiction/117255/rend/chapter/2291798/11-crappy-monday")
            self.assertEqual(first_chapter.chapter_title, "1.1 Crappy Monday")

        # Sample checks for the last chapter (index -1)
        if len(chapters) > 0:
            last_chapter = chapters[-1]
            self.assertIsInstance(last_chapter, ChapterInfo)
            self.assertEqual(last_chapter.source_chapter_id, "2322033")
            self.assertEqual(last_chapter.download_order, 12)
            self.assertEqual(last_chapter.chapter_url, "https://www.royalroad.com/fiction/117255/rend/chapter/2322033/41-a-memorial-to-remember")
            self.assertEqual(last_chapter.chapter_title, "4.1 A Memorial To Remember")

    @patch.object(RoyalRoadFetcher, '_fetch_html_content')
    def test_download_chapter_content_parsing_found(self, mock_fetch_html_content):
        sample_chapter_html = """
        <html><body>
            <div class='other-stuff'>Header</div>
            <div class='chapter-content'>
                <p>Test chapter text.</p>
                <span>More text.</span>
            </div>
            <div class='other-stuff'>Footer</div>
        </body></html>
        """
        # Configure the mock to return a BeautifulSoup object for the sample HTML
        mock_fetch_html_content.return_value = BeautifulSoup(sample_chapter_html, 'html.parser')

        # Call the method under test. The URL doesn't matter much as _fetch_html_content is mocked.
        content_html_str = self.fetcher.download_chapter_content("http://fake-chapter-url.com/some/chapter")

        # The download_chapter_content should return the string representation of the chapter-content div
        # It should also clean attributes from the div itself.
        expected_content_str = """<div class="chapter-content">
 <p>
  Test chapter text.
 </p>
 <span>
  More text.
 </span>
</div>"""
        # Normalize both for comparison (e.g. using BeautifulSoup to parse and prettify)
        # The actual cleaner might strip the class from chapter-content div.
        # Based on html_cleaner, it *will* strip the class.

        # The method returns the *string* of the div.
        # Let's parse both and compare prettified versions for robustness.

        returned_soup = BeautifulSoup(content_html_str, 'html.parser')
        # The div itself should have its class attribute removed by the cleaning process in _fetch_html_content
        # if it calls the HTMLCleaner which by default strips common attributes.
        # However, download_chapter_content itself does not invoke HTMLCleaner.
        # It just finds div.chapter-content and returns str(chapter_div).
        # The HTMLCleaner is applied by the Orchestrator *after* download.
        # So, for this unit test, the class should still be there.

        self.assertTrue(returned_soup.find('p', string='Test chapter text.'))
        self.assertTrue(returned_soup.find('span', string='More text.'))
        self.assertIsNotNone(returned_soup.find('div', class_='chapter-content')) # class should still be there

        # More precise check of the returned string structure
        # The method returns str(chapter_div), not a prettified version
        self.assertIn("<div class=\"chapter-content\">", content_html_str)
        self.assertIn("<p>Test chapter text.</p>", content_html_str)
        self.assertIn("<span>More text.</span>", content_html_str)


    @patch.object(RoyalRoadFetcher, '_fetch_html_content')
    def test_download_chapter_content_parsing_not_found(self, mock_fetch_html_content):
        sample_no_content_html = "<html><body><p>No chapter div here.</p></body></html>"
        mock_fetch_html_content.return_value = BeautifulSoup(sample_no_content_html, 'html.parser')

        content = self.fetcher.download_chapter_content("http://fake-no-content-url.com")
        self.assertEqual(content, "Chapter content not found.")

if __name__ == '__main__':
    unittest.main()
