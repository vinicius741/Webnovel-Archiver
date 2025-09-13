import datetime
import re
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

def format_timestamp(iso_timestamp_str):
    if not iso_timestamp_str:
        return None
    try:
        dt_obj = datetime.datetime.fromisoformat(iso_timestamp_str.replace('Z', '+00:00'))
        return dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z') # Include timezone
    except ValueError:
        logger.warning(f"Could not parse timestamp: {iso_timestamp_str}", exc_info=True)
        return iso_timestamp_str # Return original if parsing fails

def sanitize_for_css_class(text):
    if not text: return ""
    processed_text = str(text).lower()
    # Replace common separators with hyphens
    processed_text = processed_text.replace(' ', '-').replace('(', '').replace(')', '').replace('/', '-').replace('.', '')
    # Remove any remaining non-alphanumeric characters except hyphens
    processed_text = re.sub(r'[^a-z0-9-]', '', processed_text)
    return processed_text.strip('-')
