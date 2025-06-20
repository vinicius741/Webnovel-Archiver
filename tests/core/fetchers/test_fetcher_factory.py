import unittest
from urllib.parse import urlparse

from webnovel_archiver.core.fetchers.fetcher_factory import FetcherFactory
from webnovel_archiver.core.fetchers.royalroad_fetcher import RoyalRoadFetcher
from webnovel_archiver.core.fetchers.base_fetcher import BaseFetcher
from webnovel_archiver.core.fetchers.exceptions import UnsupportedSourceError


class TestFetcherFactory(unittest.TestCase):

    def test_get_fetcher_royalroad_url(self):
        """Test that a RoyalRoadFetcher is returned for a RoyalRoad URL."""
        urls = [
            "https://www.royalroad.com/fiction/12345/some-story",
            "http://royalroad.com/another/story",
            "https://royalroad.com/fiction/short",
            "https://www.royalroad.com/f/123/a-story" # Example of a different path structure
        ]
        for url in urls:
            with self.subTest(url=url):
                fetcher = FetcherFactory.get_fetcher(url)
                self.assertIsInstance(fetcher, RoyalRoadFetcher)
                self.assertIsInstance(fetcher, BaseFetcher)

    def test_get_fetcher_unsupported_url(self):
        """Test that UnsupportedSourceError is raised for unsupported domains."""
        urls = [
            "https://www.scribblehub.com/series/123/a-scribble-story",
            "http://unsupported-domain.com/fiction/story",
            "https://www.another-random-site.org/novel/chapter1"
        ]
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(UnsupportedSourceError) as context:
                    FetcherFactory.get_fetcher(url)
                self.assertIn("Source not supported for URL", str(context.exception))
                self.assertIn(urlparse(url).netloc.lower(), str(context.exception))


    def test_get_fetcher_malformed_url_value_error(self):
        """Test that ValueError is raised for malformed or invalid URLs."""
        urls = [
            "just_a_string_not_a_url", # Not a valid URL structure
            "ftp://validprotocolbutunsupported.com/story", # Valid URL, but factory might raise UnsupportedSourceError first depending on logic
                                                       # Current factory logic will pass to urlparse, then fail on domain check.
                                                       # This test is more about the structure if urlparse itself failed or returned no domain
            "http:///missingdomain.com", # malformed
        ]
        for url in urls:
            with self.subTest(url=url):
                # Depending on the exact nature of malformation, urlparse might still return something.
                # The factory's check `if not domain:` is key here for some cases.
                # "just_a_string_not_a_url" will likely have no netloc.
                if "ftp://" in url: # FTP is a valid scheme, so it will be an UnsupportedSourceError
                    with self.assertRaises(UnsupportedSourceError):
                        FetcherFactory.get_fetcher(url)
                else:
                    with self.assertRaises(ValueError) as context:
                        FetcherFactory.get_fetcher(url)
                    self.assertTrue(
                        "Invalid URL format" in str(context.exception) or \
                        "Could not determine domain" in str(context.exception)
                    )


    def test_get_fetcher_empty_url_value_error(self):
        """Test that ValueError is raised for an empty URL string."""
        with self.assertRaises(ValueError) as context:
            FetcherFactory.get_fetcher("")
        self.assertIn("Story URL cannot be empty", str(context.exception))

    def test_get_fetcher_url_without_domain_value_error(self):
        """Test that ValueError is raised for a URL parsed with no domain."""
        # urlparse on "path/only" results in scheme='', netloc='', path='path/only'
        url = "/path/only/no/domain"
        with self.assertRaises(ValueError) as context:
            FetcherFactory.get_fetcher(url)
        self.assertIn("Could not determine domain from URL", str(context.exception))
        self.assertIn(url, str(context.exception))

if __name__ == '__main__':
    unittest.main()
