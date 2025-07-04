import ebooklib # type: ignore
from ebooklib import epub
import os
import datetime
import requests # Added for downloading cover image
import shutil # Added for saving cover image
from typing import Optional, List, Dict, Any
from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager # Added PathManager
from webnovel_archiver.core.storage.progress_manager import add_epub_file_to_progress

logger = get_logger(__name__)

class EPUBGenerator:
    def __init__(self, path_manager: PathManager):
        self.pm = path_manager
        # self.workspace_root = workspace_root # Removed
        # self.ebooks_dir_name = "ebooks" # Removed
        # self.processed_content_dir_name = "processed_content" # Removed
        # self.temp_cover_dir_name = "temp_cover_images" # Removed

    def _download_cover_image(self, cover_url: str) -> Optional[str]: # story_id removed, available from self.pm
        """Downloads the cover image and returns the local path."""
        if not cover_url:
            return None

        story_id = self.pm.get_story_id() # Get story_id from PathManager

        try:
            response = requests.get(cover_url, stream=True)
            response.raise_for_status()

            # Ensure the temp directory for covers exists
            # temp_cover_path = os.path.join(self.workspace_root, self.ebooks_dir_name, story_id, self.temp_cover_dir_name) # Replaced
            temp_cover_path = self.pm.get_temp_cover_story_dir()
            os.makedirs(temp_cover_path, exist_ok=True)

            # Determine file extension
            content_type = response.headers.get('content-type')
            if content_type and 'jpeg' in content_type:
                ext = '.jpg'
            elif content_type and 'png' in content_type:
                ext = '.png'
            else: # Fallback or assume jpg
                ext = '.jpg'
                logger.warning(f"Could not determine cover image type for {story_id} from content-type '{content_type}'. Assuming JPG.")

            local_filename = f"cover{ext}"
            # file_path = os.path.join(temp_cover_path, local_filename) # Replaced
            file_path = str(self.pm.get_cover_image_filepath(local_filename))

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Cover image downloaded for story {self.pm.get_story_id()} to {file_path}")
            return file_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download cover image for story {self.pm.get_story_id()} from {cover_url}: {e}")
            return None
        except IOError as e: # file_path might not be defined if os.makedirs failed, though unlikely here
            logger.error(f"Failed to save cover image for story {self.pm.get_story_id()} to {local_filename} in {temp_cover_path}: {e}") # Log temp_cover_path and local_filename
            return None


    def generate_epub(self, progress_data: Dict[Any, Any], chapters_per_volume: Optional[int] = None) -> List[str]:
        # story_id is available via self.pm.get_story_id()
        # workspace_root is available via self.pm.get_workspace_root()
        story_id = self.pm.get_story_id()

        story_title = progress_data.get("effective_title", "Unknown Title")
        author_name = progress_data.get("author", "Unknown Author")
        synopsis = progress_data.get("synopsis")
        cover_image_url = progress_data.get("cover_image_url")

        downloaded_chapters = progress_data.get("downloaded_chapters", [])

        if not downloaded_chapters:
            logger.warning(f"No chapters downloaded for story {story_id}. Cannot generate EPUB.")
            return []

        # ebooks_base_path = os.path.join(self.workspace_root, self.ebooks_dir_name, story_id) # Replaced
        ebooks_base_path = self.pm.get_ebooks_story_dir()
        os.makedirs(ebooks_base_path, exist_ok=True)

        # processed_content_path = os.path.join(self.workspace_root, self.processed_content_dir_name, story_id) # Replaced
        processed_content_path = self.pm.get_processed_content_story_dir()

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

            # Download and set cover image
            local_cover_path = None
            if cover_image_url:
                local_cover_path = self._download_cover_image(cover_image_url) # story_id removed
                if local_cover_path:
                    try:
                        with open(local_cover_path, 'rb') as f:
                            cover_image_data = f.read()
                        # Determine image mime type from extension
                        img_ext = os.path.splitext(local_cover_path)[1].lower()
                        mime_type = 'image/jpeg' # default
                        if img_ext == '.png':
                            mime_type = 'image/png'
                        elif img_ext == '.gif':
                             mime_type = 'image/gif'

                        book.set_cover(os.path.basename(local_cover_path), cover_image_data, create_page=True)
                        # No need to add to spine manually if create_page=True, it's handled by some readers.
                        # However, for broader compatibility, it's better to explicitly add it.
                        # The set_cover method in ebooklib does not automatically add to spine or toc.
                    except FileNotFoundError:
                        logger.error(f"Cover image file not found at {local_cover_path} for story {story_id} during EPUB generation.")
                    except Exception as e:
                        logger.error(f"Error processing cover image for story {story_id}: {e}")


            epub_items_for_book = [] # Holds all EPUB items (synopsis, chapters) for correct ordering
            toc = []

            # Add Synopsis Page if available
            if synopsis:
                synopsis_xhtml_title = "Synopsis"
                synopsis_file_name = "synopsis.xhtml"
                epub_synopsis = epub.EpubHtml(title=synopsis_xhtml_title, file_name=synopsis_file_name, lang='en', uid="synopsis")
                epub_synopsis.content = f"<h1>{synopsis_xhtml_title}</h1><p>{synopsis}</p>"
                book.add_item(epub_synopsis)
                epub_items_for_book.append(epub_synopsis) # Add to items list for spine
                toc.append(epub.Link(synopsis_file_name, synopsis_xhtml_title, synopsis_xhtml_title))


            for chapter_info in volume_chapters:
                chapter_status = chapter_info.get("status")
                chapter_title = chapter_info.get("title", f"Chapter {chapter_info.get('download_order', 'N/A')}")
                if chapter_status == 'archived':
                    chapter_title = f"[Archived] {chapter_title}"
                local_filename = chapter_info.get("local_processed_filename")

                if not local_filename:
                    logger.error(f"Missing 'local_processed_filename' for chapter {chapter_info.get('download_order')} in story {story_id}. Skipping.")
                    continue

                # html_file_path = os.path.join(processed_content_path, local_filename) # Replaced
                html_file_path = self.pm.get_processed_content_chapter_filepath(local_filename)

                try:
                    with open(html_file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                except FileNotFoundError:
                    logger.error(f"Processed HTML file not found: {html_file_path} for story {self.pm.get_story_id()}. Skipping chapter.")
                    continue
                except Exception as e:
                    logger.error(f"Error reading HTML file {html_file_path} for story {self.pm.get_story_id()}: {e}. Skipping chapter.")
                    continue

                epub_chapter = epub.EpubHtml(
                    title=chapter_title,
                    file_name=f"chap_{chapter_info.get('download_order', 'unknown')}.xhtml",
                    lang='en',
                    uid=f"chapter_{chapter_info.get('download_order', 'unknown')}"
                )
                html_content = f"<h1>{chapter_title}</h1>{html_content}"
                epub_chapter.content = html_content
                book.add_item(epub_chapter)
                epub_items_for_book.append(epub_chapter) # Add to items list for spine
                toc.append(epub_chapter) # For NCX TOC

            if not any(item for item in epub_items_for_book if item.media_type == 'application/xhtml+xml'): # Check if there are any actual content pages
                logger.warning(f"No valid content (synopsis or chapters) found for volume {volume_number} of story {story_id}. Skipping EPUB generation for this volume.")
                if local_cover_path and os.path.exists(local_cover_path): # Clean up downloaded cover
                    try:
                        os.remove(local_cover_path)
                        # Attempt to remove the temp_cover_dir if it's empty
                        temp_cover_dir = os.path.dirname(local_cover_path)
                        if not os.listdir(temp_cover_dir):
                            os.rmdir(temp_cover_dir)
                    except OSError as e:
                        logger.warning(f"Could not clean up temporary cover file/directory for story {story_id}: {e}")
                continue

            # Define Table of Contents for NCX
            book.toc = tuple(toc) # NCX TOC should primarily list chapters and major sections like synopsis

            # Add default NCX and Nav file
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())


            # Define CSS style (optional)
            # style = 'BODY {color: white;}'
            # nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
            # book.add_item(nav_css)

            # Set the book spine
            # The spine determines the linear reading order.
            # 'nav' should come first. If a cover page was generated by set_cover(create_page=True),
            # it's often named 'cover.xhtml' and should be at the beginning of the spine or handled by reader.
            # For explicit control, we can add it. ebooklib's set_cover with create_page=True adds an item
            # book.guide also gets 'cover' entry pointing to the image.
            # Let's ensure 'nav' is first, then our content items.
            # If book.cover_page (an EpubHtml item created by set_cover) exists, add it to spine.
            spine_items = ['nav']
            if hasattr(book, 'cover_page') and book.cover_page:
                 # ebooklib might add the cover_page to items automatically.
                 # We don't need to add it to book.items again if set_cover did.
                 # We just need to ensure it's in the spine if desired.
                 # However, standard practice is that the cover is not part of the linear reading order (spine)
                 # but is pointed to by metadata. Some readers might display it if it's first in spine.
                 # For now, let's not add cover.xhtml to spine, as `set_cover` handles metadata.
                 # The `create_page=True` makes an XHTML wrapper, which some readers use.
                 pass # Cover is handled by metadata and `set_cover(create_page=True)`

            spine_items.extend(epub_items_for_book)
            book.spine = [(item, 'no') for item in spine_items]

            if len(volume_chapters_list) > 1:
                epub_filename = f"{sanitized_story_title}_vol_{volume_number}.epub"
            else:
                epub_filename = f"{sanitized_story_title}.epub"

            # epub_filepath = os.path.join(ebooks_base_path, epub_filename) # Replaced
            epub_filepath = self.pm.get_epub_filepath(epub_filename)

            try:
                epub.write_epub(epub_filepath, book, {})
                progress_data = add_epub_file_to_progress(progress_data, epub_filename, epub_filepath, story_id, self.pm.get_workspace_root())
                logger.info(f"Successfully generated EPUB: {epub_filepath}")
            except Exception as e:
                logger.error(f"Failed to write EPUB file {epub_filepath} for story {self.pm.get_story_id()}: {e}")
            finally:
                # Clean up downloaded cover image after EPUB generation for this volume
                if local_cover_path and os.path.exists(local_cover_path):
                    try:
                        os.remove(local_cover_path)
                        # Attempt to remove the temp_cover_dir if it's empty and we are on the last volume
                        if i == len(volume_chapters_list) -1: # only try to remove dir after last volume
                            temp_cover_dir = os.path.dirname(local_cover_path)
                            if os.path.exists(temp_cover_dir) and not os.listdir(temp_cover_dir):
                                os.rmdir(temp_cover_dir)
                                logger.info(f"Successfully removed temporary cover directory: {temp_cover_dir}")
                            elif os.path.exists(temp_cover_dir):
                                logger.debug(f"Temporary cover directory {temp_cover_dir} is not empty, not removing.")
                    except OSError as e:
                        logger.warning(f"Could not clean up temporary cover file/directory for story {story_id} after EPUB generation: {e}")

        return progress_data
