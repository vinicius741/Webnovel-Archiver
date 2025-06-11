import ebooklib # type: ignore
from ebooklib import epub
import os
import datetime
from typing import Optional, List, Dict, Any
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

class EPUBGenerator:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.ebooks_dir_name = "ebooks"
        self.processed_content_dir_name = "processed_content"

    def generate_epub(self, story_id: str, progress_data: Dict[Any, Any], chapters_per_volume: Optional[int] = None) -> List[str]:
        story_title = progress_data.get("effective_title", "Unknown Title")
        author_name = progress_data.get("author", "Unknown Author")
        # Additional metadata like cover image can be handled here

        downloaded_chapters = progress_data.get("downloaded_chapters", [])

        if not downloaded_chapters:
            logger.warning(f"No chapters downloaded for story {story_id}. Cannot generate EPUB.")
            return []

        ebooks_base_path = os.path.join(self.workspace_root, self.ebooks_dir_name, story_id)
        os.makedirs(ebooks_base_path, exist_ok=True)

        processed_content_path = os.path.join(self.workspace_root, self.processed_content_dir_name, story_id)

        generated_epub_files = []

        # Sanitize story title for filename
        sanitized_story_title = "".join(c if c.isalnum() or c in [' ', '.', '_'] else '_' for c in story_title).replace(' ', '_')

        num_chapters = len(downloaded_chapters)
        if chapters_per_volume is None or chapters_per_volume <= 0 or chapters_per_volume >= num_chapters:
            # Single volume
            volume_chapters_list = [downloaded_chapters]
            volume_number_offset = 0 # for naming if there's only one volume
        else:
            # Multiple volumes
            volume_chapters_list = [
                downloaded_chapters[i:i + chapters_per_volume]
                for i in range(0, num_chapters, chapters_per_volume)
            ]
            volume_number_offset = 1


        for i, volume_chapters in enumerate(volume_chapters_list):
            volume_number = i + volume_number_offset
            book = epub.EpubBook()

            volume_specific_title = story_title
            if len(volume_chapters_list) > 1:
                volume_specific_title = f"{story_title} Vol. {volume_number}"
                book.set_identifier(f"{story_id}_vol_{volume_number}")
            else:
                book.set_identifier(story_id)

            book.set_title(volume_specific_title)
            book.set_language('en')
            book.add_author(author_name)
            # Add other metadata like cover here if available

            epub_chapters_for_book = []
            toc = []

            for chapter_info in volume_chapters:
                chapter_status = chapter_info.get("status")
                chapter_title = chapter_info.get("title", f"Chapter {chapter_info.get('download_order', 'N/A')}")
                if chapter_status == 'archived':
                    chapter_title = f"[Archived] {chapter_title}"
                local_filename = chapter_info.get("local_processed_filename")

                if not local_filename:
                    logger.error(f"Missing 'local_processed_filename' for chapter {chapter_info.get('download_order')} in story {story_id}. Skipping.")
                    continue

                html_file_path = os.path.join(processed_content_path, local_filename)

                try:
                    with open(html_file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                except FileNotFoundError:
                    logger.error(f"Processed HTML file not found: {html_file_path} for story {story_id}. Skipping chapter.")
                    continue
                except Exception as e:
                    logger.error(f"Error reading HTML file {html_file_path} for story {story_id}: {e}. Skipping chapter.")
                    continue

                epub_chapter = epub.EpubHtml(
                    title=chapter_title,
                    file_name=f"chap_{chapter_info.get('download_order', 'unknown')}.xhtml",
                    lang='en'
                )
                html_content = f"<h1>{chapter_title}</h1>{html_content}"
                epub_chapter.content = html_content
                book.add_item(epub_chapter)
                epub_chapters_for_book.append(epub_chapter)
                toc.append(epub_chapter)

            if not epub_chapters_for_book:
                logger.warning(f"No valid chapters found for volume {volume_number} of story {story_id}. Skipping EPUB generation for this volume.")
                continue

            # Define Table of Contents
            book.toc = tuple(toc)

            # Add default NCX and Nav file
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Define CSS style (optional)
            # style = 'BODY {color: white;}'
            # nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
            # book.add_item(nav_css)

            # Set the book spine
            book.spine = ['nav'] + epub_chapters_for_book # Add nav first, then chapters

            if len(volume_chapters_list) > 1:
                epub_filename = f"{sanitized_story_title}_vol_{volume_number}.epub"
            else:
                epub_filename = f"{sanitized_story_title}.epub"

            epub_filepath = os.path.join(ebooks_base_path, epub_filename)

            try:
                epub.write_epub(epub_filepath, book, {})
                generated_epub_files.append(epub_filepath)
                logger.info(f"Successfully generated EPUB: {epub_filepath}")
            except Exception as e:
                logger.error(f"Failed to write EPUB file {epub_filepath} for story {story_id}: {e}")

        return generated_epub_files
