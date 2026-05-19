import os
import json
import time
import logging
import random
import re
import subprocess
from pathlib import Path
from typing import Any, Optional, Tuple

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Ensure project root is in sys.path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Local imports
from utils.resume_selector import ResumeSelector, extract_skills_from_jd
from utils.skill_scorer import calculate_match_percentage
from utils.ai_extractor import get_ai_extractor
from utils.resume_downloader import download_resume_from_url
from utils.path_contract import resolve_ai_engine_pdf_path
import requests

PROFILE_BASE_DIR = Path(os.getenv(
    "CHROME_PROFILE_DIR",
    "/app/chrome_profile" if os.path.exists("/app") else "D:/ai-bot-resumes/job_automation_system/chrome_profile"
))


class FoundItSelenium:
    """
    FoundIt scraper using undetected-chromedriver to bypass bot detection.
    Selenium-First implementation for high reliability in production.
    """

    def __init__(self, logger, settings: Any = None, student_id: str = None):
        self.logger = logger
        self.settings = settings
        self.student_id = student_id
        self.driver = None
        self.options = None
        self.profile_path = None
        self._last_applied_job_title = None
        self._last_applied_company = None
        
        # Load global threshold
        try:
            from config.settings import settings as global_settings
            self.MATCH_PERCENTAGE_MIN = getattr(global_settings, "ats_threshold", 35.0)
        except:
            self.MATCH_PERCENTAGE_MIN = 35.0

        if student_id:
            # Use separate profiles per student for session isolation
            self.profile_path = PROFILE_BASE_DIR / "selenium_profile" / student_id
            self.cookies_file = self.profile_path / "cookies.json"

    def _init_driver(self, headless: bool = True):
        """Initialize undetected Chrome."""
        if self.driver:
            return self

        if os.getenv("IN_DOCKER", "").lower() == "true":
            headless = True

        self.options = uc.ChromeOptions()
        # undetected_chromedriver still reads options.headless on some versions,
        # while Selenium 4.30+ no longer exposes it on ChromeOptions.
        self.options.headless = bool(headless)
        
        # Headless mode is harder to detect with undetected-chromedriver if set correctly
        if headless:
            self.options.add_argument('--headless=new')
        
        # Core stability options
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--lang=en-US')
        
        # Stealth / Anti-detection
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument('--disable-infobars')
        
        # Randomize user agent
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        self.options.add_argument(f'--user-agent={user_agent}')
        
        # Profile persistence
        if self.profile_path:
            self.profile_path.mkdir(parents=True, exist_ok=True)
            self.options.add_argument(f'--user-data-dir={self.profile_path}')
        
        try:
            # Find chrome binary — check env var first (Docker), then common paths
            import glob
            import os as _os
            chrome_path = _os.environ.get("CHROME_PATH") or _os.environ.get("CHROMIUM_PATH")
            
            if not chrome_path:
                chrome_paths = [
                    "/ms-playwright/chromium-*/chrome-linux/chrome",
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium",
                    "/usr/bin/chromium-browser",
                    "C:/Program Files/Google/Chrome/Application/chrome.exe",
                    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
                ]
                for p in chrome_paths:
                    found = glob.glob(p)
                    if found:
                        chrome_path = found[0]
                        break
            
            if not chrome_path:
                chrome_path = "/usr/bin/google-chrome"  # Fallback
                
            self.logger.log_info(f"Using Chrome binary: {chrome_path}")
            chrome_major = self._detect_chrome_major(chrome_path)
            if chrome_major:
                self.logger.log_info(f"Using Chrome major version: {chrome_major}")
            
            # Initialize driver — use_subprocess=True prevents blocking on binary patching
            self.driver = uc.Chrome(
                options=self.options, 
                browser_executable_path=chrome_path,
                version_main=chrome_major,
                use_subprocess=True,
            )
            
            self.driver.set_page_load_timeout(45)
            self.driver.implicitly_wait(5)

            
        except Exception as e:
            self.logger.log_err(f"Selenium initialization failed: {e}")
            raise
        
        return self

    def _detect_chrome_major(self, chrome_path: str) -> Optional[int]:
        """Detect Chrome/Chromium major version for undetected-chromedriver."""
        try:
            proc = subprocess.run(
                [chrome_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version_text = f"{proc.stdout} {proc.stderr}"
            match = re.search(r"(\d+)\.", version_text)
            if match:
                return int(match.group(1))
        except Exception as e:
            self.logger.log_warn(f"Could not detect Chrome version: {e}")
        return None

    def login(self, email: str, password: str, max_retries: int = 3) -> bool:
        """Login to FoundIt with verified production selectors."""
        # Force headful mode for better bypass
        self._init_driver(headless=False)
        
        try:
            for attempt in range(max_retries):
                self.logger.log_info(f"FoundIt login attempt {attempt + 1}/{max_retries}")
                
                self.driver.get("https://www.foundit.in/rio/login")
                time.sleep(5)
                
                self.logger.log_info(f"Current URL: {self.driver.current_url}")

                # Check if already logged in (redirected to dashboard/profile)
                if "login" not in self.driver.current_url.lower() and "otp" not in self.driver.current_url.lower():
                    self.logger.log_ok("Already logged in (session restored)")
                    return True

                # 1. Fill Username
                try:
                    user_field = WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.ID, "userName"))
                    )
                    user_field.clear()
                    user_field.send_keys(email)
                    time.sleep(1)
                except Exception as e:
                    self.logger.log_warn(f"Username field not found: {e}")
                    # Log page source snippet for debugging if blocked
                    if len(self.driver.page_source) < 1000:
                        self.logger.log_err("Page content extremely short - likely blocked")
                    continue

                # 2. Click 'Login via Password' toggle using JS to avoid interception
                try:
                    toggle = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Login via Password')]"))
                    )
                    self.driver.execute_script("arguments[0].click();", toggle)
                    self.logger.log_info("Clicked 'Login via Password' toggle")
                    time.sleep(2)
                except Exception as e:
                    self.logger.log_warn(f"Could not click password toggle: {e}")

                # 3. Fill Password with human-like typing
                try:
                    pwd_field = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "password"))
                    )
                    pwd_field.clear()
                    for char in password:
                        pwd_field.send_keys(char)
                        time.sleep(random.uniform(0.05, 0.15))
                    self.logger.log_info("Filled password")
                    time.sleep(1)
                    
                    # 4. Submit via ENTER key (often more reliable than clicking)
                    from selenium.webdriver.common.keys import Keys
                    pwd_field.send_keys(Keys.ENTER)
                    self.logger.log_info("Sent ENTER key to password field")
                    time.sleep(8) # Longer wait for redirect
                except Exception as e:
                    self.logger.log_warn(f"Password field or submit failed: {e}")
                    continue

                # 5. Verify result
                current_url = self.driver.current_url.lower()
                self.logger.log_info(f"URL after login attempt: {current_url}")
                
                if "login" not in current_url and "otp" not in current_url:
                    self.logger.log_ok("FoundIt login successful!")
                    return True
                
                if "otp" in current_url:
                    self.logger.log_warn("OTP/Captcha detected - manual bypass or session required")
                    return False
                
                # Check for error messages on page
                try:
                    error_msg = self.driver.find_element(By.CLASS_NAME, "error-msg").text
                    self.logger.log_warn(f"Login page error: {error_msg}")
                except:
                    pass
                    
        except Exception as e:
            self.logger.log_err(f"Login fatal error: {e}")
        
        return False

    def search_and_apply(self, profile: Any, settings: Any) -> dict:
        """Main entry point for Selenium-First automation."""
        applied_count = 0
        skipped_count = 0
        self.profile = profile
        
        try:
            # 1. Initialize and Login
            email = getattr(profile, 'email', '')
            # Try to resolve actual credentials if available
            try:
                from database.credentials import get_student_credentials
                creds = get_student_credentials(getattr(profile, 'student_id', ''))
                if creds and 'foundit' in creds:
                    email = creds['foundit'].get('email') or email
                    password = creds['foundit'].get('password')
            except:
                password = None

            if not password:
                self.logger.log_err("Missing FoundIt password for student")
                return {"status": "error", "error": "missing_credentials"}

            if not self.login(email, password):
                return {"status": "error", "error": "login_failed"}

            # 2. Build search query
            # We'll use the most specific roles from profile titles
            roles = getattr(profile, 'candidate_titles', []) or ["Software Engineer"]
            primary_role = roles[0] if roles else "Software Engineer"
            
            self.logger.log_info(f"Starting job search for: {primary_role}")
            
            # Construct Search URL (Verified format)
            query_slug = primary_role.lower().replace(" ", "-") + "-fresher"
            encoded_query = primary_role.replace(" ", "%20")
            search_url = f"https://www.foundit.in/search/{query_slug}-jobs-in-india?query={encoded_query}&experience=0"
            
            self.driver.get(search_url)
            time.sleep(5)
            
            # 3. Collect all job URLs from search page UPFRONT (avoids fragile ancestor XPath)
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "applyBtn"))
                )
            except:
                self.logger.log_warn("No jobs found for this query")
                return {"status": "success", "applied": 0, "skipped": 0}

            # Collect job detail URLs from card title links
            job_urls = []
            try:
                # FoundIt card links pattern: /job/<slug>-<id>
                all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/']")
                seen = set()
                for lnk in all_links:
                    href = lnk.get_attribute("href") or ""
                    if href and href not in seen:
                        seen.add(href)
                        job_urls.append(href)
            except Exception as e:
                self.logger.log_warn(f"Could not collect job URLs: {e}")

            job_buttons = self.driver.find_elements(By.ID, "applyBtn")
            self.logger.log_info(f"Found {len(job_buttons)} job cards, {len(job_urls)} unique JD URLs")

            max_to_process = min(
                max(len(job_urls), len(job_buttons)),
                getattr(settings, "max_applies_per_run", 5)
            )
            search_results_url = self.driver.current_url
            applied_jobs = []  # track (title, company) for each applied job

            for i in range(max_to_process):
                try:
                    jd_url = job_urls[i] if i < len(job_urls) else None
                    result = self._process_single_job(i, profile,
                                                      jd_url=jd_url,
                                                      search_results_url=search_results_url)
                    if result == "applied":
                        applied_count += 1
                        applied_jobs.append((self._last_applied_job_title, self._last_applied_company))
                    elif result == "skipped":
                        skipped_count += 1

                    if applied_count >= getattr(settings, "max_applies_per_run", 5):
                        break

                except Exception as e:
                    self.logger.log_err(f"Error processing job card {i}: {e}")
                    continue

            final_title = applied_jobs[-1][0] if applied_jobs else self._last_applied_job_title
            final_company = applied_jobs[-1][1] if applied_jobs else self._last_applied_company

            return {
                "status": "success",
                "applied": applied_count,
                "skipped": skipped_count,
                "job_title": final_title,
                "company": final_company,
                "applied_jobs": applied_jobs,
            }

        except Exception as e:
            self.logger.log_err(f"Search and Apply fatal error: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            self.close()

    def _extract_job_title_company(self) -> tuple:
        """Multi-strategy extraction of job title and company from FoundIt JD page."""
        job_title = None
        company_name = None

        # --- Job Title: try multiple selectors ---
        title_selectors = [
            (By.CSS_SELECTOR, "h1.jd-title"),
            (By.CSS_SELECTOR, "h1[class*='jd']"),
            (By.CSS_SELECTOR, "h1[class*='title']"),
            (By.CSS_SELECTOR, "h1[class*='job']"),
            (By.TAG_NAME, "h1"),
        ]
        for by, sel in title_selectors:
            try:
                el = self.driver.find_element(by, sel)
                text = (el.text or "").strip()
                if text and text.lower() not in ("unknown", ""):
                    job_title = text
                    break
            except:
                continue

        # --- Company: try multiple selectors ---
        company_selectors = [
            # New FoundIt class names (2024-2025)
            (By.CSS_SELECTOR, "a[class*='line-clamp'][href*='-jobs-career']"),
            (By.CSS_SELECTOR, "a[class*='line-clamp'][href*='/company/']"),
            (By.CSS_SELECTOR, "a[href*='-jobs-career']"),
            (By.CSS_SELECTOR, "a[href*='/company/']"),
            # Older class names
            (By.CSS_SELECTOR, "a[class*='text-darkKnight']"),
            (By.CSS_SELECTOR, "span[class*='company']"),
            (By.CSS_SELECTOR, "div[class*='company'] a"),
            # Generic fallback: look for company link near title
            (By.XPATH, "//h1/following-sibling::*//a[1]"),
            (By.XPATH, "//section//a[contains(@href, '/company/')][1]"),
        ]
        for by, sel in company_selectors:
            try:
                el = self.driver.find_element(by, sel)
                text = (el.text or "").strip()
                if text and text.lower() not in ("unknown", ""):
                    company_name = text
                    break
            except:
                continue

        # Last resort: try to parse from page title ("Role - Company - Foundit")
        if not job_title or not company_name:
            try:
                page_title = self.driver.title or ""
                if " - " in page_title:
                    parts = [p.strip() for p in page_title.split(" - ")]
                    if not job_title and len(parts) >= 1:
                        job_title = job_title or parts[0]
                    if not company_name and len(parts) >= 2:
                        company_name = company_name or parts[1]
            except:
                pass

        # Clean company name of experience prefix and location suffix if matched
        if company_name and company_name.lower() not in ("unknown", ""):
            import re
            # Strip "X Years of Experience at " or similar prefix
            company_name = re.sub(r'(?i).*\bexperience\s+at\s+', '', company_name)
            # Strip any location suffix starting with " in " (case-insensitive)
            company_name = re.split(r'(?i)\s+in\s+', company_name)[0]
            company_name = company_name.strip(', ')

        return (job_title or "Unknown", company_name or "Unknown")

    def _process_single_job(self, index: int, profile: Any,
                            jd_url: str = None,
                            search_results_url: str = None) -> str:
        """Extract JD, match skills, and apply via Selenium."""
        try:
            # 1. Resolve job URL
            job_url = jd_url
            if not job_url:
                # Fallback: find the i-th apply button and traverse to get link
                try:
                    button = self.driver.find_elements(By.ID, "applyBtn")[index]
                    # Try multiple XPath strategies to find the job link
                    for xpath in [
                        "./ancestor::article//a[contains(@href, '/job/')][1]",
                        "./ancestor::div[contains(@class,'card')]//a[contains(@href,'/job/')][1]",
                        "./ancestor::li//a[contains(@href,'/job/')][1]",
                        "./preceding::a[contains(@href,'/job/')][1]",
                    ]:
                        try:
                            link = button.find_element(By.XPATH, xpath)
                            href = link.get_attribute("href")
                            if href:
                                job_url = href
                                break
                        except:
                            continue
                except:
                    pass

            if not job_url:
                self.logger.log_warn(f"Job {index}: Could not find JD URL")
                return "skipped"

            if not search_results_url:
                search_results_url = self.driver.current_url

            # 2. Open JD Page and wait for it to load
            self.driver.get(job_url)
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
            except:
                time.sleep(4)  # Fallback wait

            # 3. Extract Job Title and Company using multi-strategy extraction
            job_title, company_name = self._extract_job_title_company()
            self.logger.log_info(f"Evaluating: {job_title} at {company_name}")

            # Expand "View More" if exists
            try:
                view_more = self.driver.find_element(By.XPATH, "//button[contains(., 'View More')]")
                self.driver.execute_script("arguments[0].click();", view_more)
                time.sleep(1)
            except:
                pass

            # Extract JD text
            jd_text = ""
            try:
                jd_container = self.driver.find_element(
                    By.XPATH,
                    "//div[contains(@class,'job-desc') or contains(@class,'job-description') or contains(@class,'jd-desc')]"
                )
                jd_text = jd_container.text
            except:
                jd_text = self.driver.find_element(By.TAG_NAME, "body").text

            # 4. Skill Matching
            jd_skills = extract_skills_from_jd(jd_text)
            self.logger.log_info(f"JD Skills: {', '.join(jd_skills[:10])}")

            profile_skills = getattr(profile, 'skills', [])
            match_result = calculate_match_percentage(profile_skills, jd_skills, self.MATCH_PERCENTAGE_MIN)
            match_pct = match_result.get('percentage', 0)

            self.logger.log_info(f"Match: {match_pct}% (Threshold: {self.MATCH_PERCENTAGE_MIN}%)")

            if match_pct < self.MATCH_PERCENTAGE_MIN:
                self.logger.log_info("Match too low, skipping")
                self.driver.get(search_results_url)
                return "skipped"

            # 5. Resume Selection
            selector = ResumeSelector(getattr(profile, 'student_id', 'default'))
            res_type, res_path, res_source = selector.select_resume(jd_text, jd_skills, profile_skills, job_title)

            if res_type == "AI_TAILOR_NEEDED":
                self.logger.log_info("Triggering AI tailoring...")
                res_path = self._generate_ai_resume(jd_text, profile)

            if not res_path or not os.path.exists(res_path):
                self.logger.log_warn("No resume available for application")
                self.driver.get(search_results_url)
                return "skipped"

            # 6. Apply
            self._update_resume_on_profile(str(res_path))

            # Return to JD page
            self.driver.get(job_url)
            time.sleep(2)

            try:
                apply_btn = self._find_apply_button(timeout=15)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                time.sleep(0.5)
                try:
                    apply_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", apply_btn)
                time.sleep(4)

                # Check success indicators
                success_indicators = [
                    "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'applied successfully')]",
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'applied')]",
                    "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'thanks for applying')]",
                    "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'applied')]",
                ]
                applied = any(
                    self.driver.find_elements(By.XPATH, ind)
                    for ind in success_indicators
                )

                # Store title/company regardless of success detection
                self._last_applied_job_title = job_title
                self._last_applied_company = company_name

                if applied:
                    self.logger.log_ok(f"Applied successfully to {job_title} at {company_name}!")
                else:
                    self.logger.log_warn(f"Applied (unverified) to {job_title} at {company_name}")

                # Notify dashboard
                try:
                    import asyncio
                    asyncio.run(self.logger.log_application_success(
                        job_id=f"foundit_{index}_{int(time.time())}",
                        title=job_title,
                        company=company_name,
                        platform="foundit",
                        student_id=getattr(profile, "student_id", None)
                    ))
                except Exception as report_err:
                    self.logger.log_warn(f"Dashboard reporting failed: {report_err}")

                self.driver.get(search_results_url)
                return "applied"

            except Exception as e:
                self.logger.log_err(f"Apply button interaction failed: {e}")
                self.driver.get(search_results_url)
                return "skipped"

        except Exception as e:
            self.logger.log_err(f"Job processing error: {e}")
            return "skipped"

    def _update_resume_on_profile(self, resume_path: str) -> bool:
        """Update resume on FoundIt profile page via Selenium."""
        try:
            self.logger.log_info("Syncing resume to profile...")
            self.driver.get("https://www.foundit.in/rio/profile")
            time.sleep(3)
            
            # 1. Click 'Replace resume'
            try:
                replace_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Replace resume')]"))
                )
                self.driver.execute_script("arguments[0].click();", replace_btn)
                time.sleep(2)
            except:
                self.logger.log_warn("Replace button not found, searching for direct upload")
            
            # 2. Find file input (Hidden)
            # We use JS to make it visible then send keys
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.opacity = '1'; arguments[0].style.visibility = 'visible';", 
                    file_input
                )
                file_input.send_keys(resume_path)
                self.logger.log_info(f"Uploaded: {os.path.basename(resume_path)}")
                time.sleep(4)
                
                # Check for Save/Update button if it appeared
                save_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'Update') or contains(., 'Save')]")
                if save_btns:
                    save_btns[0].click()
                    time.sleep(2)
                
                self.logger.log_ok("Profile resume updated")
                return True
            except Exception as e:
                self.logger.log_err(f"Profile upload failed: {e}")
                return False
                
        except Exception as e:
            self.logger.log_err(f"Resume sync failed: {e}")
            return False

    def _generate_ai_resume(self, jd_text: str, profile: Any) -> Optional[str]:
        """Call AI Engine to generate tailored resume."""
        api_base = os.getenv("LOCAL_API_URL", "http://ai-engine:8000").rstrip("/")
        api_url = f"{api_base}/generate"
        
        try:
            # Simple content for retrieval
            retrieved_chunks = f"NAME: {profile.name}\nSKILLS: {', '.join(profile.skills)}"
            
            input_data = {
                "jobDescription": jd_text,
                "retrievedChunks": retrieved_chunks,
                "disableCache": False
            }
            
            response = requests.post(api_url, json=input_data, timeout=120)
            if response.status_code == 200:
                result = response.json()
                pdf_path = resolve_ai_engine_pdf_path(result)
                if pdf_path and os.path.exists(pdf_path):
                    return pdf_path
            
            self.logger.log_err(f"AI Engine failed with status {response.status_code}")
        except Exception as e:
            self.logger.log_err(f"AI Generation Error: {e}")
        
        return None

    def _find_apply_button(self, timeout: int = 15):
        """Find a clickable FoundIt apply control across listing and JD layouts."""
        selectors = [
            (By.ID, "applyBtn"),
            (By.CSS_SELECTOR, "button[id*='apply' i]"),
            (By.CSS_SELECTOR, "a[id*='apply' i]"),
            (By.CSS_SELECTOR, "button[class*='apply' i]"),
            (By.CSS_SELECTOR, "a[class*='apply' i]"),
            (
                By.XPATH,
                "//*[self::button or self::a][contains("
                "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),"
                " 'apply')]",
            ),
        ]

        last_error = None
        end_time = time.time() + timeout
        while time.time() < end_time:
            for by, value in selectors:
                try:
                    for el in self.driver.find_elements(by, value):
                        if el.is_displayed() and el.is_enabled():
                            text = (el.text or "").strip().lower()
                            if "applied" in text:
                                continue
                            return el
                except Exception as e:
                    last_error = e
            time.sleep(0.5)

        raise TimeoutException(f"FoundIt apply button not found: {last_error}")

    def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        time.sleep(random.uniform(min_sec, max_sec))

    def close(self):
        """Close driver."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except:
            pass

    # Legacy method for backward compatibility
    def search_jobs(self, keywords: list, location: str = "India", max_jobs: int = 10) -> list:
        """Search for jobs (Legacy sync version)."""
        self._init_driver()
        # ... (Implementation kept simple or redirected to new logic if needed)
        return []
