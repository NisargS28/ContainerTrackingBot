import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Input Excel file — all sheets inside this are processed one by one
# File lives one level above the bot directory
INPUT_FILE = os.path.join(
    os.path.dirname(BASE_DIR), "Export Sheet 2026-27.xlsx"
)

# Reference output file — tracking results are written back into this workbook,
# one sheet per source sheet name (e.g. "EOU", "Mundra Unit-I" …)
OUTPUT_REFERENCE_FILE = os.path.join(
    os.path.dirname(BASE_DIR), "Copy of bl_full_with delivery.xlsx"
)

# Log file
LOG_FILE = os.path.join(OUTPUT_DIR, "run_log.txt")

# Browser Configuration
BROWSER = "chrome"
HEADLESS = False  # Set to True if headless browser is desired
WAIT_TIME = 30    # General web driver wait timeout in seconds

# Tracking Settings
DELAY_BETWEEN_TRACKING = 5  # Delay between requests in seconds to avoid anti-bot flags
MAX_RETRIES = 2             # Retry limit for intermittent failures

# Carrier URLs
MSC_TRACKING_URL = "https://www.msc.com/en/track-a-shipment"
