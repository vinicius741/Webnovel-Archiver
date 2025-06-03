from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class StoryMetadata:
    story_id: Optional[str] = None # Should be populated by ProgressManager or Orchestrator
    story_url: Optional[str] = None
    original_title: Optional[str] = None
    original_author: Optional[str] = None
    cover_image_url: Optional[str] = None
    synopsis: Optional[str] = None
    estimated_total_chapters_source: Optional[int] = None
    # Add other fields as needed from progress_status.json structure if they are purely metadata
    # Fields like last_downloaded_chapter_url are progress-related, not pure metadata

@dataclass
class ChapterInfo:
    source_chapter_id: Optional[str] = None # Original chapter ID from source or download order
    download_order: Optional[int] = None # Order in which it was downloaded/listed
    chapter_url: Optional[str] = None
    chapter_title: Optional[str] = None
    # next_chapter_url_from_page: Optional[str] = None # This might be too specific for base ChapterInfo

class BaseFetcher(ABC):
    @abstractmethod
    def get_story_metadata(self, url: str) -> StoryMetadata:
        """
        Fetches and returns metadata for a story from the given URL.
        This method should parse the main story page.
        """
        pass

    @abstractmethod
    def get_chapter_urls(self, story_url: str) -> List[ChapterInfo]:
        """
        Fetches and returns a list of chapter URLs and their titles for a given story URL.
        This method might parse a table of contents page or the main story page.
        """
        pass

    @abstractmethod
    def download_chapter_content(self, chapter_url: str) -> str:
        """
        Downloads the raw HTML content of a single chapter from its URL.
        """
        pass
