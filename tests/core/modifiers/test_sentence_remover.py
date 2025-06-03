import pytest
import json
import os
import re
from webnovel_archiver.core.modifiers.sentence_remover import SentenceRemover
from webnovel_archiver.utils.logger import get_logger

# If tests need to see logs:

@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config file and returns its path."""
    def _create_config(content):
        config_path = tmp_path / "test_sentence_remover_config.json"
        # Ensure content is not None before trying to dump it
        if content is not None:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(content, f)
        else:
            # If content is None, perhaps create an empty file or handle as error
            # For test_malformed_json_config, we'll write malformed string manually
            config_path.touch() # Creates an empty file if content is None
        return str(config_path)
    return _create_config

HTML_SAMPLE = """
<html><head><title>Test</title></head><body>
    <p>Hello world. This is an annoying sentence that must be removed. What a beautiful day.</p>
    <div>Some text. Please Note: This is important. Another one bites the dust.</div>
    <p>ADVERTISEMENT: Buy now!</p>
    <p>This paragraph should remain untouched.</p>
    <p>Empty after removal: <span>This is an annoying sentence that must be removed.</span></p>
    <p>Parent to be removed: This is an annoying sentence that must be removed.</p>
    <p>Script content: <script>console.log("This is an annoying sentence that must be removed.");</script></p>
    <style>.annoying { content: "This is an annoying sentence that must be removed."; }</style>
</body></html>
"""

def test_sentence_removal_exact_match(temp_config_file):
    config_content = {
        "remove_sentences": ["This is an annoying sentence that must be removed."]
    }
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)

    assert "This is an annoying sentence that must be removed." not in modified_html
    assert "Hello world.  What a beautiful day." in modified_html # Check adjacent text
    # Check that script/style content is NOT affected by simple string replacement
    assert 'console.log("This is an annoying sentence that must be removed.");</script>' in modified_html
    assert '.annoying { content: "This is an annoying sentence that must be removed."; }</style>' in modified_html


def test_sentence_removal_regex_match(temp_config_file):
    config_content = {
        "remove_patterns": ["ADVERTISEMENT:.*", "^Parent to be removed:.*$"]
    }
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)

    assert "ADVERTISEMENT: Buy now!" not in modified_html
    assert "Parent to be removed: This is an annoying sentence that must be removed." not in modified_html
    # Check if the parent <p> tags of the removed content are also removed (if they become empty)
    # This depends on the heuristic in SentenceRemover.
    # A more robust check would be to parse the modified_html and check its structure.
    # For "ADVERTISEMENT: Buy now!", its <p> tag should be gone.
    # For "Parent to be removed: ...", its <p> tag should be gone.
    # A simple check: count <p> tags or look for specific surrounding text if <p> is removed.
    # The current heuristic might make it <p></p> then remove it.
    # Let's assume they are removed and not present as <p></p>
    assert "<p>ADVERTISEMENT: Buy now!</p>" not in modified_html # Original form
    assert "<p></p>" not in modified_html # Check if it became an empty <p> tag, it should be removed by heuristic


def test_sentence_removal_empty_tag_heuristic(temp_config_file):
    config_content = {
        "remove_sentences": ["This is an annoying sentence that must be removed."]
    }
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)

    # The <p> containing "Empty after removal: <span>...</span>"
    # The span's text "This is an annoying sentence that must be removed." is removed.
    # The span itself should be removed if it becomes empty and meets heuristic.
    # Then the parent <p> "Empty after removal: " might also be removed if it becomes empty.
    # Current heuristic: span removed, then p removed. So "Empty after removal:" should not be present.
    assert "Empty after removal:" not in modified_html


def test_non_existent_config_file(caplog):
    remover = SentenceRemover("non_existent_config_file.json")
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)
    assert modified_html == HTML_SAMPLE # Should not change HTML
    assert "Sentence removal config file not found" in caplog.text

def test_empty_config_file(temp_config_file, caplog):
    config_path = temp_config_file({}) # Empty JSON
    remover = SentenceRemover(config_path)
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)
    assert modified_html == HTML_SAMPLE
    assert "No sentences or patterns loaded from config" in caplog.text


def test_malformed_json_config(tmp_path, caplog): # Changed from temp_config_file to tmp_path
    config_path = tmp_path / "malformed_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("{malformed_json") # Write malformed JSON directly

    remover = SentenceRemover(str(config_path))
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)
    assert modified_html == HTML_SAMPLE
    assert "Error decoding JSON" in caplog.text

def test_invalid_regex_pattern(temp_config_file, caplog):
    config_content = {"remove_patterns": ["*["]} # Invalid regex
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path) # Should log an error
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)
    assert modified_html == HTML_SAMPLE # HTML should be unchanged if pattern fails
    assert "Invalid regex pattern '*['" in caplog.text
    assert not remover.remove_patterns # Ensure bad pattern was not added

def test_no_matching_rules(temp_config_file):
    config_content = {"remove_sentences": ["Non-existent sentence."]}
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    modified_html = remover.remove_sentences_from_html(HTML_SAMPLE)
    assert modified_html == HTML_SAMPLE

def test_config_sentences_not_list(temp_config_file, caplog):
    config_content = {"remove_sentences": "This is not a list"}
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    assert not remover.remove_sentences
    assert "Config 'remove_sentences' should be a list of strings" in caplog.text

def test_config_patterns_not_list(temp_config_file, caplog):
    config_content = {"remove_patterns": "This is not a list"}
    config_path = temp_config_file(config_content)
    remover = SentenceRemover(config_path)
    assert not remover.remove_patterns
    assert "Config 'remove_patterns' should be a list of strings" in caplog.text

# Add more tests for specific HTML structures or removal scenarios if needed
