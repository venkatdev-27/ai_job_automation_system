import os
import json
import time
import logging
from pathlib import Path
from typing import Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Try to use undetected-chromedriver for better bypass
try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False


PROFILE_BASE_DIR = Path(os.getenv(
    "CHROME_PROFILE_DIR",
    "D:/ai-bot-resumes/job_automation_system/chrome_profile"
))


class NaukriSelenium:
    """Selenium-based Naukri scraper - fallback for CDP failures."""

    def __init__(self, logger, settings: Any = None, student_id: str = None):
        self.logger = logger
        self.settings = settings
        self.student_id = student_id
        self.driver = None
        self.options = None
        self.profile_path = None
        if student_id:
            self.profile_path = PROFILE_BASE_DIR / student_id / "naukri"
            self.cookies_file = self.profile_path / "cookies.json"

    def _init_driver(self, headless: bool = True):
        """Initialize Chrome with Selenium using undetected-chromedriver when available."""
        # Use undetected-chromedriver if available
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
            # Fallback to regular Selenium
            self.options = Options()
            if headless:
                self.options.add_argument('--headless=new')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
            self.options.add_argument('--disable-blink-features=AutomationControlled')
            self.options.add_argument('--disable-gpu')
            self.options.add_argument('--window-size=1280,720')
            self.options.add_argument('--disable-extensions')
            self.options.add_argument('--disable-sync')
            self.options.add_argument('--lang=en-US')
            self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.options.add_experimental_option('useAutomationExtension', False)
            
            if self.profile_path:
                self.profile_path.mkdir(parents=True, exist_ok=True)
                self.options.add_argument(f'--user-data-dir={self.profile_path}')
            
            self.driver = webdriver.Chrome(options=self.options)
            
            # Remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.driver.set_page_load_timeout(45)
        self.driver.implicitly_wait(10)

    def _load_existing_cookies(self) -> bool:
        """Load cookies from SessionManager cookies file before login attempt."""
        if not self.cookies_file or not self.cookies_file.exists():
            return False
        try:
            cookies = json.loads(self.cookies_file.read_text(encoding='utf-8'))
            if not cookies:
                return False
            # Selenium uses .add_cookie() which needs domain, path, name, value
            for cookie in cookies:
                if 'domain' in cookie and 'name' in cookie:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception:
                        pass
            self.logger.log_info(f"Selenium: Loaded {len(cookies)} cookies from shared profile")
            return True
        except Exception as e:
            self.logger.log_warn(f"Selenium: Failed to load existing cookies: {e}")
            return False

    def _save_cookies(self) -> bool:
        """Save cookies after successful login to shared profile."""
        if not self.cookies_file:
            return False
        try:
            cookies = self.driver.get_cookies()
            if cookies:
                self.profile_path.mkdir(parents=True, exist_ok=True)
                self.cookies_file.write_text(json.dumps(cookies, indent=2), encoding='utf-8')
                self.logger.log_info(f"Selenium: Saved {len(cookies)} cookies to shared profile")
            return True
        except Exception as e:
            self.logger.log_warn(f"Selenium: Failed to save cookies: {e}")
            return False
        
    async def get_driver(self, headless: bool = True):
        """Get or create driver."""
        if self.driver is None:
            self._init_driver(headless)
        return self.driver
    
    async def login(self, username: str, password: str) -> bool:
        """Login to Naukri with session persistence."""
        try:
            # Try to restore existing session from shared profile
            if self.profile_path and self.profile_path.exists():
                self.driver.get("https://www.naukri.com/mnjuser/homepage")
                time.sleep(3)
                if "nlogin" not in self.driver.current_url.lower():
                    self.logger.log_ok("Selenium: Session restored from shared profile!")
                    return True

            self.logger.log_info("Selenium: Opening Naukri login...")

            # Load existing cookies before attempting login
            self._load_existing_cookies()

            self.driver.get("https://www.naukri.com/nlogin/login")

            # Wait for username field
            wait = WebDriverWait(self.driver, 15)
            username_field = wait.until(EC.presence_of_element_located((By.ID, "usernameField")))

            self.logger.log_info("Selenium: Filling credentials...")
            username_field.send_keys(username)

            password_field = self.driver.find_element(By.ID, "passwordField")
            password_field.send_keys(password)

            self.driver.find_element(By.XPATH, "//button[contains(@class, 'loginButton')]").click()

            self.logger.log_info("Selenium: Waiting for login...")
            time.sleep(10)

            current_url = self.driver.current_url
            if "naukri.com" in current_url and "login" not in current_url:
                self.logger.log_ok("Selenium: Login successful!")
                self._save_cookies()
                return True

            self.logger.log_warn(f"Selenium: Login may have failed, URL: {current_url}")
            return True
            
        except Exception as e:
            self.logger.log_err(f"Selenium login failed: {e}")
            return False
    
    async def search_jobs(self, role: str, location: str = "") -> int:
        """Search for jobs and return count."""
        try:
            # Build search URL
            search_url = f"https://www.naukri.com/{role.replace(' ', '-').lower()}-jobs"
            if location:
                search_url += f"-in-{location.replace(' ', '-').lower()}"
                
            self.logger.log_info(f"Selenium: Searching for {role}...")
            self.driver.get(search_url)
            
            time.sleep(8)  # Wait for page load
            
            # Get page source
            content = self.driver.page_source
            content_len = len(content)
            
            self.logger.log_info(f"Selenium: Page loaded. Content length: {content_len}")
            
            # Check for 1945 error
            if content_len == 1945 or "Application error" in content:
                self.logger.log_warn("Selenium: 1945 detected! Retrying...")
                self.driver.get(search_url)
                time.sleep(12)
                content = self.driver.page_source
                content_len = len(content)
                self.logger.log_info(f"Selenium: Retry content: {content_len}")
            
            # Try to find job cards
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, ".srp-jobtuple-wrapper")
                count = len(job_cards)
                if count > 0:
                    self.logger.log_ok(f"Selenium: Found {count} jobs!")
                    return count
            except:
                pass
            
            # Try alternative selectors
            try:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-job-id]")
                count = len(job_cards)
                if count > 0:
                    self.logger.log_ok(f"Selenium: Found {count} jobs via data-id!")
                    return count
            except:
                pass
            
            # Count job links
            try:
                job_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/']")
                count = len(job_links)
                if count > 0:
                    self.logger.log_ok(f"Selenium: Found {count} jobs via links!")
                    return count
            except:
                pass
                
            self.logger.log_warn("Selenium: No jobs found")
            return 0
            
        except Exception as e:
            self.logger.log_err(f"Selenium search failed: {e}")
            return 0
    
    async def apply_to_job(self, job_url: str) -> bool:
        """Apply to a specific job."""
        try:
            self.logger.log_info(f"Selenium: Applying to {job_url}")
            self.driver.get(job_url)
            time.sleep(5)
            
            # Try to find apply button
            try:
                apply_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Apply')]")
                apply_btn.click()
                self.logger.log_ok("Selenium: Applied!")
                return True
            except NoSuchElementException:
                self.logger.log_warn("Selenium: No apply button found")
                return False
                
        except Exception as e:
            self.logger.log_err(f"Selenium apply failed: {e}")
            return False
    
    async def close(self):
        """Close driver."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None


def create_selenium_scraper(logger, settings, student_id=None):
    """Factory function to create Selenium scraper."""
    return NaukriSelenium(logger, settings, student_id=student_id)
