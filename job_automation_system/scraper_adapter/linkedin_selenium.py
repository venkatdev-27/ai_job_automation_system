import os
import json
import time
import logging
from pathlib import Path
from typing import Any, Optional

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


PROFILE_BASE_DIR = Path(os.getenv(
    "CHROME_PROFILE_DIR",
    "D:/ai-bot-resumes/job_automation_system/chrome_profile"
))


class LinkedInSelenium:
    """Selenium-based LinkedIn scraper - fallback for CDP failures."""

    def __init__(self, logger, settings: Any = None, student_id: str = None):
        self.logger = logger
        self.settings = settings
        self.student_id = student_id
        self.driver = None
        self.options = None
        self.profile_path = None
        if student_id:
            self.profile_path = PROFILE_BASE_DIR / student_id / "linkedin"
            self.cookies_file = self.profile_path / "cookies.json"

    def _init_driver(self, headless: bool = True):
        """Initialize Chrome with Selenium using undetected-chromedriver when available."""
        if HAS_UNDETECTED:
            self.options = uc.ChromeOptions()
            # undetected_chromedriver still reads options.headless on some versions,
            # while Selenium 4.30+ no longer exposes it on ChromeOptions.
            self.options.headless = bool(headless)
            if headless:
                self.options.add_argument('--headless=new')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--window-size=1400,900')
            self.options.add_argument('--lang=en-US')
            
            if self.profile_path:
                self.profile_path.mkdir(parents=True, exist_ok=True)
                self.options.add_argument(f'--user-data-dir={self.profile_path}')
            
            try:
                self.driver = uc.Chrome(options=self.options)
            except Exception as e:
                self.logger.log_err(f"undetected driver init failed: {e}")
                raise
        else:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            self.options = Options()
            if headless:
                self.options.add_argument('--headless=new')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-blink-features=AutomationControlled')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--window-size=1280,720')
            self.options.add_argument('--lang=en-US')
            self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            if self.profile_path:
                self.profile_path.mkdir(parents=True, exist_ok=True)
                self.options.add_argument(f'--user-data-dir={self.profile_path}')
            
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.driver.set_page_load_timeout(45)
        self.driver.implicitly_wait(10)

    def login(self, email: str, password: str, max_retries: int = 3) -> bool:
        """Login to LinkedIn."""
        self._init_driver(headless=False)
        
        try:
            for attempt in range(max_retries):
                self.logger.log_info(f"LinkedIn Selenium login attempt {attempt + 1}/{max_retries}")
                
                self.driver.get("https://www.linkedin.com/login")
                time.sleep(5)  # Wait longer for page load
                
                # Check if blocked
                page_source = self.driver.page_source
                if len(page_source) < 5000:
                    self.logger.log_warn(f"Page blocked (len={len(page_source)}), retry {attempt + 1}")
                    continue
                
                # Fill email - use stable name selector
                try:
                    wait = WebDriverWait(self.driver, 15)
                    email_field = wait.until(EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[name='session_key']")
                    ))
                    email_field.clear()
                    email_field.send_keys(email)
                    time.sleep(1.5)
                except Exception as e:
                    self.logger.log_warn(f"Email field not found: {e}")
                    continue
                
                # Fill password - use stable name selector
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='session_password']")
                    password_field.clear()
                    password_field.send_keys(password)
                    time.sleep(1)
                except Exception as e:
                    self.logger.log_warn(f"Password field not found: {e}")
                    continue
                
                # Click sign in button - use type submit
                try:
                    login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    login_btn.click()
                    time.sleep(6)
                except:
                    # Press Enter instead
                    password_field.send_keys("\n")
                    time.sleep(6)
                
                current_url = self.driver.current_url.lower()
                self.logger.log_info(f"URL after login: {current_url}")
                
                if "login" not in current_url and "feed" in current_url:
                    self.logger.log_ok("LinkedIn Selenium login successful!")
                    self._save_cookies()
                    return True
                
                if "login" in current_url:
                    self.logger.log_warn("Still on login page, retrying...")
        
        except Exception as e:
            self.logger.log_err(f"Login error: {e}")
        
        self.logger.log_err("LinkedIn login failed")
        return False

    def _save_cookies(self):
        """Save cookies."""
        if not self.driver or not self.profile_path:
            return
        
        try:
            self.profile_path.mkdir(parents=True, exist_ok=True)
            cookies = self.driver.get_cookies()
            
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            
            self.logger.log_info(f"Saved {len(cookies)} cookies")
        except Exception as e:
            self.logger.log_warn(f"Cookie save failed: {e}")

    def search_jobs(self, keywords: list, location: str = "India", max_jobs: int = 10) -> list:
        """Search for jobs."""
        jobs = []
        
        if not self.driver:
            self._init_driver()
        
        try:
            self.driver.get("https://www.linkedin.com/jobs")
            time.sleep(3)
            
            for keyword in keywords[:3]:
                self.logger.log_info(f"Searching: {keyword}")
                
                try:
                    search_box = self.driver.find_element(By.CSS_SELECTOR, "input[class*='jobs-search-box']")
                    search_box.clear()
                    search_box.send_keys(keyword)
                    time.sleep(1)
                    
                    location_box = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='Location']")
                    location_box.clear()
                    location_box.send_keys(location)
                    time.sleep(1)
                    
                    search_box.submit()
                    time.sleep(5)
                except:
                    pass
                
                # Collect jobs
                try:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
                    for card in job_cards[:max_jobs]:
                        try:
                            title = card.text[:50]
                            if title:
                                jobs.append({
                                    "title": title,
                                    "source": "linkedin",
                                    "url": ""
                                })
                        except:
                            pass
                except:
                    pass
                
        except Exception as e:
            self.logger.log_err(f"Search error: {e}")
        
        return jobs[:max_jobs]

    def close(self):
        """Close driver."""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
