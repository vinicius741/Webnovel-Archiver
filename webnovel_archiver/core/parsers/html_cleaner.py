from bs4 import BeautifulSoup, NavigableString, Tag
import re # Added for regex operations
from typing import Optional # Added for type hinting

class HTMLCleaner:
    def __init__(self, config=None):
        """
        Initializes the HTMLCleaner.
        Config might be used in the future to customize cleaning rules.
        """
        self.config = config if config else {}
        # Define tags and attributes to remove or keep.
        # These are common defaults; could be extended by config.
        self.default_tags_to_remove = ['script', 'style', 'link', 'meta', 'noscript', 'header', 'footer', 'nav', 'aside', 'form', 'iframe', 'button', 'input']
        self.default_attributes_to_remove = [
            'style', 'class', 'id', 'onclick', 'onerror', 'onload', 'onmouseover', 'onmouseout',
            'data-reactid', 'data-testid', # Common React/testing attributes
            'aria-labelledby', 'aria-describedby', 'role', # Accessibility attributes not essential for raw content
            # Other common JS or framework specific attributes
            'jsaction', 'jscontroller', 'jsmodel', 'c-wiz', 'jsshadow', 'jsname',
        ]
        # Add specific selectors for RoyalRoad if known (e.g. user comments, author notes sections not part of story)
        self.royalroad_selectors_to_remove = [
            '.author-notes-start', '.author-notes-end', # Typical classes for author notes outside content
            '.comments-area', '#comments', '.comment-section', # Comment sections
            '.rating-section', '.star-rating', # Rating widgets
            '.patreon-button', '.subscribe-button', # Call to action buttons
            '.portlet', # Often sidebars or unrelated content blocks on RR
            'div.hidden[style*="display:none"]', # Hidden divs often for ads or trackers
            'div[id*="nitro-ad"]', 'div[class*="nitro-ad"]', # Ad placeholders
            'div[class*="bottom-spacing"]', # Often empty or for layout
            'div[class*="ad-container"]',
        ]


    def clean_html(self, raw_html: str, source_site: Optional[str] = "royalroad") -> str:
        """
        Cleans the raw HTML content to extract the main story.
        Focuses on removing scripts, styles, and common clutter.
        Selects the main content div for RoyalRoad.
        """
        soup = BeautifulSoup(raw_html, 'html.parser')

        # --- Site-specific main content extraction ---
        # For RoyalRoad, the main content is typically within a div with class 'chapter-content'
        if source_site == "royalroad":
            main_content_div = soup.find('div', class_='chapter-content')
            if main_content_div:
                soup = BeautifulSoup(str(main_content_div), 'html.parser') # Re-parse with only the main content
            else:
                # If no 'chapter-content' div, we proceed with cleaning the whole soup,
                # but this might indicate a page structure change or wrong page.
                print("Warning: 'chapter-content' div not found for RoyalRoad. Cleaning entire HTML.")

        # --- General cleaning applicable to the selected content ---

        # 1. Remove unwanted site-specific selectors first (if any matched within main_content_div)
        if source_site == "royalroad":
            for selector in self.royalroad_selectors_to_remove:
                for unwanted_element in soup.select(selector):
                    unwanted_element.decompose()

        # 2. Remove standard unwanted tags
        for tag_name in self.default_tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 3. Remove unwanted attributes from all remaining tags
        for tag in soup.find_all(True): # True matches all tags
            attrs_to_remove_for_this_tag = []
            for attr in tag.attrs:
                if attr in self.default_attributes_to_remove:
                    attrs_to_remove_for_this_tag.append(attr)
            for attr_to_remove in attrs_to_remove_for_this_tag:
                del tag[attr_to_remove]

        # 4. Remove empty tags (e.g., <p></p>, <span></span>) after cleaning,
        #    but be careful not to remove tags like <br/> or <hr/> if they are standalone.
        #    A simple check: if a tag has no children (text or other tags) and is not self-closing by default.
        #    Common self-closing tags: br, hr, img, input, link, meta
        common_self_closing = ['br', 'hr', 'img']
        for tag in soup.find_all(True):
            if not tag.contents and not tag.get_text(strip=True) and tag.name not in common_self_closing:
                # If it's truly empty and not a structural self-closing tag, remove it.
                # Exception: Keep empty <p> if they might be for spacing, though CSS should handle that.
                # For now, let's be aggressive with totally empty tags.
                # A more sophisticated check might be needed if this removes too much.
                is_empty = True
                for child in tag.children: # Check if it contains any non-empty NavigableString
                    if isinstance(child, NavigableString) and child.strip():
                        is_empty = False
                        break
                    elif isinstance(child, Tag): # Or if it contains any other tags
                        is_empty = False
                        break
                if is_empty:
                    tag.decompose()


        # 5. Optional: Convert multiple <br> tags into paragraphs or single <br>s
        #    This can be complex. For now, we'll leave <br> tags as they are.

        # 6. Optional: Normalize whitespace
        #    This can also be tricky. BeautifulSoup's prettify does some, but might not be exactly what's needed.

        # Get the cleaned HTML string
        # Use prettify for a more readable output, or just str(soup) for compact.
        cleaned_html = soup.prettify() # soup.encode_contents(formatter="html").decode('utf-8')

        # Further specific cleanups that are hard with BS4 alone:
        # Remove consecutive blank lines resulting from decomposed elements + prettify
        cleaned_html = re.sub(r'\n\s*\n', '\n', cleaned_html)

        return cleaned_html.strip()

if __name__ == '__main__':
    # Example usage:
    cleaner = HTMLCleaner()

    # Test case 1: RoyalRoad-like chapter content
    # This is similar to what download_chapter_content in royalroad_fetcher might return
    sample_rr_html = """
    <html>
    <head>
        <title>Chapter Title</title>
        <script>alert('This is a script');</script>
        <style>.useless { color: blue; }</style>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <header>Site Header</header>
        <nav>Navigation Menu</nav>
        <div class="main-story-container">
            <div class="chapter-content">
                <h1>Actual Chapter Title</h1>
                <p style="color: red;" class="first-paragraph">This is the first paragraph of the story.</p>
                <div class="author-notes-start">Author notes here, should be removed.</div>
                <p>This is the second paragraph, with <strong>bold text</strong> and <em>italic text</em>.</p>
                <script type="text/javascript">
                    // Another script
                    console.log("Hello");
                </script>
                <p>A paragraph with a <a href="http://example.com" onclick="return false;">link that has JS</a>.</p>
                <div id="comments">Comments section that should be removed.</div>
                <p></p> <!-- Empty paragraph -->
                <p>   </p> <!-- Paragraph with only spaces -->
                <p>Final paragraph.</p>
            </div>
            <div class="sidebar">
                <div class="portlet">Sidebar content, should not be included.</div>
            </div>
        </div>
        <footer>Site Footer</footer>
    </body>
    </html>
    """

    print("--- Cleaning RoyalRoad Sample HTML ---")
    cleaned_rr_html = cleaner.clean_html(sample_rr_html, source_site="royalroad")
    print(cleaned_rr_html)

    # Test case 2: HTML without the specific 'chapter-content' div
    sample_generic_html = """
    <html>
    <body>
        <script>alert("test");</script>
        <h1>Title</h1>
        <p>Some content here.</p>
        <style>.data { font-weight: bold; }</style>
        <p>More content.</p>
    </body>
    </html>
    """
    print("\n--- Cleaning Generic Sample HTML (simulating no 'chapter-content' div) ---")
    # When 'chapter-content' is not found, it should attempt to clean the whole thing.
    # We can simulate this by passing a different source_site or if RoyalRoad page structure changes.
    cleaned_generic_html = cleaner.clean_html(sample_generic_html, source_site="generic_site_test")
    print(cleaned_generic_html)

    # Test case 3: HTML that IS ONLY the chapter-content (as if pre-selected)
    sample_only_chapter_div_html = """
    <div class="chapter-content">
        <p>Only content here.</p>
        <script>console.log("Should be gone");</script>
        <div class="author-notes-start">Author notes here, should be removed.</div>
    </div>
    """
    print("\n--- Cleaning HTML that is only chapter-content div ---")
    cleaned_only_chapter_div_html = cleaner.clean_html(sample_only_chapter_div_html, source_site="royalroad")
    # Since the input itself is the div, the first step of selecting .chapter-content will work on it.
    print(cleaned_only_chapter_div_html)
