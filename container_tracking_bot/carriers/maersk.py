from carriers.base import BaseTracker
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from config import HEADLESS, WAIT_TIME

class MaerskTracker(BaseTracker):
    """
    Maersk Tracking Implementation
    Extracts Size, Last Move, ETA, Status, and Delivery Status.
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
            "TrackingURL": f"https://www.maersk.com/tracking/{container_no}",
            "TrackedAt": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }

        if not self.driver:
            self._init_driver()
            
        driver = self.driver
        
        try:
            driver.get(result["TrackingURL"])
            # Give it time to load initial DOM
            time.sleep(4)
            
            # Click Allow all cookies if present
            try:
                cookie_btn = driver.find_elements(By.CSS_SELECTOR, "#coiPage-1 > div.coi-banner__content > div > div.coi-banner__page-actions > div > button:nth-child(2)")
                if cookie_btn and cookie_btn[0].is_displayed():
                    cookie_btn[0].click()
                    time.sleep(2)
            except Exception as e:
                pass
                
            # Give it more time to load dynamic tracking content
            time.sleep(4)
            
            # Check if container is found
            main_div = driver.find_elements(By.TAG_NAME, "main")
            if not main_div:
                result["Remarks"] = "Tracking page structure not found."
                return result
                
            full_text = main_div[0].text
            if "No results found" in full_text or "No results" in full_text:
                result["Remarks"] = "Container not found."
                return result

            # Extract data using mc-text-and-icon elements
            mc_elements = driver.find_elements(By.TAG_NAME, "mc-text-and-icon")
            
            if len(mc_elements) >= 4:
                # 1. Size
                size_text = mc_elements[0].text
                size = ""
                if "4" in size_text:
                    size = "40'"
                elif "2" in size_text:
                    size = "22'"
                
                # 2. Latest Event / Move Location
                last_move_loc = ""
                try:
                    move_el = driver.find_elements(By.CSS_SELECTOR, "#maersk-app > div > main > div:nth-child(2) > div > div.container__wrapper > mc-text-and-icon:nth-child(2) > span")
                    if move_el:
                        import re
                        txt = move_el[0].text
                        parts = re.split(r'\s+[•—\-\ufffd]\s+', txt)
                        if len(parts) >= 2:
                            last_move_loc = parts[1].strip()
                        else:
                            last_move_loc = txt
                    else:
                        # Fallback finding logic
                        for i, el in enumerate(mc_elements):
                            if "Last updated" in el.text:
                                for j in range(i+1, min(i+3, len(mc_elements))):
                                    txt = mc_elements[j].text.strip()
                                    if txt and "Shipment details" not in txt:
                                        import re
                                        parts = re.split(r'\s+[•—\-\ufffd]\s+', txt)
                                        if len(parts) >= 2:
                                            last_move_loc = parts[1].strip()
                                        else:
                                            last_move_loc = txt
                                        break
                                break
                except Exception:
                    pass
                
                # 3. ETA
                eta_str = ""
                # Execute JavaScript to pierce shadow DOM for data-test="container-eta"
                js_script = """
                let result = "";
                // First try container-eta element directly
                let etaEl = document.querySelector('[data-test="container-eta"]');
                if (etaEl && etaEl.shadowRoot) {
                    let sublabel = etaEl.shadowRoot.querySelector('.sublabel');
                    if (sublabel) {
                        result = sublabel.textContent;
                    }
                }
                // Fallback to searching all mc-text-and-icon
                if (!result) {
                    document.querySelectorAll('mc-text-and-icon').forEach(el => {
                        if(el.shadowRoot) {
                            let labelSlot = el.shadowRoot.querySelector('.label');
                            if (labelSlot) {
                                let labelText = labelSlot.textContent || "";
                                let lowerLabel = labelText.toLowerCase();
                                if (lowerLabel.includes("estimated arrival date") || lowerLabel.includes("arrived at")) {
                                    let sublabelSlot = el.shadowRoot.querySelector('.sublabel');
                                    if (sublabelSlot) {
                                        result = sublabelSlot.textContent || "";
                                    }
                                }
                            }
                        }
                    });
                }
                return result ? result.trim() : "";
                """
                try:
                    eta_val = driver.execute_script(js_script)
                    if eta_val:
                        eta_str = eta_val.strip()
                except Exception as e:
                    print(f"Shadow DOM ETA extraction failed: {e}")
                    
                # Fallback text parsing if JS fails
                if not eta_str:
                    for el in mc_elements:
                        txt = el.text
                        if "Estimated arrival date" in txt or "Arrived at" in txt:
                            lines = txt.split('\\n')
                            if len(lines) > 1:
                                eta_str = lines[-1].strip()
                            break
                
                # 4. ETD
                etd_str = ""
                try:
                    t_plan = driver.find_elements(By.CSS_SELECTOR, "[id^='transport-plan__container']")
                    if t_plan:
                        lis = t_plan[0].find_elements(By.TAG_NAME, "li")
                        found_load_on = False
                        for li in lis:
                            txt = li.text.strip()
                            if not txt: continue
                            if "Load on" in txt:
                                found_load_on = True
                            elif "Vessel departure" in txt and found_load_on:
                                lines = txt.split('\\n')
                                if len(lines) > 1:
                                    etd_str = lines[1].strip()
                                else:
                                    try:
                                        etd_span = li.find_element(By.CSS_SELECTOR, "div > span:nth-child(3)")
                                        etd_str = etd_span.text.strip()
                                    except: pass
                                break
                except Exception:
                    pass
                
                result["Size"] = size
                result["CurrentStatus"] = last_move_loc
                result["ETD"] = etd_str
                
                # ETA Parsing
                try:
                    if eta_str:
                        import re
                        date_match = re.search(r'\d{2}\s+[A-Za-z]{3}\s+\d{4}', eta_str)
                        if date_match:
                            parsed_date = datetime.strptime(date_match.group(), "%d %b %Y")
                            result["ETA"] = parsed_date.strftime("%d-%m-%Y")
                            
                            # Delivery Status logic
                            if parsed_date >= datetime.now():
                                result["DeliveryStatus"] = "NotDelivered"
                            else:
                                result["DeliveryStatus"] = "Delivered"
                            result["TrackingStatus"] = "Tracked"
                        else:
                            result["ETA"] = eta_str  # Just put the raw string if we can't parse it
                            result["TrackingStatus"] = "Tracked"
                            result["DeliveryStatus"] = "Not Updated"
                    else:
                        result["ETA"] = "---"
                        result["TrackingStatus"] = "Not Updated"
                        result["DeliveryStatus"] = "Not Updated"
                except Exception as e:
                    result["ETA"] = "---"
                    result["TrackingStatus"] = "Not Updated"
                    result["DeliveryStatus"] = "Not Updated"
                    print(f"Maersk ETA parsing error: {e}")

                result["Remarks"] = "Tracking successful."
            else:
                result["Remarks"] = "Unexpected page structure."
                
        except Exception as e:
            result["Remarks"] = f"Error during tracking: {str(e)}"
            
        return result
