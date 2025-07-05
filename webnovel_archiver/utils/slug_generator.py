import re
import unicodedata

def generate_slug(text: str) -> str:
    """
    Generates a URL-friendly slug from a given string.

    Args:
        text: The input string (e.g., a story title).

    Returns:
        A clean, lowercase, hyphen-separated slug.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")

    # Normalize Unicode characters to their closest ASCII equivalents
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric characters (except hyphens) with hyphens
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    # Remove multiple hyphens
    text = re.sub(r'-+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text
