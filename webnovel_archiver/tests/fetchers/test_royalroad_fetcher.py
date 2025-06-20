import pytest
from webnovel_archiver.core.fetchers.royalroad_fetcher import RoyalRoadFetcher

# Instantiate the fetcher once for all tests in this module
fetcher = RoyalRoadFetcher()

@pytest.mark.parametrize("url, expected_id", [
    ("https://www.royalroad.com/fiction/12345/some-story-title", "12345"),
    ("https://www.royalroad.com/fiction/12345", "12345"),
    ("http://www.royalroad.com/fiction/67890/another-story", "67890"),
    ("https://royalroad.com/fiction/54321/no-www", "54321"),
    ("https://www.royalroad.com/fiction/1/short-id", "1"),
    ("https://www.royalroad.com/fiction/111943/the-empress-of-nightmares-embraces-the-world-power", "111943"),
])
def test_get_source_specific_id_valid_urls(url, expected_id):
    """Test that valid RoyalRoad URLs return the correct fiction ID."""
    assert fetcher.get_source_specific_id(url) == expected_id

@pytest.mark.parametrize("invalid_url", [
    "https://www.royalroad.com/fictio/12345/some-story-title", # Misspelled 'fiction'
    "https://www.royalroad.com/profile/12345", # Not a fiction URL
    "https://www.another-site.com/fiction/12345", # Different domain
    "https://www.royalroad.com/fiction//no-id", # No ID
    "https://www.royalroad.com/fiction/abcde/letters-as-id", # Non-numeric ID
    "http://royalroad.com/some/other/path",
    "Just some random text",
    "", # Empty string
])
def test_get_source_specific_id_invalid_urls(invalid_url):
    """Test that invalid or non-matching URLs raise ValueError."""
    with pytest.raises(ValueError):
        fetcher.get_source_specific_id(invalid_url)

def test_get_source_specific_id_url_with_query_params():
    """Test URL with query parameters."""
    url = "https://www.royalroad.com/fiction/77777/story-with-query?param=value&another=true"
    expected_id = "77777"
    assert fetcher.get_source_specific_id(url) == expected_id

def test_get_source_specific_id_url_with_fragment():
    """Test URL with a fragment."""
    url = "https://www.royalroad.com/fiction/88888/story-with-fragment#section1"
    expected_id = "88888"
    assert fetcher.get_source_specific_id(url) == expected_id

def test_get_source_specific_id_complex_url():
    """Test a more complex URL combining features."""
    url = "http://royalroad.com/fiction/99999/a-very-long-story-title-with-hyphens-and-numbers-123?utm_source=test&page=3#comments"
    expected_id = "99999"
    assert fetcher.get_source_specific_id(url) == expected_id
