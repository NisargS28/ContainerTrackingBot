# Container Tracking Bot - Phase 1 (MSC)

An automated container tracking solution using Python, Selenium, pandas, and openpyxl. This application reads a shipping logistics workbook, filters and lists MSC containers needing tracking, crawls the official MSC tracking site using a dynamic browser-based agent, and writes tracking updates (ETD, ETA, Vessel, Voyage, Current Status) back into standardized result Excel files.

## Project Structure

```
container_tracking_bot/
  main.py                # Main orchestrator script
  config.py              # Configuration settings (paths, timing, browser specs)
  requirements.txt       # Python dependencies
  README.md              # Project documentation
  carriers/              # Module representing shipping line crawlers
    __init__.py
    base.py              # Abstract base tracker class
    msc.py               # MSC container crawler (implemented via Selenium)
    cma.py               # CMA CGM tracker placeholder
    one.py               # ONE Line tracker placeholder
    maersk.py            # Maersk tracker placeholder
    hapag.py             # Hapag-Lloyd tracker placeholder
  utils/                 # Helper utilities
    __init__.py
    excel_handler.py     # Reads/writes sheets, converts 9-column sheets to standardized 7-column format
    logger.py            # Event logger (writes to stdout & output/run_log.txt)
    text_utils.py        # Text cleanups, date parsing, and WAF/CAPTCHA check
  subflows/
    MSC_Track_Container.txt # Reference Power Automate subflow description
  input/
    Export.xlsx          # Source tracking spreadsheet (copied on startup if empty)
  output/
    msc_list.xlsx        # Output list of MSC candidates extracted from input
    msc_tracking_output.xlsx # Output details and tracking summary worksheet
    updated_original_with_msc_tracking.xlsx # Copy of the source workbook with standardized 7-column sheets containing updates
    run_log.txt          # Event runtime log file
```

## Prerequisites

- Python 3.8 or higher.
- Chrome Browser installed on your system.

## Setup Instructions

1. Navigate to the project root directory:
   ```bash
   cd container_tracking_bot
   ```

2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure you have the source workbook placed at `input/Export.xlsx`. 
   *(Note: On initial startup, if no file is present at `input/Export.xlsx`, the script will copy the default copy `Copy of bl_full_with delivery.xlsx` from the parent directory.)*

## Running the Automation

To run the tracking bot, execute the main script:
```bash
python main.py
```

### Automation Details
- By default, the browser is visible (`HEADLESS = False` in `config.py`).
- The bot will dynamically detect the columns from each worksheet, filters rows where Carrier is `MSC` and `DELIVERY STATUS` is empty or contains `Not`.
- If a security challenge (CAPTCHA / Cloudflare block) is triggered on the site, the bot marks the status as `Manual Required` and continues with the next container.
- Results are saved progressively to avoid data loss.
- In the updated workbook `output/updated_original_with_msc_tracking.xlsx`, all worksheets are standardized to the 7-column layout (`S/LINE`, `CONTAINER NO.`, `ETD`, `ETA AT PORT`, `STATUS`, `CURRENT DATE & TIME`, `DELIVERY STATUS`), formatting and aligning cells.
