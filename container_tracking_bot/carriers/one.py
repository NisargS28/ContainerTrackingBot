from carriers.base import BaseTracker
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from config import HEADLESS, WAIT_TIME
import re

class ONETracker(BaseTracker):
    """
    ONE (Ocean Network Express) Tracking Implementation
    Extracts Last Move, ETA, ETD, Status, and Delivery Status.
    """
    def __init__(self):
        self.driver = None

    def _init_driver(self):
        chrome_options = Options()
        if HEADLESS:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
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

    def track(self, container_no: str, bl_no: str = None) -> dict:
        result = {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "Not Tracked",
            "TrackingStatus": "Not Tracked",
            "DeliveryStatus": "Not Updated",
            "Remarks": "",
            "TrackingURL": f"https://ecomm.one-line.com/one-ecom/manage-shipment/cargo-tracking?trakNoParam={container_no}&trakNoTpCdParam=C",
            "TrackedAt": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "Size": ""
        }

        if not self.driver:
            self._init_driver()
            
        driver = self.driver
        
        try:
            driver.get(result["TrackingURL"])
            # Give it time to load dynamic React/Vue content and popups
            time.sleep(6)
            
            # Click promotion skip buttons if they appear
            try:
                # Find buttons matching the 'skip-btn' pattern in the class name
                skip_btns = driver.find_elements(By.CSS_SELECTOR, "button[class*='PromotionPopoverContent_skip-btn']")
                for btn in skip_btns:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
            except Exception as e:
                pass
                
            time.sleep(2)
            
            # Check for generic failure or missing data
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "No results found" in body_text or "No data found" in body_text:
                result["Remarks"] = "Container not found."
                return result

            # 1. Last Move Location
            last_move_loc = ""
            try:
                # User provided selector
                lm_el = driver.find_elements(By.CSS_SELECTOR, "#table-wrap-fake > div.Table_body__JrCVh.sticky-row-wrapper-alias > div.flex > div > div:nth-child(3) > div > div > div.TableColumn_location-name__mJCZC")
                if lm_el:
                    last_move_loc = lm_el[0].get_attribute("textContent").strip()
                else:
                    # Generic fallback since hashes change
                    lm_fallback = driver.find_elements(By.CSS_SELECTOR, "div[class*='TableColumn_location-name']")
                    if lm_fallback:
                        last_move_loc = lm_fallback[0].get_attribute("textContent").strip()
            except Exception as e:
                pass

            # 2. ETA
            eta_str = ""
            try:
                # User provided selector
                eta_el = driver.find_elements(By.CSS_SELECTOR, "#table-wrap-fake > div.Table_body__JrCVh.sticky-row-wrapper-alias > div.flex > div > div:nth-child(5) > div > div.ds-text-body.text-ds-grey-darker-1.flex.items-center.gap-1 > div > span")
                if eta_el:
                    eta_str = eta_el[0].get_attribute("textContent").strip()
                else:
                    # Generic fallback
                    eta_fallback = driver.find_elements(By.XPATH, "//*[contains(@id, 'table-wrap')]//div[contains(@class, 'Table_body')]//div[contains(@class, 'flex items-center')]//span")
                    for ef in eta_fallback:
                        txt = ef.get_attribute("textContent").strip()
                        if txt and len(txt) >= 8 and "-" in txt:
                            eta_str = txt
                            break
            except Exception as e:
                pass

            # 3. ETD
            etd_str = ""
            try:
                # User provided selector
                etd_el = driver.find_elements(By.CSS_SELECTOR, "#sailing-table-wrap > div.SailingTable_body__4RssK > div.SailingTable_departure-date-td__ABo6E > div > div > span")
                if etd_el:
                    etd_str = etd_el[0].get_attribute("textContent").strip()
                else:
                    # Generic fallback
                    etd_fallback = driver.find_elements(By.CSS_SELECTOR, "div[class*='SailingTable_departure-date'] span")
                    if etd_fallback:
                        etd_str = etd_fallback[0].get_attribute("textContent").strip()
                        
                if etd_str:
                    from utils.text_utils import extract_date_from_text
                    parsed_etd = extract_date_from_text(etd_str)
                    if parsed_etd:
                        etd_str = parsed_etd.strftime("%d-%m-%Y")
            except Exception as e:
                pass

            result["CurrentStatus"] = last_move_loc
            result["ETD"] = etd_str
            
            # ETA Parsing
            try:
                if eta_str:
                    # Match dates like YYYY-MM-DD or DD-MM-YYYY or DD MMM YYYY
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}\s+[A-Za-z]{3}\s+\d{4}', eta_str)
                    if date_match:
                        from utils.text_utils import extract_date_from_text
                        parsed_date = extract_date_from_text(date_match.group())
                        if parsed_date:
                            result["ETA"] = parsed_date.strftime("%d-%m-%Y")
                            if parsed_date >= datetime.now():
                                result["DeliveryStatus"] = "NotDelivered"
                            else:
                                result["DeliveryStatus"] = "Delivered"
                        else:
                            result["ETA"] = eta_str
                            result["DeliveryStatus"] = "Not Updated"
                    else:
                        result["ETA"] = eta_str
                        result["DeliveryStatus"] = "Not Updated"
                        
                    result["TrackingStatus"] = "Tracked"
                else:
                    result["ETA"] = "---"
                    result["TrackingStatus"] = "Not Updated"
                    result["DeliveryStatus"] = "Not Updated"
            except Exception as e:
                result["ETA"] = "---"
                result["TrackingStatus"] = "Not Updated"
                result["DeliveryStatus"] = "Not Updated"

            result["Remarks"] = "Tracking successful."
                
        except Exception as e:
            result["Remarks"] = f"Error during tracking: {str(e)}"
            
        return result
