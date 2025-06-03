import json
import re
from typing import List, Dict, Any, Pattern
from bs4 import BeautifulSoup, NavigableString, Tag

from webnovel_archiver.utils.logger import get_logger
# Need to import setup_basic_logging for the __main__ block
from webnovel_archiver.utils.logger import setup_basic_logging


logger = get_logger(__name__)

class SentenceRemover:
    """
    Removes specified sentences or patterns from HTML content based on a JSON configuration.
    The removal operates on the text content within HTML tags.
    """

    def __init__(self, config_filepath: str):
        """
        Initializes the SentenceRemover with a configuration file.

        Args:
            config_filepath: Path to the JSON configuration file.
                             The JSON file should contain a list of strings or patterns to remove.
                             Example: {"remove_sentences": ["Sentence to remove.", "Another one."]}
                             Or for regex: {"remove_patterns": ["^Advertisement:", "Click here.*"]}
        """
        self.config_filepath = config_filepath
        self.remove_sentences: List[str] = []
        self.remove_patterns: List[Pattern[str]] = []
        self._load_config()

    def _load_config(self) -> None:
        """Loads and parses the JSON configuration file."""
        try:
            with open(self.config_filepath, 'r', encoding='utf-8') as f:
                config: Dict[str, Any] = json.load(f)

            self.remove_sentences = config.get("remove_sentences", [])
            if not isinstance(self.remove_sentences, list) or not all(isinstance(s, str) for s in self.remove_sentences):
                logger.warning("Config 'remove_sentences' should be a list of strings. Using empty list.")
                self.remove_sentences = []

            raw_patterns = config.get("remove_patterns", [])
            if not isinstance(raw_patterns, list) or not all(isinstance(p, str) for p in raw_patterns):
                logger.warning("Config 'remove_patterns' should be a list of strings. Using empty list for patterns.")
                raw_patterns = []

            for pattern_str in raw_patterns:
                try:
                    self.remove_patterns.append(re.compile(pattern_str))
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern_str}' in config: {e}")

            if not self.remove_sentences and not self.remove_patterns:
                logger.warning(f"No sentences or patterns loaded from config: {self.config_filepath}")
            else:
                logger.info(f"Loaded {len(self.remove_sentences)} sentences and {len(self.remove_patterns)} patterns for removal from {self.config_filepath}")

        except FileNotFoundError:
            logger.error(f"Sentence removal config file not found: {self.config_filepath}")
            # Keep remove_sentences and remove_patterns as empty lists
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from sentence removal config file: {self.config_filepath}")
            # Keep remove_sentences and remove_patterns as empty lists
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading sentence removal config: {e}")
            # Keep remove_sentences and remove_patterns as empty lists


    def remove_sentences_from_html(self, html_content: str) -> str:
        """
        Removes configured sentences/patterns from the given HTML content.
        This method parses the HTML and processes text nodes.

        Args:
            html_content: The HTML content string.

        Returns:
            The HTML content with specified sentences/patterns removed from text nodes.
        """
        if not self.remove_sentences and not self.remove_patterns:
            return html_content # No rules to apply

        soup = BeautifulSoup(html_content, 'html.parser')

        # Iterate over all text nodes in the document
        for text_node in soup.find_all(string=True):
            if isinstance(text_node, NavigableString) and text_node.parent and text_node.parent.name not in ['script', 'style']:
                original_text = str(text_node)
                modified_text = original_text

                # Apply exact sentence removal
                for sentence in self.remove_sentences:
                    modified_text = modified_text.replace(sentence, "")

                # Apply regex pattern removal
                for pattern in self.remove_patterns:
                    modified_text = pattern.sub("", modified_text)

                # If text changed, replace the node content
                if modified_text != original_text:
                    # If the modified text is empty and the parent tag becomes empty, consider removing the parent.
                    # This is a simple heuristic. More complex logic might be needed for robust empty tag removal.
                    if not modified_text.strip():
                        parent = text_node.parent
                        text_node.extract() # Remove the now empty text node
                        # If parent has no other children (text or tags) and no attributes that might be important (e.g. id, class for structure)
                        # A more robust check would be if not parent.get_text(strip=True) and not parent.find(True, recursive=False)
                        # For now, a simpler check: if not parent.contents and not parent.attrs
                        if parent and not parent.contents and not parent.attrs and parent.name not in ['body', 'html', 'head']:
                             # Check if it's a common block tag that might be intentionally empty for spacing (e.g. <p></p>)
                            if parent.name not in ['p', 'div', 'span', 'br']: # Add more tags if needed
                                logger.debug(f"Removing empty parent tag: <{parent.name}>")
                                parent.decompose()
                            elif not parent.get_text(strip=True): # For p, div, span - remove if truly empty after modification
                                parent.decompose()

                    else:
                        text_node.replace_with(NavigableString(modified_text))

        return str(soup)

if __name__ == '__main__':
    # Basic Test
    logger_main = get_logger('sentence_remover_main')
    setup_basic_logging() # Ensure logs are visible for testing

    # Create a dummy config file
    dummy_config_content = {
        "remove_sentences": [
            "This is an annoying sentence that must be removed.",
            "Another one bites the dust."
        ],
        "remove_patterns": [
            "ADVERTISEMENT:.*",
            "Please Note:.*"
        ]
    }
    dummy_config_path = "dummy_sentence_remover_config.json"
    with open(dummy_config_path, 'w', encoding='utf-8') as f:
        json.dump(dummy_config_content, f)

    remover = SentenceRemover(dummy_config_path)

    sample_html = """
    <html>
        <head><title>Test</title></head>
        <body>
            <p>Hello world. This is an annoying sentence that must be removed. What a beautiful day.</p>
            <div>Some text. Please Note: This is important. Another one bites the dust.</div>
            <p>ADVERTISEMENT: Buy now!</p>
            <p>This paragraph should remain untouched.</p>
            <p>Empty after removal: <span>This is an annoying sentence that must be removed.</span></p>
            <p>Parent to be removed: This is an annoying sentence that must be removed.</p>
            <p>Text directly in body: This is an annoying sentence that must be removed.</p>
        </body>
    </html>
    """

    logger_main.info(f"Original HTML:\n{sample_html}")
    modified_html_output = remover.remove_sentences_from_html(sample_html)
    logger_main.info(f"Modified HTML:\n{modified_html_output}")

    # Clean up dummy config
    import os
    os.remove(dummy_config_path)

    # Test with non-existent config
    logger_main.info("\n--- Testing with non-existent config ---")
    non_existent_remover = SentenceRemover("non_existent_config.json")
    no_change_html = non_existent_remover.remove_sentences_from_html(sample_html)
    if no_change_html == sample_html:
        logger_main.info("Correctly returned original HTML for non-existent config.")
    else:
        logger_main.error("HTML changed even with non-existent config.")

    # Test with empty config
    logger_main.info("\n--- Testing with empty config ---")
    empty_config_path = "empty_sentence_remover_config.json"
    with open(empty_config_path, 'w', encoding='utf-8') as f:
        json.dump({}, f)
    empty_remover = SentenceRemover(empty_config_path)
    no_change_html_empty = empty_remover.remove_sentences_from_html(sample_html)
    if no_change_html_empty == sample_html:
        logger_main.info("Correctly returned original HTML for empty config.")
    else:
        logger_main.error("HTML changed even with empty config.")
    os.remove(empty_config_path)

    # Test with malformed regex
    logger_main.info("\n--- Testing with malformed regex pattern ---")
    malformed_regex_config_path = "malformed_regex_config.json"
    with open(malformed_regex_config_path, 'w', encoding='utf-8') as f:
        json.dump({"remove_patterns": ["*["]}, f) # Malformed regex
    malformed_remover = SentenceRemover(malformed_regex_config_path) # Should log an error
    # At this point, malformed_remover.remove_patterns should be empty or not contain the bad pattern
    no_change_html_malformed = malformed_remover.remove_sentences_from_html(sample_html)

    # We need to check if the bad pattern was actually skipped and other patterns (if any) would still work.
    # For this specific test, no other patterns are defined, so it should be original HTML.
    if no_change_html_malformed == sample_html:
        logger_main.info("Correctly returned original HTML when regex was malformed (check logs for error about the pattern).")
    else:
        logger_main.error("HTML changed unexpectedly with malformed regex.")
    os.remove(malformed_regex_config_path)

    logger_main.info("\n--- Testing with text node directly under body ---")
    html_direct_text = "<html><body>Direct text to remove: This is an annoying sentence that must be removed. And some other text.</body></html>"
    logger_main.info(f"Original HTML for direct text test:\n{html_direct_text}")
    remover_for_direct = SentenceRemover(dummy_config_path) # Re-use good config
    modified_direct_text_html = remover_for_direct.remove_sentences_from_html(html_direct_text)
    logger_main.info(f"Modified HTML for direct text test:\n{modified_direct_text_html}")
    if "This is an annoying sentence that must be removed." not in modified_direct_text_html:
        logger_main.info("Successfully removed sentence from text node directly under body.")
    else:
        logger_main.error("Failed to remove sentence from text node directly under body.")
    # Re-create dummy config for next test if needed, or ensure tests are independent.
    # For now, it's fine as dummy_config_path is defined above.
    # if not os.path.exists(dummy_config_path):
    #    with open(dummy_config_path, 'w', encoding='utf-8') as f:
    #        json.dump(dummy_config_content, f)
