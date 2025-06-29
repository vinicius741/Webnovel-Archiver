from typing import List, Optional
import re
import requests
from requests.exceptions import HTTPError, RequestException
from bs4 import BeautifulSoup, Tag
import logging # Added for logging
from urllib.parse import urljoin

from .base_fetcher import BaseFetcher, StoryMetadata, ChapterInfo

# Setup basic logging
logger = logging.getLogger(__name__)

class RoyalRoadFetcher(BaseFetcher):
    def __init__(self, story_url: str):
        super().__init__(story_url)

    def _fetch_html_content(self, url: str) -> BeautifulSoup:

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        timeout_seconds = 15 # Reasonable timeout

        logger.info(f"Fetching HTML content from URL: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
            return BeautifulSoup(response.text, 'html.parser')
        except HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching {url}: {http_err} - Status code: {response.status_code}")
            raise # Re-raise the caught HTTPError
        except RequestException as req_err:
            logger.error(f"Request exception occurred while fetching {url}: {req_err}")
            # Wrap generic RequestException in an HTTPError or a custom exception if preferred
            # For now, re-raising a more generic error or a new HTTPError
            raise HTTPError(f"Request failed for {url}: {req_err}") # Consider a custom exception here
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {url}: {e}")
            # Catching other unexpected errors
            raise HTTPError(f"An unexpected error occurred for {url}: {e}")


    def get_story_metadata(self) -> StoryMetadata:
        # Fetch live content or use example based on URL.
        # _fetch_html_content will handle if it's the specific example URL.
        soup = self._fetch_html_content(self.story_url)

        metadata = StoryMetadata()
        metadata.story_url = self.story_url

        # Title
        title_tag = soup.find('h1', class_='font-white')
        if title_tag:
            metadata.original_title = title_tag.text.strip()
        else: # Fallback to meta property
            og_title_tag = soup.find('meta', property='og:title')
            if isinstance(og_title_tag, Tag): # Check if it's a Tag
                content = og_title_tag.get('content')
                if isinstance(content, str):
                    metadata.original_title = content
                elif isinstance(content, list): # Should not happen for 'content' but good practice
                    metadata.original_title = content[0] if content else None
            if not metadata.original_title: # Fallback to document title if specific tags are missing
                doc_title_tag = soup.find('title')
                if isinstance(doc_title_tag, Tag) and doc_title_tag.string is not None:
                    title_text = str(doc_title_tag.string).strip() # Ensure it's a string
                    # Remove " | Royal Road" suffix
                    metadata.original_title = title_text.replace(" | Royal Road", "").strip()


        # Author
        author_link = soup.select_one('h4.font-white a[href*="/profile/"]')
        if author_link:
            metadata.original_author = author_link.text.strip()
        else: # Fallback to meta property
            meta_author_tag = soup.find('meta', property='books:author')
            if isinstance(meta_author_tag, Tag): # Check if it's a Tag
                content = meta_author_tag.get('content')
                if isinstance(content, str):
                    metadata.original_author = content
                elif isinstance(content, list):
                    metadata.original_author = content[0] if content else None

        # Cover Image URL
        cover_img_tag = soup.select_one('div.cover-art-container img.thumbnail')
        if cover_img_tag:
            src_content = cover_img_tag.get('src')
            if isinstance(src_content, str):
                metadata.cover_image_url = src_content
            elif isinstance(src_content, list):
                metadata.cover_image_url = src_content[0] if src_content else None
        if not metadata.cover_image_url: # Fallback to meta property
            og_image_tag = soup.find('meta', property='og:image')
            if isinstance(og_image_tag, Tag): # Check if it's a Tag
                content = og_image_tag.get('content')
                if isinstance(content, str):
                    metadata.cover_image_url = content
                elif isinstance(content, list):
                    metadata.cover_image_url = content[0] if content else None

        # Synopsis
        # Try the schema.org description first as it's often cleaner
        schema_script = soup.find('script', type='application/ld+json')
        if schema_script and isinstance(schema_script, Tag) and schema_script.string:
            import json
            try:
                schema_data = json.loads(schema_script.string) # schema_script.string should be str
                description = schema_data.get('description')
                if schema_data.get('@type') == 'Book' and isinstance(description, str):
                    # Basic cleaning for synopsis from schema: remove <p>, <br>, <hr>
                    synopsis_html = description
                    synopsis_soup = BeautifulSoup(synopsis_html, 'html.parser')
                    # Replace <br> and <hr> with newlines, then get text
                    for br in synopsis_soup.find_all("br"):
                        br.replace_with("\n")
                    for hr in synopsis_soup.find_all("hr"):
                        hr.replace_with("\n---\n")
                    metadata.synopsis = synopsis_soup.get_text(separator='\n').strip()

            except json.JSONDecodeError:
                pass # Fallback if JSON is malformed

        if not metadata.synopsis: # Fallback to the description div if schema fails or not present
            description_div = soup.select_one('div.description div.hidden-content')
            if description_div:
                # Convert <p> tags to text with newlines, <hr> to separator
                ps = []
                for element in description_div.children:
                    if isinstance(element, Tag):
                        if element.name == 'p':
                            ps.append(element.get_text(strip=True))
                        elif element.name == 'hr':
                            ps.append("---")
                metadata.synopsis = "\n\n".join(ps).strip()

        # Estimated total chapters from source (from the table#chapters data-chapters attribute)
        chapters_table = soup.find('table', id='chapters')
        if isinstance(chapters_table, Tag) and chapters_table.has_attr('data-chapters'):
            data_chapters = chapters_table['data-chapters']
            if isinstance(data_chapters, str):
                try:
                    metadata.estimated_total_chapters_source = int(data_chapters)
                except ValueError:
                    metadata.estimated_total_chapters_source = None # Or some other default/logging
            elif isinstance(data_chapters, list) and data_chapters: # Should not happen for data-chapters
                 try:
                    metadata.estimated_total_chapters_source = int(data_chapters[0])
                 except ValueError:
                    metadata.estimated_total_chapters_source = None

        return metadata

    def get_chapter_urls(self) -> List[ChapterInfo]:
        # Fetch live content or use example based on URL.
        soup = self._fetch_html_content(self.story_url)

        chapters: List[ChapterInfo] = []
        chapter_table_tag = soup.find('table', id='chapters')
        if not isinstance(chapter_table_tag, Tag):
            return chapters

        tbody = chapter_table_tag.find('tbody')
        if not isinstance(tbody, Tag):
            return chapters

        base_url = "https://www.royalroad.com" # Needed to construct full URLs

        for order, row in enumerate(tbody.find_all('tr', class_='chapter-row')):
            if not isinstance(row, Tag):
                continue
            link_tag = row.find('a')
            if isinstance(link_tag, Tag) and link_tag.has_attr('href'):
                href_attr = link_tag['href']
                if isinstance(href_attr, str):
                    chapter_relative_url = href_attr
                elif isinstance(href_attr, list) and href_attr: # handle case if href is a list
                    chapter_relative_url = href_attr[0]
                else:
                    continue # skip if href is not a string or a list of strings

                full_chapter_url = base_url + chapter_relative_url if chapter_relative_url.startswith('/') else chapter_relative_url
                chapter_title_text = link_tag.text.strip()

                # Try to extract a source_chapter_id from the URL, e.g., the numeric part
                # Example: /fiction/117255/rend/chapter/2291798/11-crappy-monday -> 2291798
                match = re.search(r'/chapter/(\d+)/', full_chapter_url)
                source_id = match.group(1) if match else f"order_{order + 1}"

                chapters.append(ChapterInfo(
                    source_chapter_id=source_id,
                    download_order=order + 1,
                    chapter_url=full_chapter_url,
                    chapter_title=chapter_title_text
                ))
        return chapters

    def download_chapter_content(self, chapter_url: str) -> str:
        logger.info(f"Attempting to download chapter content from: {chapter_url}")
        try:
            soup = self._fetch_html_content(chapter_url) # This will make a live request
            chapter_div = soup.find('div', class_='chapter-content')

            if chapter_div:
                # Return the HTML content of the chapter_div as a string
                return str(chapter_div)
            else:
                logger.warning(f"Chapter content div (class 'chapter-content') not found for URL: {chapter_url}")
                return "Chapter content not found."
        except HTTPError as http_err:
            # Logged in _fetch_html_content, but can add more context here if needed
            logger.error(f"Failed to download chapter {chapter_url} due to HTTP error: {http_err}")
            raise # Re-raise to signal failure to the caller
        except Exception as e:
            logger.error(f"An unexpected error occurred while downloading chapter {chapter_url}: {e}")
            # Optionally raise a custom exception or return an error message
            return f"Error downloading chapter: {e}"

    def get_next_chapter_url_from_page(self, chapter_page_url: str) -> Optional[str]:
        """
        Fetches a chapter page and extracts the URL for the next chapter.

        Args:
            chapter_page_url: The URL of the current chapter page.

        Returns:
            The absolute URL of the next chapter, or None if not found or an error occurs.
        """
        logger.info(f"Attempting to find next chapter URL from: {chapter_page_url}")
        try:
            soup = self._fetch_html_content(chapter_page_url)
        except HTTPError as http_err:
            # _fetch_html_content already logs this, but we can add context
            logger.error(f"HTTP error when trying to fetch page for next chapter link from {chapter_page_url}: {http_err}")
            return None
        except Exception as e: # Catch any other unexpected errors from _fetch_html_content
            logger.error(f"Unexpected error fetching page for next chapter link from {chapter_page_url}: {e}")
            return None

        next_chapter_href = None

        # Try selectors in order
        selectors_tried = []

        # 1. `soup.find('a', rel='next')`
        try:
            next_link_tag = soup.find('a', rel='next')
            if next_link_tag and next_link_tag.get('href'):
                next_chapter_href = next_link_tag['href']
                logger.info(f"Found next chapter link using 'a[rel=next]': {next_chapter_href}")
            else:
                selectors_tried.append("a[rel=next]")
        except Exception as e:
            logger.warning(f"Error applying selector 'a[rel=next]' on {chapter_page_url}: {e}")
            selectors_tried.append("a[rel=next] (error)")

        # 2. `soup.find('a', class_='next-chapter')`
        if not next_chapter_href:
            try:
                next_link_tag = soup.find('a', class_='next-chapter')
                if next_link_tag and next_link_tag.get('href'):
                    next_chapter_href = next_link_tag['href']
                    logger.info(f"Found next chapter link using 'a.next-chapter': {next_chapter_href}")
                else:
                    selectors_tried.append("a.next-chapter")
            except Exception as e:
                logger.warning(f"Error applying selector 'a.next-chapter' on {chapter_page_url}: {e}")
                selectors_tried.append("a.next-chapter (error)")

        # 3. `soup.select_one('a.btn-primary.next-chapter')`
        if not next_chapter_href:
            try:
                next_link_tag = soup.select_one('a.btn-primary.next-chapter')
                if next_link_tag and next_link_tag.get('href'):
                    next_chapter_href = next_link_tag['href']
                    logger.info(f"Found next chapter link using 'a.btn-primary.next-chapter': {next_chapter_href}")
                else:
                    selectors_tried.append("a.btn-primary.next-chapter")
            except Exception as e:
                logger.warning(f"Error applying selector 'a.btn-primary.next-chapter' on {chapter_page_url}: {e}")
                selectors_tried.append("a.btn-primary.next-chapter (error)")

        # 4. `soup.select_one('a[href*="/chapter/"]:contains("Next")')`
        if not next_chapter_href:
            try:
                # BeautifulSoup's :contains is CSS standard, checks for text content.
                # For more complex text matching, other methods might be needed, but this is a good attempt.
                next_link_tag = soup.select_one('a[href*="/chapter/"]:has(> :contains("Next"))') # Checks for direct children like <span>Next</span>
                if not next_link_tag: # Fallback for direct text
                    next_link_tag = soup.select_one('a[href*="/chapter/"]:contains("Next")')

                if next_link_tag and next_link_tag.get('href'):
                    next_chapter_href = next_link_tag['href']
                    logger.info(f"Found next chapter link using 'a[href*=/chapter/]:contains(Next)': {next_chapter_href}")
                else:
                    selectors_tried.append('a[href*="/chapter/"]:contains("Next")')
            except Exception as e:
                # Some parsers might not support :contains well or other issues.
                logger.warning(f"Error applying selector 'a[href*=/chapter/]:contains(Next)' on {chapter_page_url}: {e}")
                selectors_tried.append('a[href*="/chapter/"]:contains("Next") (error)')

        if next_chapter_href:
            # Ensure the URL is absolute
            absolute_url = urljoin(chapter_page_url, str(next_chapter_href))
            logger.info(f"Successfully extracted and absolutized next chapter URL: {absolute_url}")
            return absolute_url
        else:
            logger.warning(f"Could not find the next chapter link on {chapter_page_url} after trying selectors: {', '.join(selectors_tried)}")
            return None

    def get_permanent_id(self) -> str:
        """
        Extracts the numerical fiction ID from a RoyalRoad URL.
        Example: "https://www.royalroad.com/fiction/12345/some-story-title" -> "12345"
        """
        match = re.search(r"royalroad.com/fiction/(\d+)", self.story_url)
        if match:
            return f"royalroad-{match.group(1)}"
        else:
            logger.warning(f"Could not extract fiction ID from RoyalRoad URL: {self.story_url}")
            raise ValueError(f"Could not parse RoyalRoad fiction ID from URL: {self.story_url}")

if __name__ == '__main__':
    # Setup basic logging for the __main__ block
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Example usage for testing (will be part of actual test files later)
    story_url_example = "https://www.royalroad.com/fiction/117255/rend"
    fetcher = RoyalRoadFetcher(story_url_example)

    logger.info("--- Story Metadata ---")
    try:
        metadata = fetcher.get_story_metadata()
        logger.info(f"Title: {metadata.original_title}")
        logger.info(f"Author: {metadata.original_author}")
        logger.info(f"Cover URL: {metadata.cover_image_url}")
        synopsis_preview = (metadata.synopsis[:200] + "...") if metadata.synopsis else "N/A"
        logger.info(f"Synopsis: {synopsis_preview}")
        logger.info(f"Est. Chapters: {metadata.estimated_total_chapters_source}")
        logger.info(f"Story URL: {metadata.story_url}")
    except Exception as e:
        logger.error(f"Error fetching story metadata: {e}")


    logger.info("\n--- Chapter List ---")
    try:
        chapters = fetcher.get_chapter_urls()
        if chapters:
            for i, chap in enumerate(chapters[:2]): # Print first 2 chapters for brevity
                logger.info(f"Order: {chap.download_order}, Source ID: {chap.source_chapter_id}, Title: {chap.chapter_title}, URL: {chap.chapter_url}")
            if len(chapters) > 2:
                logger.info(f"... and {len(chapters) - 2} more chapters.")
        else:
            logger.warning("No chapters found.")
    except Exception as e:
        logger.error(f"Error fetching chapter list: {e}")


    logger.info("\n--- Download Chapter Content (Live Request) ---")
    if chapters:
        # Attempt to download the first chapter's content - THIS WILL BE A LIVE REQUEST
        # Ensure the URL is a valid chapter URL that can be fetched.
        # For testing, you might want to use a known public chapter URL.
        # Example: chapters[0].chapter_url from the example story
        # Note: Continuous live requests might be rate-limited or blocked.
        # This is for demonstration; actual usage should be respectful of site terms.
        first_chapter_to_download = chapters[0]
        logger.info(f"Attempting to download content for chapter: {first_chapter_to_download.chapter_title} from {first_chapter_to_download.chapter_url}")
        try:
            # This part will make a live request to RoyalRoad
            # If running in an environment without internet or if RoyalRoad blocks, this will fail.
            # For CI/testing, consider mocking requests.
            if first_chapter_to_download.chapter_url is not None:
                first_chapter_content = fetcher.download_chapter_content(first_chapter_to_download.chapter_url)
                if "Chapter content not found." in first_chapter_content :
                    logger.warning(f"Content for '{first_chapter_to_download.chapter_title}': {first_chapter_content}")
                else:
                    logger.info(f"Content for '{first_chapter_to_download.chapter_title}':\n{first_chapter_content[:300]}...")
            else:
                logger.warning(f"Chapter '{first_chapter_to_download.chapter_title}' has no URL, skipping download.")
        except HTTPError as http_err:
            logger.error(f"HTTPError downloading '{first_chapter_to_download.chapter_title}': {http_err}")
        except Exception as e:
            logger.error(f"Unexpected error downloading '{first_chapter_to_download.chapter_title}': {e}")

    else:
        logger.warning("No chapters found, cannot simulate download.")

    # Example of fetching a non-example story URL (will make live requests)
    # Use with caution to avoid rate limiting or IP bans. Best to mock for tests.
    # story_url_live_test = "https://www.royalroad.com/fiction/76753/the-perfect-run" # A different popular story
    # logger.info(f"\n--- Testing live fetch for a different story: {story_url_live_test} ---")
    # try:
    #     live_metadata = fetcher.get_story_metadata(story_url_live_test)
    #     logger.info(f"Live Title: {live_metadata.original_title}")
    #     live_chapters = fetcher.get_chapter_urls(story_url_live_test)
    #     if live_chapters:
    #         logger.info(f"First live chapter: {live_chapters[0].chapter_title}")
    # except HTTPError as e:
    #     logger.error(f"Failed to fetch live story '{story_url_live_test}': {e}")
    # except Exception as e:
    #     logger.error(f"An unexpected error occurred with live story '{story_url_live_test}': {e}")
