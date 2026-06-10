from carriers.base import BaseTracker
from datetime import datetime
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import HEADLESS, WAIT_TIME


class HapagTracker(BaseTracker):
    """
    Hapag-Lloyd Tracking Implementation.
    Handles Cloudflare "Verify you are human" checkbox,
    cookie consent ("Confirm My Choices"), and extracts
    Last Move (location only), ETA (from last "Vessel arrival" row),
    and ETD.
    """

    def __init__(self):
        self.driver = None
        self.chrome_process = None
        self._first_load = True  # Track whether cookie consent is needed

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------
    def _init_driver(self):
        import os
        chrome_options = Options()
        self.chrome_process = None
        
        # Check if we are running headful and can use remote debugging
        if not HEADLESS:
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            chrome_path = None
            for p in chrome_paths:
                if os.path.exists(p):
                    chrome_path = p
                    break
                    
            if chrome_path:
                try:
                    import subprocess
                    debug_port = 9222
                    user_data_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scratch", "chrome_debug_profile"
                    )
                    os.makedirs(user_data_dir, exist_ok=True)
                    
                    cmd = [
                        chrome_path,
                        f"--remote-debugging-port={debug_port}",
                        f"--user-data-dir={user_data_dir}",
                        "--start-maximized",
                        "--no-first-run",
                        "--disable-default-apps",
                        "--disable-extensions",
                    ]
                    # Launch Chrome
                    self.chrome_process = subprocess.Popen(cmd)
                    time.sleep(5)
                    
                    # Connect Selenium
                    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.set_page_load_timeout(WAIT_TIME)
                    print("Chrome launched successfully in remote debugging mode.")
                    return
                except Exception as e:
                    print(f"Failed to launch Chrome in remote debugging mode: {e}. Falling back to standard driver.")
                    if self.chrome_process:
                        try:
                            self.chrome_process.terminate()
                        except Exception:
                            pass
                        self.chrome_process = None

        # Standard driver fallback
        if HEADLESS:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_page_load_timeout(WAIT_TIME)

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
        if hasattr(self, 'chrome_process') and self.chrome_process:
            try:
                self.chrome_process.terminate()
            except Exception:
                pass
            self.chrome_process = None

    # ------------------------------------------------------------------
    # Cloudflare bypass helper
    # ------------------------------------------------------------------
    def _handle_cloudflare(self, driver, timeout=15):
        """
        Waits for the Cloudflare "Security Check" / "Verify you are human"
        text to appear and clicks the checkbox using coordinates extraction
        with ActionChains and pyautogui.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        
        for attempt in range(1, 4):
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if "Security Check" not in body_text and "Verify you are human" not in body_text:
                    return  # No challenge visible – nothing to do

                print(f"Cloudflare challenge detected. Attempt {attempt}/3...")
                time.sleep(2)  # slow down so Cloudflare doesn't flag us

                # Locate the container element
                target_element = None
                for selector in ["#BbLB6", ".cf-turnstile", "iframe[src*='challenges.cloudflare.com']"]:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            target_element = elements[0]
                            print(f"Found Cloudflare element using selector: {selector}")
                            break
                    except Exception:
                        continue

                if target_element:
                    # 1. Extract X and Y position coordinates
                    location = target_element.location
                    size = target_element.size
                    x_coord = location['x']
                    y_coord = location['y']
                    print(f"Element coordinates: X={x_coord}, Y={y_coord}, Width={size['width']}, Height={size['height']}")

                    # Try clicking at the checkbox offset using ActionChains
                    try:
                        click_x = x_coord + 30
                        click_y = y_coord + (size['height'] // 2 if size['height'] > 0 else 30)
                        print(f"Moving to viewport coords ({click_x}, {click_y}) via ActionChains and clicking...")
                        actions = ActionChains(driver)
                        actions.move_by_offset(click_x, click_y).click().perform()
                        time.sleep(6)
                        
                        body_text = driver.find_element(By.TAG_NAME, "body").text
                        if "Security Check" not in body_text and "Verify you are human" not in body_text:
                            print("Cloudflare challenge bypassed via ActionChains!")
                            return
                    except Exception as e:
                        print(f"ActionChains click failed: {e}")

                    # Try fallback to pyautogui screen coordinates
                    try:
                        import pyautogui
                        # Enable pyautogui failsafe
                        pyautogui.FAILSAFE = True
                        pyautogui.PAUSE = 0.3

                        # Get window rect
                        window_rect = driver.execute_script("""
                            return {
                                screenX: window.screenX || window.screenLeft || 0,
                                screenY: window.screenY || window.screenTop || 0,
                                outerWidth: window.outerWidth,
                                outerHeight: window.outerHeight,
                                innerWidth: window.innerWidth,
                                innerHeight: window.innerHeight
                            };
                        """)
                        screen_x = window_rect['screenX']
                        screen_y = window_rect['screenY']
                        toolbar_height = window_rect['outerHeight'] - window_rect['innerHeight']

                        # Checkbox screen coordinates
                        checkbox_screen_x = screen_x + x_coord + 30
                        checkbox_screen_y = screen_y + toolbar_height + y_coord + (size['height'] // 2 if size['height'] > 0 else 30)
                        print(f"Moving to screen coords ({checkbox_screen_x}, {checkbox_screen_y}) via pyautogui and clicking...")
                        pyautogui.moveTo(checkbox_screen_x, checkbox_screen_y, duration=0.5)
                        time.sleep(0.5)
                        pyautogui.click()
                        time.sleep(6)

                        body_text = driver.find_element(By.TAG_NAME, "body").text
                        if "Security Check" not in body_text and "Verify you are human" not in body_text:
                            print("Cloudflare challenge bypassed via pyautogui!")
                            return
                    except Exception as e:
                        print(f"Pyautogui click failed: {e}")

                # Standard iframe/checkbox fallback if coordinates method didn't work
                iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
                for iframe in iframes:
                    try:
                        driver.switch_to.frame(iframe)
                        cbs = driver.find_elements(By.CSS_SELECTOR, "input[type=checkbox]")
                        for cb in cbs:
                            if cb.is_displayed():
                                driver.execute_script("arguments[0].click();", cb)
                                time.sleep(6)
                                break
                    except Exception:
                        pass
                    finally:
                        driver.switch_to.default_content()

                time.sleep(3)

            except Exception as e:
                print(f"Error handling Cloudflare: {e}")
                time.sleep(2)

    # ------------------------------------------------------------------
    # Cookie consent helper
    # ------------------------------------------------------------------
    def _handle_cookie_consent(self, driver):
        """Click 'Confirm My Choices' if it appears."""
        try:
            btns = driver.find_elements(By.XPATH, "//button[contains(text(),'Confirm My Choices')]")
            for b in btns:
                if b.is_displayed():
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(1)
                    return
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Container number formatting
    # ------------------------------------------------------------------
    @staticmethod
    def _format_container(container_no: str) -> str:
        """
        Hapag URL needs '++' between the 4-letter prefix and the 7-digit
        suffix.  e.g.  FANU1456666  →  FANU++1456666
        """
        clean = container_no.strip().upper()
        if len(clean) >= 5 and clean[:4].isalpha():
            return clean[:4] + "++" + clean[4:]
        return clean

    # ------------------------------------------------------------------
    # Location extraction from "last move" text
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_location(text: str) -> str:
        r"""
        The last-move span contains something like:
           'Vessel departure  in  SAVANNAH  on  2026-04-22'
        or 'Loaded  from  NEW YORK  at  Terminal XYZ  on  2026-05-01'
        
        The Power Automate flow uses regex:
           (?:\bin\s+|\bfrom\s+)(.*?)(?:\s+at\b|\s+on\b)
        to grab the location between 'in'/'from' and 'at'/'on'.
        """
        if not text:
            return ""
        m = re.search(r'(?:\bin\s+|\bfrom\s+)(.*?)(?:\s+at\b|\s+on\b)', text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # Fallback: split by common separators and return middle part
        parts = re.split(r'[•—\-]', text)
        if len(parts) >= 2:
            return parts[1].strip()
        return text.strip()

    # ------------------------------------------------------------------
    # Main tracking method
    # ------------------------------------------------------------------
    def track(self, container_no: str, bl_no: str = None) -> dict:
        formatted = self._format_container(container_no)
        url = (
            f"https://www.hapag-lloyd.com/en/online-business/track/"
            f"track-by-container-solution.html?container={formatted}"
        )

        result = {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "",
            "TrackingStatus": "Not Tracked",
            "DeliveryStatus": "Not Updated",
            "Remarks": "",
            "TrackingURL": url,
            "TrackedAt": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "Size": "",
        }

        if not self.driver:
            self._init_driver()

        driver = self.driver

        try:
            driver.get(url)
            time.sleep(4)

            # --- Cloudflare challenge ---
            self._handle_cloudflare(driver)

            # --- Cookie consent (first load only) ---
            if self._first_load:
                self._handle_cookie_consent(driver)
                self._first_load = False

            # Wait for the page content to fully load
            time.sleep(4)

            body_text = driver.find_element(By.TAG_NAME, "body").text

            # If Cloudflare is STILL blocking, bail
            if "Security Check" in body_text or "Verify you are human" in body_text:
                result["Remarks"] = "Cloudflare challenge could not be bypassed."
                result["TrackingStatus"] = "Manual Required"
                return result

            # ----------------------------------------------------------------
            # 1. LAST MOVE (location only)
            # ----------------------------------------------------------------
            last_move_loc = ""
            try:
                lm_sel = (
                    "#tracing_by_container_f\\:hl56 > tbody > tr > td > div > table > "
                    "tbody > tr > td:nth-child(1) > table > tbody > tr > td.inputNonEdit > span"
                )
                lm_els = driver.find_elements(By.CSS_SELECTOR, lm_sel)
                if lm_els:
                    raw_text = lm_els[0].get_attribute("textContent").strip()
                    last_move_loc = self._extract_location(raw_text)
                else:
                    # Fallback: any span inside inputNonEdit
                    fb = driver.find_elements(By.CSS_SELECTOR, "td.inputNonEdit span")
                    if fb:
                        raw_text = fb[0].get_attribute("textContent").strip()
                        last_move_loc = self._extract_location(raw_text)
            except Exception:
                pass

            # ----------------------------------------------------------------
            # 2. ETA – date from the last "Vessel arrival" row
            # ----------------------------------------------------------------
            eta_str = ""
            try:
                # Strategy: find the tracking events table and locate all rows
                # whose Status column contains "Vessel arrival" (or "Vessel arrived").
                # Take the DATE from the last such row.
                eta_sel = (
                    "#tracing_by_container_f\\:hl66 > tbody > tr"
                )
                rows = driver.find_elements(By.CSS_SELECTOR, eta_sel)

                # Walk rows, remember the date of the last vessel-arrival row
                last_arrival_date = ""
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        status_text = cells[0].get_attribute("textContent").strip()
                        if "vessel arrival" in status_text.lower() or "vessel arrived" in status_text.lower():
                            date_text = cells[2].get_attribute("textContent").strip()
                            if date_text:
                                last_arrival_date = date_text

                if last_arrival_date:
                    eta_str = last_arrival_date
                else:
                    # Fallback: use the user-provided exact selector
                    eta_exact_sel = (
                        "#tracing_by_container_f\\:hl66 > tbody > "
                        "tr:nth-child(5) > td:nth-child(3) > span"
                    )
                    eta_els = driver.find_elements(By.CSS_SELECTOR, eta_exact_sel)
                    if eta_els:
                        eta_str = eta_els[0].get_attribute("textContent").strip()
            except Exception:
                pass

            # ----------------------------------------------------------------
            # 3. ETD – extract ETD date from row where status is "Vessel departed" or "Vessel departure"
            # just after "Loaded" text in table, falling back to exact selector:
            # #tracing_by_container_f\:hl66 > tbody > tr:nth-child(4) > td:nth-child(3) > span
            # ----------------------------------------------------------------
            etd_str = ""
            try:
                rows = driver.find_elements(
                    By.CSS_SELECTOR,
                    "#tracing_by_container_f\\:hl66 > tbody > tr"
                )
                loaded_seen = False
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:
                        status_text = cells[0].get_attribute("textContent").strip().lower()
                        if "loaded" in status_text:
                            loaded_seen = True
                        elif loaded_seen and ("vessel departed" in status_text or "vessel departure" in status_text):
                            date_text = cells[2].get_attribute("textContent").strip()
                            if date_text:
                                etd_str = date_text
                                break

                # Fallback: try the exact selector if no match found
                if not etd_str:
                    etd_exact_sel = (
                        "#tracing_by_container_f\\:hl66 > tbody > "
                        "tr:nth-child(4) > td:nth-child(3) > span"
                    )
                    etd_els = driver.find_elements(By.CSS_SELECTOR, etd_exact_sel)
                    if etd_els:
                        etd_str = etd_els[0].get_attribute("textContent").strip()
            except Exception:
                pass

            # ----------------------------------------------------------------
            # Format dates to DD-MM-YYYY
            # ----------------------------------------------------------------
            from utils.text_utils import extract_date_from_text

            if eta_str:
                parsed = extract_date_from_text(eta_str)
                if parsed:
                    result["ETA"] = parsed.strftime("%d-%m-%Y")
                else:
                    result["ETA"] = eta_str
            if etd_str:
                parsed = extract_date_from_text(etd_str)
                if parsed:
                    result["ETD"] = parsed.strftime("%d-%m-%Y")
                else:
                    result["ETD"] = etd_str

            result["CurrentStatus"] = last_move_loc

            # Determine tracking status
            if last_move_loc or eta_str:
                result["TrackingStatus"] = "Tracked"
                result["Remarks"] = "Tracking successful."
            else:
                result["TrackingStatus"] = "Not Updated"
                result["Remarks"] = "Page loaded but no data could be extracted."

        except Exception as e:
            result["Remarks"] = f"Error during tracking: {str(e)}"

        return result
