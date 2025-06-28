from urllib.parse import urlparse

from .base_fetcher import BaseFetcher
from .royalroad_fetcher import RoyalRoadFetcher
from .exceptions import UnsupportedSourceError


class FetcherFactory:
    """
    Factory class to select and return the appropriate fetcher based on the story URL.
    """

    @staticmethod
    def get_fetcher(story_url: str) -> BaseFetcher:
        """
        Analyzes the story URL and returns an instance of the appropriate fetcher.

        Args:
            story_url: The URL of the story.

        Returns:
            An instance of a BaseFetcher subclass.

        Raises:
            UnsupportedSourceError: If the domain of the story_url is not supported.
            ValueError: If the URL is malformed or missing a domain.
        """
        if not story_url:
            raise ValueError("Story URL cannot be empty.")

        try:
            parsed_url = urlparse(story_url)
            domain = parsed_url.netloc.lower()
        except Exception as e: # Catch any parsing errors, though urlparse is usually robust
            raise ValueError(f"Invalid URL format: {story_url}. Error: {e}")

        if not domain:
            raise ValueError(f"Could not determine domain from URL: {story_url}")

        if "royalroad.com" in domain:
            return RoyalRoadFetcher(story_url)
        # Example for a future ScribbleHubFetcher
        # elif "scribblehub.com" in domain:
        #     from .scribblehub_fetcher import ScribbleHubFetcher # Assuming it exists
        #     return ScribbleHubFetcher(story_url)
        else:
            raise UnsupportedSourceError(f"Source not supported for URL: {story_url} (domain: {domain})")

if __name__ == '__main__':
    # Example Usage (for testing or demonstration)
    test_urls = [
        "https://www.royalroad.com/fiction/12345/some-story",
        "http://royalroad.com/another/story",
        "https://www.scribblehub.com/series/123/a-scribble-story", # Will raise UnsupportedSourceError
        "https://unsupported.com/fiction/789", # Will raise UnsupportedSourceError
        "ftp://invalidprotocol.com/story", # Will raise UnsupportedSourceError
        "just_a_string_not_a_url", # Will raise ValueError
        "", # Will raise ValueError
        None, # Will raise ValueError (handled by type hinting in real use, but good to test)
    ]

    for url in test_urls:
        print(f"\nTesting URL: {url}")
        try:
            if url is None: # Simulate passing None which would be a TypeError if not caught by caller
                # In real usage, type hints should prevent this, but for direct call test:
                # FetcherFactory.get_fetcher(None) would fail earlier due to type check.
                # Here we explicitly handle it for this test script's purpose.
                print("Error: URL is None, cannot process.")
                continue

            fetcher_instance = FetcherFactory.get_fetcher(url)
            print(f"  Fetcher: {type(fetcher_instance).__name__}")
        except UnsupportedSourceError as e:
            print(f"  Error: {e}")
        except ValueError as e:
            print(f"  Error: {e}")
        except Exception as e:
            print(f"  Unexpected Error: {e}")
