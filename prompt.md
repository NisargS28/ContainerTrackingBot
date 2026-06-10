I want to build this project step by step.

For Phase 1, implement ONLY MSC container tracking automation in Python Selenium.

Do not implement CMA, ONE, Maersk, Hapag, or other shipping lines yet.
Only create the project structure in such a way that other carriers can be added later.

I have a file named main_flow.txt copied from my existing Power Automate Desktop flow.
Read and understand main_flow.txt first.

Important logic from main_flow.txt:
- It opens an Excel file.
- It loops through all worksheets.
- It reads data from:
  - Column 1 = S/Line
  - Column 2 = B/L
  - Column 3 = Container No.
  - Column 9 = Delivery Status
- It starts from row 2.
- It skips row if B/L is blank.
- It checks shipping line name.
- If S/Line contains "MSC", then it adds the container to MSC_List only if:
  - Delivery Status contains "Not", OR
  - Delivery Status is empty
- It stores MSC list item like:
  ContainerNo|||ExcelRow
- Later it removes duplicate items from MSC_List.
- Then it opens MSC tracking website:
  https://www.msc.com/en/track-a-shipment
- Then for each item in MSC_List, it splits by "|||", gets container number and original Excel row, and calls MSC subflow.

Now convert only this MSC part into Python Selenium.

Goal of Phase 1:
Create a working Python project that:
1. Reads Excel file.
2. Loops through all worksheets.
3. Filters only MSC rows.
4. Creates MSC_List.
5. Tracks MSC containers on MSC website.
6. Extracts ETD and ETA.
7. Writes results to output Excel.
8. Also optionally updates a copy of original Excel with MSC tracking result.

Technical requirements:
- Use Python 3.
- Use Selenium.
- Use pandas.
- Use openpyxl.
- Use webdriver-manager.
- Browser should be visible by default, not headless.
- Do not bypass CAPTCHA.
- If CAPTCHA or login appears, mark that record as "Manual Required".
- Use WebDriverWait.
- Use proper exception handling.
- If one container fails, continue with next container.
- Save output even if some records fail.
- Add logs.

Project structure:
container_tracking_bot/
  main.py
  config.py
  requirements.txt
  README.md
  carriers/
    __init__.py
    base.py
    msc.py
  utils/
    __init__.py
    excel_handler.py
    logger.py
    text_utils.py
  input/
    Export.xlsx
  output/
    msc_tracking_output.xlsx
    msc_list.xlsx
    updated_original_with_msc_tracking.xlsx
    run_log.txt

Important:
Even though only MSC is implemented now, keep architecture modular so later I can add:
- CMA
- ONE
- Maersk
- Hapag

Input Excel handling:
- Input file path should be in config.py.
- Default input path:
  input/Export.xlsx
- Process all worksheets.
- Start reading from row 2.
- Use column position as primary logic:
  - Column 1: S/Line
  - Column 2: B/L
  - Column 3: Container No.
  - Column 9: Delivery Status
- Also support column names if available:
  - S/Line
  - B/L
  - Container No.
  - Delivery Status
- Skip row if B/L is blank.
- Select only rows where S/Line contains "MSC", case-insensitive.
- Select only rows where Delivery Status is blank or contains "Not", case-insensitive.
- Preserve:
  - SheetName
  - OriginalExcelRow
  - SLine
  - BLNo
  - ContainerNo
  - DeliveryStatus
- Remove duplicates based on ContainerNo + BLNo + SheetName.
- Export MSC list to:
  output/msc_list.xlsx

MSC tracking:
- Open:
  https://www.msc.com/en/track-a-shipment
- For each MSC container number:
  - Search container number.
  - Wait for result.
  - Extract ETD and ETA.
  - If possible also extract:
    - Vessel
    - Voyage
    - CurrentStatus
- If data is not found, mark:
  TrackingStatus = "No Data Found"
- If CAPTCHA, login, blocked page, or manual action required appears, mark:
  TrackingStatus = "Manual Required"
- If exception occurs, mark:
  TrackingStatus = "Failed"

Output Excel:
Create:
output/msc_tracking_output.xlsx

Columns:
- SheetName
- OriginalExcelRow
- SLine
- Carrier
- BLNo
- ContainerNo
- DeliveryStatus
- ETD
- ETA
- Vessel
- Voyage
- CurrentStatus
- TrackingStatus
- Remarks
- TrackingURL
- TrackedAt

Also create Summary sheet:
- Total MSC Records
- Success
- Failed
- Manual Required
- No Data Found

Updated original workbook:
- Do not modify original Excel file.
- Create copy:
  output/updated_original_with_msc_tracking.xlsx
- Add new columns if not already present:
  - MSC_ETD
  - MSC_ETA
  - MSC_TrackingStatus
  - MSC_Remarks
  - MSC_TrackedAt
- Write results back to correct worksheet and correct original Excel row using SheetName and OriginalExcelRow.

Code design:
- config.py should contain:
  INPUT_FILE = "input/Export.xlsx"
  OUTPUT_DIR = "output"
  BROWSER = "chrome"
  HEADLESS = False
  WAIT_TIME = 30
  DELAY_BETWEEN_TRACKING = 5
  MAX_RETRIES = 2
  MSC_TRACKING_URL = "https://www.msc.com/en/track-a-shipment"

- carriers/base.py:
  Create BaseTracker class.

- carriers/msc.py:
  Create MSCTracker class.
  It should inherit or follow BaseTracker.
  It should have:
    track(container_no, bl_no=None) -> dict

- utils/excel_handler.py:
  Functions for:
    read_input_workbook()
    extract_msc_rows()
    save_msc_list()
    save_tracking_output()
    update_original_copy()

- utils/text_utils.py:
  Functions for:
    clean_container_number()
    normalize_text()
    extract_date_from_text()
    detect_captcha_or_manual_required()

- utils/logger.py:
  Setup logging to console and output/run_log.txt.

MSC website selector instructions:
- Use robust selectors.
- Try multiple fallback selectors for input box:
  - input[type='text']
  - input[placeholder*='track']
  - input[placeholder*='container']
  - input[aria-label*='track']
  - input[aria-label*='container']
- Add clear comments where selectors may need manual update.
- After search, parse the result page.
- First try exact selectors if identifiable.
- If exact selectors are uncertain, use page body text and extract dates near keywords:
  - ETA
  - ETD
  - Estimated Arrival
  - Estimated Departure
  - Arrival
  - Departure
- Make parsing function separate so it can be improved later.

Deliverables:
1. Full Python project files.
2. requirements.txt.
3. README.md.
4. Code should be runnable.
5. Do not implement other shipping lines in Phase 1.
6. Add placeholder files/comments showing that CMA, ONE, Maersk, and Hapag will be added in later phases, but do not code them yet.

Before coding:
First summarize your understanding of main_flow.txt and explain how you will implement only MSC phase.
Then create the project files.
Then explain how to run:
  pip install -r requirements.txt
  python main.py

  I am also providing my MSC subflow exported from Power Automate.
Use main_flow.txt for master Excel/list logic.
Use MSC subflow txt for exact MSC browser steps.

Important:
Do not blindly copy Power Automate actions.
Convert the logic into clean Python Selenium code.
Preserve the same behavior:
- open MSC website
- search container
- extract ETD/ETA
- write result to correct Excel row
- handle failed/no data/manual cases


I want to implement phase wise, now let's start with Phase 1 only MSC.

I have already uploaded "main_flow.txt" to the project folder.
Use it to understand master Excel loop and MSC_List logic.

Next, create a sub-folder "subflows" inside container_tracking_bot/.
In "subflows/", create "MSC_Track_Container.txt".

In MSC_Track_Container.txt, I will copy the exact subflow logic from my Power Automate:
- Open MSC tracking website.
- Fill container number.
- Click Search.
- Wait for result.
- Extract ETD and ETA.
- Mark errors if CAPTCHA/block/no result.

For Phase 1, your job:
1. Read "main_flow.txt" from container_tracking_bot/.
2. Understand:
   - Which columns to read (S/Line, B/L, Container No., Delivery Status).
   - How to build MSC_List (only MSC containers with empty/“Not” Delivery Status).
   - How to split container + excel row by "|||".
3. After building MSC_List in memory, open "subflows/MSC_Track_Container.txt".
4. Convert that subflow into a Python Selenium function in:
   carriers/msc.py
5. The Python function should:
   - Accept:
     - container_number
     - original_excel_row
     - sheet_name
   - Open:
     https://www.msc.com/en/track-a-shipment
   - Follow the same steps as in MSC_Track_Container.txt.
   - Extract:
     - ETD
     - ETA
   - Mark:
     - "Success"
     - "Manual Required" if CAPTCHA or login or block appears
     - "No Data Found" if result not found
     - "Failed" for any exception
   - Log every step to console and log file.

Once the MSC subflow is converted, update main.py:
- Run MSC_List creation.
- Call the MSC tracking function for each item in MSC_List.
- Save results to output/msc_tracking_output.xlsx.
- Also update:
  output/updated_original_with_msc_tracking.xlsx
  preserving original formatting and sheet structure.

Deliverables:
1. Add file "subflows/MSC_Track_Container.txt".
2. Implement MSC tracking in:
   carriers/msc.py
   in a function:
   track(container_no, original_excel_row, sheet_name)
3. Update main.py to:
   - Read main_flow.txt.
   - Create MSC_List.
   - Call the MSC tracking function.
   - Save output.
4. Keep the code modular so that later CMA, ONE, Maersk, Hapag can be added easily in:
   carriers/cma.py
   carriers/one.py
   carriers/maersk.py
   carriers/hapag.py

Start with:
1. Create subflows/MSC_Track_Container.txt from my Power Automate MSC subflow.
2. Convert it into Python Selenium function in carriers/msc.py.
3. Update main.py to use it.