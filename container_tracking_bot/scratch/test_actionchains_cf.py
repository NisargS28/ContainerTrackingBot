import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA = r"d:\Nisarg.Doc\Skaps\automate\container_tracking\container_tracking_bot\scratch\chrome_debug_profile"
DEBUG_PORT = 9222

def launch_chrome():
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={USER_DATA}",
        "--start-maximized",
        "--no-first-run",
        "--disable-default-apps",
        "--disable-extensions",
    ]
    proc = subprocess.Popen(cmd)
    time.sleep(5)
    return proc

def run_test():
    proc = launch_chrome()
    
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        url = "https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html?container=FANU++1456666"
        print(f"Navigating to {url}...")
        driver.get(url)
        
        print("Waiting 10 seconds for page to load/CF check to appear...")
        time.sleep(10)
        
        # Look for Cloudflare Turnstile iframe
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
        if not iframes:
            print("No Turnstile iframe found by src. Trying generic iframe...")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            
        print(f"Found {len(iframes)} iframes on page.")
        
        # We can also try locating by class or ID
        # The user mentioned selector: #BbLB6 > div > label > input[type=checkbox]
        # Let's see if we can find the element with ID "BbLB6" or container element.
        target_element = None
        for selector in ["#BbLB6", ".cf-turnstile", "iframe[src*='challenges.cloudflare.com']"]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    target_element = elements[0]
                    print(f"Found target element using selector: {selector}")
                    break
            except Exception as e:
                print(f"Error searching selector {selector}: {e}")
                
        if target_element:
            # Get location coordinates as requested
            location = target_element.location
            size = target_element.size
            x_coord = location['x']
            y_coord = location['y']
            print(f"Element coordinates: X={x_coord}, Y={y_coord}, Width={size['width']}, Height={size['height']}")
            
            # Let's try ActionChains move_by_offset and click
            # Checkbox is inside the iframe, usually around x + 30, y + 30 (or center of iframe)
            # We will try the user's exact snippet first, and then with a small offset if needed.
            print("Performing ActionChains click...")
            actions = ActionChains(driver)
            
            # The user's code:
            # actions.move_by_offset(x_coord, y_coord).click().perform()
            # Let's try to click near the middle of the element height and slightly to the right (x + 30, y + height/2)
            click_x = x_coord + 30
            click_y = y_coord + (size['height'] // 2 if size['height'] > 0 else 30)
            print(f"Moving to ({click_x}, {click_y}) and clicking...")
            actions.move_by_offset(click_x, click_y).click().perform()
            
            print("ActionChains performed. Waiting 10 seconds to see if CF is bypassed...")
            time.sleep(10)
            
            body_text = driver.find_element(By.TAG_NAME, "body").text
            if "Security Check" not in body_text and "Verify you are human" not in body_text:
                print("SUCCESS! ActionChains bypassed Cloudflare.")
            else:
                print("ActionChains did not bypass Cloudflare. Page body still contains challenge text.")
        else:
            print("Could not find any suitable target element to click.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()
        proc.terminate()

if __name__ == "__main__":
    run_test()
