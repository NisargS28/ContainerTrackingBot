import re
from datetime import datetime
from utils.logger import logger

def clean_container_number(container_no):
    """
    Cleans and validates a container number.
    Typical container number structure is 4 alphabetic characters followed by 7 digits (e.g. MSCU1234567).
    """
    if not container_no:
        return ""
    
    # Cast to string and remove all whitespace
    clean_no = str(container_no).strip().replace(" ", "").upper()
    
    # Optional check: standard ISO 6346 container validation is 4 letters + 7 digits
    if re.match(r'^[A-Z]{4}\d{7}$', clean_no):
        return clean_no
    
    # If it doesn't match perfectly, return stripped alphanumeric
    alphanumeric_only = re.sub(r'[^A-Z0-9]', '', clean_no)
    logger.debug(f"Cleaned container number '{container_no}' to '{alphanumeric_only}'")
    return alphanumeric_only

def normalize_text(text):
    """Trims whitespace and returns an empty string if None."""
    if text is None:
        return ""
    return str(text).strip()

def extract_date_from_text(text):
    """
    Attempts to parse date from typical formats found in tracking pages (e.g. DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD).
    Returns datetime object or None if failed.
    """
    if not text:
        return None
    
    text = normalize_text(text)
    
    # Try different format matchers
    formats = [
        "%d/%m/%Y",  # 21/04/2026
        "%d-%m-%Y",  # 21-04-2026
        "%Y-%m-%d",  # 2026-04-21
        "%d %b %Y",  # 21 Apr 2026
        "%b %d, %Y", # Apr 21, 2026
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
            
    # Try matching regex for dates in long texts if exact parsing fails
    date_regexes = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD-MM-YYYY or DD/MM/YYYY
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'   # YYYY-MM-DD
    ]
    for pattern in date_regexes:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(0)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
                    
    return None

def detect_captcha_or_manual_required(html_content, page_text):
    """
    Detects if the page contains signs of WAF blocking, CAPTCHA, Cloudflare,
    Imperva, or login redirections requiring manual interaction.
    """
    if not html_content:
        return False
        
    html_lower = html_content.lower()
    text_lower = page_text.lower() if page_text else ""
    
    indicators = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "g-recaptcha",
        "security check",
        "human verification",
        "verify you are a human",
        "checking your browser",
        "ddos",
        "b2clogin",
        "authorize?p="
    ]
    
    for indicator in indicators:
        if indicator in html_lower or indicator in text_lower:
            logger.warning(f"Detection warning: CAPTCHA / WAF / Block indicator found: '{indicator}'")
            return True
            
    return False
