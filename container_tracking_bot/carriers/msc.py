import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from carriers.base import BaseTracker
from config import BROWSER, HEADLESS, WAIT_TIME, MSC_TRACKING_URL
from utils.logger import logger
from utils.text_utils import detect_captcha_or_manual_required, extract_date_from_text, normalize_text

class MSCTracker(BaseTracker):
    """
    MSCTracker automates tracking container numbers on the MSC website.
    It inherits from BaseTracker and implements the Selenium automation workflow.
    """

    def __init__(self):
        self.driver = None

    def _init_driver(self):
        """Initializes and returns the Selenium Chrome webdriver."""
        logger.info("Initializing Selenium Chrome WebDriver...")
        chrome_options = Options()
        
        if HEADLESS:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            
        chrome_options.add_argument("--start-maximized")
        # Exclude the collection of enable-automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        # Use a premium user agent to reduce bot detection
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Bypass Cloudflare/Imperva detection flags
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Script execution override for webdriver flag
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

    def close(self):
        """Closes the browser instance if open."""
        if self.driver:
            logger.info("Closing browser...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            finally:
                self.driver = None

    def _accept_cookies(self):
        """Handles the cookie acceptance pop-up if it appears."""
        cookie_selectors = [
            (By.ID, "onetrust-accept-btn-handler"),
            (By.XPATH, "//button[contains(text(), 'Accept All')]"),
            (By.XPATH, "//button[contains(@class, 'accept')]"),
            (By.CSS_SELECTOR, "button[id*='accept']"),
            (By.CSS_SELECTOR, "button[class*='cookie']")
        ]
        
        for by, selector in cookie_selectors:
            try:
                element = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                element.click()
                logger.info(f"Accepted cookies using selector: {selector}")
                time.sleep(1)
                return
            except Exception:
                continue
        logger.debug("No cookie banner appeared or could not click it.")

    def track(self, container_no: str, bl_no: str = None) -> dict:
        """
        Navigates to MSC tracking website and crawls details for a container.
        """
        result = {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "",
            "TrackingStatus": "Failed",
            "Remarks": "",
            "TrackingURL": f"{MSC_TRACKING_URL}?trackingNumber={container_no}",
            "TrackedAt": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }

        try:
            if not self.driver:
                self._init_driver()

            # Only navigate to the tracking URL if we are not already on it
            current_url = self.driver.current_url if self.driver.current_url else ""
            if "track-a-shipment" not in current_url:
                logger.info(f"Navigating to MSC URL: {MSC_TRACKING_URL}")
                self.driver.get(MSC_TRACKING_URL)
                # Wait for page JavaScript to fully render (MSC page is JS-heavy)
                time.sleep(5)
                # Step 1: Accept cookies (only needed on first visit)
                self._accept_cookies()
            else:
                logger.info("Already on tracking page, reusing existing session for next container...")
                # Small wait to mimic human delay before entering next tracking number
                time.sleep(2)

            # Step 2: Search input selectors.
            # NOTE: On the MSC tracking page, the input has id='trackingNumber' but name='' (empty).
            # So By.ID must be the primary selector. By.NAME will NOT work.
            input_selectors = [
                (By.ID, "trackingNumber"),
                (By.CSS_SELECTOR, "input[id='trackingNumber']"),
                (By.CSS_SELECTOR, "input[placeholder*='Container']"),
                (By.CSS_SELECTOR, "input[placeholder*='Lading']"),
                (By.CSS_SELECTOR, "input[placeholder*='Bill of']"),
                (By.CSS_SELECTOR, "input[placeholder*='track']"),
            ]
            
            search_input = None
            for by, selector in input_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 15).until(
                        EC.visibility_of_element_located((by, selector))
                    )
                    logger.info(f"Found input field using selector: ({by}, {selector})")
                    break
                except Exception:
                    continue
            
            if not search_input:
                raise Exception("Could not find the container tracking input field on the page.")

            # Ensure we are at the top of the page so sticky headers don't block the input
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

            # Clear and populate the input field robustly
            try:
                # Use JS to focus and clear to avoid click interception
                self.driver.execute_script("arguments[0].focus(); arguments[0].value = '';", search_input)
                # Also try normal clear just in case JS clear didn't trigger React/Angular events
                search_input.clear()
            except Exception:
                pass
                
            search_input.send_keys(container_no)
            logger.info(f"Entered container number: {container_no}")
            time.sleep(1)

            # Step 3: Submit using Enter key on input field.
            # IMPORTANT: We do NOT click button[type='submit'] because MSC's submit button
            # triggers an authentication redirect to mscciam.b2clogin.com (login page).
            # Pressing Enter on the input field performs a guest/public tracking search,
            # exactly like the original Power Automate subflow which used
            # PopulateTextFieldUsePhysicalKeyboard with UnfocusAfterPopulate:True then PressButton.
            logger.info("Pressing Enter on input field to trigger tracking search (avoids login redirect)...")
            search_input.send_keys(Keys.RETURN)

            # Wait for tracking results page to fully load (MSC results load via JS)
            logger.info("Waiting for tracking results page to load...")
            time.sleep(10)
            
            # Also wait for page readyState == complete
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except Exception:
                pass

            # Step 4: Check for CAPTCHA/Manual Block
            html_content = self.driver.page_source
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            current_url = self.driver.current_url.lower()
            
            if detect_captcha_or_manual_required(html_content, page_text) or "b2clogin" in current_url or "identityserver" in current_url:
                result["TrackingStatus"] = "Manual Required"
                result["Remarks"] = "CAPTCHA, login, or blocking page detected (Manual Required)."
                logger.warning(f"CAPTCHA / Login / Bot detection page found for container {container_no} at URL: {self.driver.current_url}")
                return result

            # Step 5: Check if No Data / Not Found
            no_data_indicators = [
                "no container found",
                "no tracking information found",
                "check the spelling",
                "number is invalid",
                "please check your container number",
                "no results",
                "not found"
            ]
            for ind in no_data_indicators:
                if ind in page_text.lower():
                    result["TrackingStatus"] = "No Data Found"
                    result["Remarks"] = "No tracking information returned for this container."
                    logger.info(f"No tracking data found for container {container_no}")
                    return result

            # Step 6: Extract tracking data
            # We'll use a dynamic text parsing approach as well as fallbacks for the labels.
            self._extract_tracking_details(result)

        except Exception as e:
            logger.error(f"Exception while tracking container {container_no}: {str(e)}")
            result["TrackingStatus"] = "Failed"
            result["Remarks"] = f"Error during tracking: {str(e)}"
            
        return result

    def _extract_tracking_details(self, result_dict):
        """
        Parses the active MSC tracking result page to extract dates and status.
        
        MSC page structure (as seen in live page):
          - ETA (Primary): CSS selector span.data-value inside the 4th cell of the open
            tracking bar:
            #main > div.msc-flow-tracking... > div.msc-flow-tracking__cell--four > ... > span.data-value
          - ETA (Fallback): "POD ETA" label text scan -> date on next line (DD/MM/YYYY)
          - Movement history rows contain: Date | Location | Description | Vessel/Voyage
          - "Export Loaded on Vessel" row date --> ETD
          - "Estimated Time of Arrival" row --> confirms ETA (fallback)
          - Latest/first move description in history --> CurrentStatus
          - Vessel name in format "MSC <NAME> <VOYAGE>" in the Vessel/Voyage column
        """
        import re

        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            body_lines = [line.strip() for line in body_text.split('\n') if line.strip()]

            logger.info("Scanning MSC result page text for shipment data...")

            # Date pattern DD/MM/YYYY
            date_pattern = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')

            # -------------------------------------------------------
            # Step 1 (Primary): Extract ETA via precise CSS selector
            # Selector targets span.data-value inside the 4th tracking cell
            # of the open container bar on the MSC tracking results page.
            # -------------------------------------------------------
            ETA_CSS_SELECTOR = "div.msc-flow-tracking__bar.open div.msc-flow-tracking__cell--four span.data-value"
            try:
                eta_element = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, ETA_CSS_SELECTOR))
                )
                raw_eta = eta_element.text.strip()
                logger.info(f"ETA element found via CSS selector. Raw value: '{raw_eta}'")
                if raw_eta:
                    dt = extract_date_from_text(raw_eta)
                    if dt:
                        result_dict["ETA"] = dt.strftime("%d-%m-%Y")
                        logger.info(f"Extracted ETA via CSS selector: {result_dict['ETA']}")
                    else:
                        logger.warning(f"Could not parse date from ETA element text: '{raw_eta}'")
            except Exception as css_ex:
                logger.warning(f"CSS selector ETA extraction failed ({css_ex}), falling back to text scan...")

            # -------------------------------------------------------
            # Step 1 (Fallback): Extract ETA from "POD ETA" label in body text
            # The page has "POD ETA" on one line then the date on the next
            # -------------------------------------------------------
            if not result_dict["ETA"]:
                for i, line in enumerate(body_lines):
                    if line.strip().upper() in ("POD ETA", "ETA", "ESTIMATED TIME OF ARRIVAL"):
                        for offset in range(1, 4):
                            if i + offset < len(body_lines):
                                m = date_pattern.search(body_lines[i + offset])
                                if m:
                                    dt = extract_date_from_text(m.group(1))
                                    if dt:
                                        result_dict["ETA"] = dt.strftime("%d-%m-%Y")
                                        logger.info(f"Fallback ETA from '{line}' label: {result_dict['ETA']}")
                                    break

            # -------------------------------------------------------
            # Step 2: Extract ETD by finding the tracking step row where
            # the Description cell contains "Export Loaded on Vessel",
            # then reading the date from the date cell (cell--two) of
            # that same row.
            # -------------------------------------------------------
            try:
                # All step rows live inside div.msc-flow-tracking__steps
                step_rows = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.msc-flow-tracking__steps > div"
                )
                logger.info(f"Found {len(step_rows)} tracking step rows for ETD scan.")
                for step_row in step_rows:
                    try:
                        # Description is in msc-flow-tracking__cell--three
                        desc_cells = step_row.find_elements(
                            By.CSS_SELECTOR,
                            "div.msc-flow-tracking__cell--three"
                        )
                        desc_text = " ".join(c.text.strip() for c in desc_cells).upper()

                        if "EXPORT LOADED ON VESSEL" in desc_text or "LOADED ON VESSEL" in desc_text:
                            # Date is in msc-flow-tracking__cell--two in the same row
                            date_cells = step_row.find_elements(
                                By.CSS_SELECTOR,
                                "div.msc-flow-tracking__cell--two"
                            )
                            raw_etd = " ".join(c.text.strip() for c in date_cells)
                            logger.info(f"Found 'Export Loaded on Vessel' row. Raw ETD text: '{raw_etd}'")
                            dt = extract_date_from_text(raw_etd)
                            if dt:
                                result_dict["ETD"] = dt.strftime("%d-%m-%Y")
                                logger.info(f"Extracted ETD from row DOM: {result_dict['ETD']}")
                                break
                            else:
                                logger.warning(f"Could not parse date from ETD row text: '{raw_etd}'")
                    except Exception:
                        continue
            except Exception as etd_dom_ex:
                logger.warning(f"DOM row-scan ETD extraction failed ({etd_dom_ex}), falling back to text scan...")

            # ETD Fallback: body-text scan for "Export Loaded on Vessel"
            if not result_dict["ETD"]:
                for i, line in enumerate(body_lines):
                    if "EXPORT LOADED ON VESSEL" in line.upper() or "LOADED ON VESSEL" in line.upper():
                        for offset in range(1, 5):
                            if i - offset >= 0:
                                m = date_pattern.search(body_lines[i - offset])
                                if m:
                                    dt = extract_date_from_text(m.group(1))
                                    if dt:
                                        result_dict["ETD"] = dt.strftime("%d-%m-%Y")
                                        logger.info(f"Fallback ETD from body text 'Export Loaded on Vessel': {result_dict['ETD']}")
                                    break

                pass

                # (CurrentStatus extracted via CSS selector in Step 4 below; text scan is fallback only)

            # -------------------------------------------------------
            # Step 4 (Primary): Extract CurrentStatus (Last Move) via CSS selector.
            # The selector targets span.data-value inside the "Latest move" cell
            # (msc-flow-tracking__cell--three msc-flow-tracking__cell--delivered).
            # -------------------------------------------------------
            LAST_MOVE_CSS_SELECTOR = "div.msc-flow-tracking__bar.open div.msc-flow-tracking__cell--three span.data-value"
            try:
                last_move_el = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, LAST_MOVE_CSS_SELECTOR))
                )
                last_move_text = last_move_el.text.strip()
                if last_move_text:
                    result_dict["CurrentStatus"] = last_move_text
                    logger.info(f"Extracted CurrentStatus (Last Move) via CSS: '{last_move_text}'")
                else:
                    logger.warning("Last Move CSS element found but text is empty.")
            except Exception as lm_ex:
                logger.warning(f"Last Move CSS extraction failed ({lm_ex}), falling back to text scan...")

            # Fallback: keyword scan in body text
            if not result_dict["CurrentStatus"]:
                status_keywords = [
                    "full transshipment discharged", "full transshipment loaded",
                    "export loaded on vessel", "export received at cy",
                    "empty to shipper", "carrier release",
                    "estimated time of arrival", "arrived", "discharged",
                    "gate in", "gate out", "customs", "delivery"
                ]
                for body_line in body_lines:
                    for kw in status_keywords:
                        if kw in body_line.lower():
                            result_dict["CurrentStatus"] = body_line.strip()
                            logger.info(f"Fallback CurrentStatus from body text: '{result_dict['CurrentStatus']}'")
                            break
                    if result_dict["CurrentStatus"]:
                        break

            # -------------------------------------------------------
            # Step 3: Fallback - if ETA still empty, try "Estimated Time of Arrival" row
            # -------------------------------------------------------
            if not result_dict["ETA"]:
                for i, line in enumerate(body_lines):
                    if "ESTIMATED TIME OF ARRIVAL" in line.upper():
                        for offset in range(1, 4):
                            if i - offset >= 0:
                                m = date_pattern.search(body_lines[i - offset])
                                if m:
                                    dt = extract_date_from_text(m.group(1))
                                    if dt:
                                        result_dict["ETA"] = dt.strftime("%d-%m-%Y")
                                        logger.info(f"Fallback ETA from 'Estimated Time of Arrival': {result_dict['ETA']}")
                                    break

            # -------------------------------------------------------
            # Step 4: Log summary and determine final status
            # -------------------------------------------------------
            if not result_dict["ETD"] and not result_dict["ETA"]:
                result_dict["TrackingStatus"] = "No Data Found"
                result_dict["Remarks"] = "No departure or arrival dates found on the page."
            else:
                result_dict["TrackingStatus"] = "Success"
                result_dict["Remarks"] = "Tracking data successfully parsed."

            logger.info(
                f"Tracking complete - ETD={result_dict['ETD']}, ETA={result_dict['ETA']}, "
                f"Vessel={result_dict['Vessel']}, Voyage={result_dict['Voyage']}, "
                f"CurrentStatus={result_dict['CurrentStatus']}, Status={result_dict['TrackingStatus']}"
            )

        except Exception as ex:
            logger.error(f"Error parsing tracking details: {str(ex)}")
            if result_dict["ETD"] or result_dict["ETA"]:
                result_dict["TrackingStatus"] = "Success"
                result_dict["Remarks"] = f"Partial parsing success: {str(ex)}"
            else:
                raise ex


