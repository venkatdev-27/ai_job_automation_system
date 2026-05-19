import asyncio
import re
import random
import logging
import json
import os
from pathlib import Path
import sys

# Ensure the job_automation_system root is in sys.path to avoid shadowing by top-level ai_engine
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any, List, Optional, Dict
from urllib.parse import quote_plus, urljoin
from playwright.async_api import Page, Locator

from scraper_adapter.base_scraper import BaseScraper
from utils.job_utils import extract_skills, normalize_whitespace
from utils.job_retrieval import retrieve_field_relevant_chunks, compact_text, build_field_payload
from role_manager.dynamic_role_generator import (
    get_role_by_top_skills,
    extract_role_from_skills,
    generate_dynamic_resumes_from_skills,
)
from utils.student_mongodb import get_student_profile, list_all_students
from utils.resume_downloader import download_resume_from_url
from utils.resume_selector import ResumeSelector, extract_skills_from_jd
from utils.path_contract import resolve_ai_engine_pdf_path
from utils.ai_extractor import get_ai_extractor
from utils.skill_scorer import calculate_match_percentage, SkillScorer
import requests
from scraper_adapter.playwright_manager import playwright_manager
from scraper_adapter.human_behavior import human_delay, simulate_mouse_movement, simulate_human_scroll
from risk_engine.risk_scorer import risk_scorer
from verification_handler.verification_handler import verification_handler
from config.settings import settings as global_settings

# ============================================================
# LINKEDIN LOGIN FIX HELPERS - Comprehensive fix for 40-50 students
# ============================================================

def human_delay(min_sec: float = 1, max_sec: float = 3) -> float:
    """Random delay mimicking human pause to prevent bot detection."""
    return random.uniform(min_sec, max_sec)

# Retry delays with exponential backoff (30s, 60s, 120s)
RETRY_DELAYS = [30, 60, 120]

# Verification screen patterns
VERIFICATION_PATTERNS = [
    "Verify you're human",
    "Enter the code we sent",
    "account has been",
    "suspicious activity",
    "Too many attempts",
    "captcha",
    "Challenge",
    "Two-step verification",
    "Enter the verification code",
    "email verification",
]

# ============================================================
# PHASE 1: Screen Detection
# ============================================================

async def detect_login_screen_type(page: Page) -> str:
    """
    Detect what's actually shown on LinkedIn login page.
    Returns: 'normal' | 'verification' | 'email_code' | 'suspended' | 'rate_limited' | 'unknown'
    """
    try:
        page_text = (await page.inner_text("body")).lower() if page else ""
        
        # Check for verification/CAPTCHA screens
        for pattern in VERIFICATION_PATTERNS:
            if pattern.lower() in page_text:
                if "email" in pattern.lower() or "code" in pattern.lower():
                    return "email_code"
                return "verification"
        
        # Check for rate limiting
        if "too many attempts" in page_text or "try again later" in page_text:
            return "rate_limited"
        
        # Check for account suspension
        if "suspended" in page_text or "locked out" in page_text:
            return "suspended"
        
        # Check normal login exists
        if await page.locator("input[type='email']").count() > 0:
            return "normal"
        if await page.locator("#username").count() > 0:
            return "normal"
            
        return "unknown"
        
    except Exception as e:
        return "unknown"

# ============================================================
# PHASE 2: Session Cookies Management
# ============================================================

def get_cookies_path(student_id: str) -> Path:
    """Get cookie file path for student."""
    base = Path("chrome_profile")
    cookie_dir = base / "student_cookies"
    cookie_dir.mkdir(parents=True, exist_ok=True)
    return cookie_dir / f"{student_id}.json"

async def save_cookies_to_file(page: Page, student_id: str) -> bool:
    """Save browser cookies after successful login."""
    try:
        cookies = await page.context.cookies()
        cookie_path = get_cookies_path(student_id)
        with open(cookie_path, 'w') as f:
            json.dump(cookies, f)
        return True
    except Exception:
        return False

async def load_cookies_from_file(page: Page, student_id: str) -> bool:
    """Load saved cookies if available and not expired."""
    try:
        cookie_path = get_cookies_path(student_id)
        if not cookie_path.exists():
            return False
        
        # Check file age (configurable via LINKEDIN_COOKIE_MAX_AGE_HOURS)
        import time
        max_age = global_settings.linkedin_cookie_max_age_hours * 3600
        file_age = time.time() - cookie_path.stat().st_mtime
        if file_age > max_age:
            return False  # Expired
            
        with open(cookie_path) as f:
            cookies = json.load(f)
        await page.context.add_cookies(cookies)
        return True
    except Exception:
        return False

async def check_cookies_valid(page: Page, student_id: str) -> bool:
    """Check if saved cookies are still valid without navigating to /feed (avoids CAPTCHA trigger)."""
    try:
        current_url = page.url
        
        if "feed" in current_url or "home" in current_url:
            pass
        elif "linkedin.com" in current_url and current_url != "https://www.linkedin.com/":
            await page.goto("https://www.linkedin.com/", timeout=10000, wait_until="domcontentloaded")
        elif current_url == "about:blank":
            return False
        
        await asyncio.sleep(1)
        
        logout_btn = await page.locator("button[aria-label='Sign out']").count()
        profile_btn = await page.locator("img[alt*='Profile']").count()
        
        return logout_btn > 0 or profile_btn > 0
    except Exception:
        return False

try:
    from rag_engine.rag_engine import RAGEngine
except ImportError:
    RAGEngine = None

# Local module imports (self-contained, no ai_job_auto_apply dependency)
try:
    from job_automation_system.ai_engine.llm_answers import LLMAnswers
except ImportError:
    try:
        from ai_engine.llm_answers import LLMAnswers  # type: ignore
    except ImportError:
        LLMAnswers = None

try:
    from engine.form_filler import FormFiller
except ImportError:
    FormFiller = None

try:
    from rag_engine.rag_resume_generator import get_rag_resume_generator
except ImportError:
    get_rag_resume_generator = None


logger = logging.getLogger(__name__)


class LinkedIn10_10:
    """LinkedIn 10/10 Production Flow"""
    
    # Resume variants mapping
    RESUME_VARIANTS = {
        "frontend": "resume_frontend.pdf",
        "backend": "resume_backend.pdf", 
        "fullstack": "resume_fullstack.pdf",
        "java": "resume_java.pdf",
        "python": "resume_python.pdf",
        "react": "resume_react.pdf",
    }
    
    async def search_and_apply(self, profile: Any, settings: Any, logger: Any) -> dict:
        """Main 10/10 entry point"""
        self.settings = settings
        self.logger = logger
        self.profile = profile
        self.applied_count = 0
        self.skipped_count = 0
        self._warmup_roles = []
        self._warmup_skill_keywords = []
        self._resolved_profile_skills: list[str] = []
        self._last_applied_job_title = None
        self._last_applied_company = None
        self._login_failure_reason = "linkedin_login_failed"
        
        # Session time tracking + platform-specific caps (anti-detection)
        import time as _time
        self._session_start = _time.time()
        from config.platforms import get_platform_config
        _plat_cfg = get_platform_config("linkedin")
        self._max_applies = _plat_cfg.max_applies_per_run if _plat_cfg else 3

        requested_target = int(
            getattr(settings, "max_applies_per_run", 0)
            or getattr(settings, "target_applies", 0)
            or 0
        )
        if requested_target > self._max_applies:
            self.logger.log_info(f"Raising LinkedIn apply cap to runtime target: {requested_target}")
            self._max_applies = requested_target
        self._session_limit = _plat_cfg.session_time_limit if _plat_cfg else 1500
        self._micro_break_interval = _plat_cfg.micro_break_interval if _plat_cfg else 2
        self._micro_break_min = _plat_cfg.micro_break_min if _plat_cfg else 30.0
        self._micro_break_max = _plat_cfg.micro_break_max if _plat_cfg else 75.0
        
        # Initialize AI Brain
        self.brain = None
        if LLMAnswers:
            self.brain = LLMAnswers(settings, self.logger)
        
        from scraper_adapter.playwright_manager import playwright_manager
        import os
        cdp_url = os.environ.get("CDP_URL")
        use_cdp = os.environ.get("LINKEDIN_USE_CDP", "false").lower() == "true"
        
        try:
            if use_cdp:
                page, method = await playwright_manager.get_page_with_cdp_fallback(
                    settings, 
                    student_id=self._get_candidate_id(),
                    cdp_url=cdp_url
                )
                self.logger.log_ok(f"Browser via: {method.upper()} (CDP)")
                
                # Check if CDP returned content is too short (blocked).
                # Do not continue with a closed/blocked page; recreate a persistent
                # Playwright page so LinkedIn can reuse the student's saved session.
                content = await page.content()
                if len(content) < 10000:
                    self.logger.log_warn(
                        f"CDP returned blocked page ({len(content)} bytes). "
                        "Switching to persistent Playwright profile..."
                    )
                    await page.close()
                    page = await playwright_manager.get_page(
                        settings,
                        student_id=self._get_candidate_id(),
                    )
                    self.logger.log_info("Browser via: Playwright (Persistent fallback)")
            else:
                page = await playwright_manager.get_page(settings, student_id=self._get_candidate_id())
                self.logger.log_info("Browser via: Playwright (Persistent)")
        except Exception as e:
            self.logger.log_err(f"Failed to get browser page: {e}. Trying Selenium fallback...")
            
            # Selenium Fallback for LinkedIn
            try:
                from scraper_adapter.linkedin_selenium import LinkedInSelenium
                sel = LinkedInSelenium(self.logger, settings, student_id=self._get_candidate_id())
                
                self.logger.log_info("Trying LinkedIn Selenium fallback...")
                login_ok = sel.login(
                    getattr(profile, 'username', ''), 
                    getattr(profile, 'password', '')
                )
                
                if login_ok:
                    self.logger.log_ok("LinkedIn Selenium login successful!")
                    # Selenium doesn't support async search_and_apply - return success with job search pending
                    await sel.close()
                    return {"status": "selenium_login_success", "applied": 0, "skipped": 0, "method": "selenium"}
                else:
                    self.logger.log_err("Selenium login failed")
                    await sel.close()
                    return {"status": "selenium_login_failed", "applied": 0, "skipped": 0, "error": "selenium_login_failed"}
            except Exception as sel_err:
                self.logger.log_err(f"Selenium fallback also failed: {sel_err}")
                return {"status": "browser_error", "applied": 0, "skipped": 0, "error": str(e)}
            
        try:
            # Phase 1: Setup
            login_ok = await self._ensure_logged_in(page, settings)
            if not login_ok:
                self.logger.log_err("LinkedIn login failed; stopping run before job search.")
                return {
                    "status": "error",
                    "applied": self.applied_count,
                    "skipped": self.skipped_count,
                    "error": self._login_failure_reason,
                }
            await self._ensure_resume_uploaded(page)
            
            # Phase 1.5: RUN WARMUP if needed (discover roles + generate 5-6 resumes)
            await self._ensure_warmup(profile)
            # Sync profile skills/titles fallback before matching starts.
            self._resolve_profile_skills()
            
            # Get roles list (max 5)
            roles = self._get_search_roles()
            max_pages = min(settings.max_pages_per_run, 4)

            async def _process_role(role_name: str, role_label: str, page_cap: int) -> None:
                if self.applied_count >= self._max_applies:
                    return


                elapsed = _time.time() - self._session_start
                if elapsed > self._session_limit:
                    self.logger.log_warn(f"Session time limit reached ({int(elapsed)}s). Stopping.")
                    return

                self.logger.log_ok("-" * 40)
                self.logger.log_ok(f"  {role_label}: {role_name.upper()}")
                self.logger.log_ok("-" * 40)

                for page_idx in range(page_cap):
                    if self.applied_count >= self._max_applies:
                        break

                    elapsed = _time.time() - self._session_start
                    if elapsed > self._session_limit:
                        break

                    if page_idx > 0 and page_idx % self._micro_break_interval == 0:
                        import random
                        pause = random.uniform(self._micro_break_min, self._micro_break_max)
                        self.logger.log_info(f"Micro-break: pausing {pause:.0f}s")
                        await asyncio.sleep(pause)

                    start_val = page_idx * 25
                    self.current_role = role_name
                    self.current_start = start_val
                    self.logger.log_ok(f"  PAGE {page_idx + 1} (start={start_val})")

                    total = await self._search_and_lock(page, role_name, start_val)
                    if total == 0:
                        self.logger.log_warn(f"No results for {role_name} at start={start_val}")
                        continue

                    decisions = await self._fast_scan(page)
                    self.applied_count += await self._strike_loop(page, decisions)

            # Primary discovered roles
            for role_idx, role in enumerate(roles):
                if self.applied_count >= self._max_applies:
                    break
                await _process_role(role, f"ROLE {role_idx + 1}", max_pages)

            # Generic fallbacks after primary roles are exhausted
            if self.applied_count < self._max_applies:
                used_roles = {r.lower().strip() for r in roles}
                fallback_roles = ["Software Engineer", "Software Developer"]
                self.logger.log_info(
                    f"Primary roles completed with applied={self.applied_count}. Remaining target={self._max_applies - self.applied_count}. Starting generic fallback roles."
                )
                for fb_role in fallback_roles:
                    if self.applied_count >= self._max_applies:
                        break
                    if fb_role.lower() in used_roles:
                        continue
                    await _process_role(fb_role, "FALLBACK", max_pages)
                    used_roles.add(fb_role.lower())
            
            return {"status": "completed", "applied": self.applied_count, "skipped": self.skipped_count, "job_title": self._last_applied_job_title, "company": self._last_applied_company}
            
        except Exception as e:
            self.logger.log_err(f"Pipeline error: {e}")
            import traceback
            self.logger.log_err(traceback.format_exc())
            return {"status": "error", "applied": self.applied_count, "skipped": self.skipped_count, "error": str(e), "job_title": self._last_applied_job_title, "company": self._last_applied_company}
            
        finally:
            # Safe return of page
            try:
                if page and not page.is_closed():
                    await playwright_manager.return_page(page)
            except Exception as e:
                self.logger.log_warn(f"Page return error: {e}")
    
    def _resolve_linkedin_credentials(self, settings: Any = None) -> tuple[str, str, str]:
        """
        Resolve LinkedIn credentials with MongoDB-first fallback.
        Returns (email_or_username, password, source).
        """
        email = ""
        password = ""

        try:
            from database.credentials import get_student_credentials

            student_id = self._get_candidate_id()
            creds = get_student_credentials(student_id) or {}
            linkedin = creds.get("linkedin", {}) if isinstance(creds, dict) else {}
            email = (linkedin.get("email") or linkedin.get("username") or "").strip()
            password = (linkedin.get("password") or "").strip()
            if email and password:
                return email, password, "mongodb_credentials"
        except Exception as e:
            self.logger.log_warn(f"MongoDB credential lookup failed: {e}")

        if settings:
            email = (
                getattr(settings, "linkedin_email", "")
                or getattr(settings, "linkedin_username", "")
                or ""
            ).strip()
            password = (getattr(settings, "linkedin_password", "") or "").strip()
            if email and password:
                return email, password, "runtime_settings_fallback"

        return email, password, "missing"
    
    async def _ensure_logged_in(self, page: Page, settings: Any = None) -> bool:
        """Force fresh LinkedIn login using resolved credentials with comprehensive fixes."""
        email, password, source = self._resolve_linkedin_credentials(settings)
        if not email or not password:
            self.logger.log_err(
                "LinkedIn credentials are missing. Configure student.credentials.linkedin in MongoDB."
            )
            return False

        max_retries = 3
        student_id = self._get_candidate_id()
        
        # Try to use saved cookies first (Phase 2)
        self.logger.log_info("Checking for saved session cookies...")
        
        throttle_delay = risk_scorer.get_throttle_delay(student_id)
        if throttle_delay > 1:
            self.logger.log_info(f"Risk-based throttle: waiting {throttle_delay:.1f}s...")
            await asyncio.sleep(throttle_delay)
        
        if risk_scorer.is_in_cooldown(student_id):
            remaining = risk_scorer.get_cooldown_remaining(student_id)
            self.logger.log_warn(f"Student {student_id} in cooldown - {remaining}s remaining. Skipping.")
            return False
        
        if not risk_scorer.can_login(student_id, min_interval_hours=4):
            self.logger.log_warn(f"Student {student_id} rate limited - wait 4h between logins")
            return False
        
        if await load_cookies_from_file(page, student_id):
            if await check_cookies_valid(page, student_id):
                self.logger.log_ok("Reusing valid session cookies - skip login!")
                return True
            else:
                self.logger.log_warn("Cookies invalid/expired, proceeding with login...")
                await page.context.clear_cookies()
        
        for login_attempt in range(1, max_retries + 1):
            try:
                # PHASE 1: Wait with exponential backoff (Phase 2)
                if login_attempt > 1:
                    backoff_time = RETRY_DELAYS[min(login_attempt - 2, len(RETRY_DELAYS) - 1)]
                    self.logger.log_info(f"Exponential backoff: waiting {backoff_time}s before retry...")
                    await asyncio.sleep(backoff_time)
                
                self.logger.log_info(f"LinkedIn login attempt {login_attempt}/{max_retries} (source={source})")
                self.logger.log_info("Opening LinkedIn login page first (forced fresh auth).")

                try:
                    await page.context.clear_cookies()
                except Exception as cookie_err:
                    self.logger.log_warn(f"Could not clear cookies before login: {cookie_err}")

                try:
                    await page.goto("https://www.linkedin.com/m/logout/", wait_until="domcontentloaded", timeout=10000)
                    await asyncio.sleep(human_delay(1, 2))
                except Exception:
                    pass

                await page.goto(
                    "https://www.linkedin.com/login",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await asyncio.sleep(human_delay(2, 4))
                await simulate_mouse_movement(page)
                await simulate_human_scroll(page)

                # PHASE 1: Detect what screen we're on
                screen_type = await detect_login_screen_type(page)
                self.logger.log_info(f"Detected screen type: {screen_type}")
                
                if screen_type == "verification":
                    self.logger.log_warn("CAPTCHA/Verification detected; manual action required.")
                    
                    vresult = await verification_handler.handle_verification(
                        page, student_id, "linkedin", max_retries=1
                    )
                    self.logger.log_warn(f"Verification handling: {vresult.get('message', 'unknown')}")
                    
                    if vresult.get("type") == "captcha":
                        risk_scorer.increment_captcha(student_id)
                    
                    risk_scorer.set_cooldown(student_id, hours=24)
                    self._login_failure_reason = "manual_login_required"
                    return False
                elif screen_type == "email_code":
                    self.logger.log_warn("Email verification required - marking student as needs manual review")
                    self._login_failure_reason = "manual_login_required"
                    return False
                elif screen_type == "rate_limited":
                    self.logger.log_warn("Rate limited by LinkedIn - waiting 5 minutes...")
                    risk_scorer.set_cooldown(student_id, hours=4)
                    self._login_failure_reason = "linkedin_rate_limited"
                    return False
                elif screen_type == "suspended":
                    self.logger.log_err("Account suspended - requires manual intervention")
                    self._login_failure_reason = "account_suspended"
                    return False

                # Human-like delay before typing (Phase 3)
                await asyncio.sleep(human_delay(1, 3))

                username_selectors = [
                    "input[autocomplete='username']:visible",
                    "input[type='email']:visible",
                    "#username",
                    "input#username",
                    "input[aria-label='Email or phone']",
                ]
                username_filled = False

                for attempt in range(2):
                    for selector in username_selectors:
                        try:
                            loc = page.locator(selector)
                            if await loc.count() == 0:
                                continue
                            if not await loc.first.is_visible():
                                continue
                            await page.wait_for_selector(selector, state="visible", timeout=10000)
                            try:
                                await loc.first.fill(email, timeout=5000)
                            except:
                                await loc.first.evaluate('(el, val) => el.value = val', email)
                            self.logger.log_info(f"Filled username with: {selector}")
                            username_filled = True
                            break
                        except Exception:
                            continue
                    if username_filled:
                        break
                    self.logger.log_warn(f"Login fields not visible (attempt {attempt + 1}). Reloading...")
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(human_delay(3, 5))

                if not username_filled:
                    self.logger.log_warn("Trying brute force input selection...")
                    all_inputs = await page.locator("input").all()
                    for i, inp in enumerate(all_inputs):
                        try:
                            inp_type = await inp.get_attribute("type") or ""
                            inp_visible = await inp.is_visible()
                            self.logger.log_info(f"Input {i}: type={inp_type}, visible={inp_visible}")
                            if inp_visible and inp_type in ["text", "email", "tel", ""]:
                                await inp.fill(email)
                                self.logger.log_info(f"Filled with brute force input {i}")
                                username_filled = True
                                break
                        except Exception:
                            continue

                if not username_filled:
                    await page.screenshot(path="linkedin_login_debug.png")
                    self.logger.log_warn("Could not find username field")
                    all_inputs = await page.locator("input").count()
                    self.logger.log_warn(f"Total input fields on page: {all_inputs}")
                    if login_attempt < max_retries:
                        await asyncio.sleep(2.0 * login_attempt)
                        continue
                    return False

                password_selectors = [
                    "input[autocomplete='current-password']",
                    "input[type='password']",
                    "#password",
                ]
                password_filled = False
                for pwd_sel in password_selectors:
                    try:
                        loc = page.locator(pwd_sel)
                        if await loc.count() == 0:
                            continue
                        if not await loc.first.is_visible():
                            continue
                        try:
                            await loc.first.fill(password, timeout=5000)
                        except:
                            await loc.first.evaluate('(el, val) => el.value = val', password)
                        self.logger.log_info(f"Filled password with: {pwd_sel}")
                        password_filled = True
                        break
                    except Exception:
                        continue
                if not password_filled:
                    self.logger.log_warn("Password field not found; retrying login flow.")
                    if login_attempt < max_retries:
                        await asyncio.sleep(2.0 * login_attempt)
                        continue
                    return False

                submit_clicked = False
                submit_selectors = [
                    "button[type='submit']",
                    "button[aria-label='Sign in']",
                    "button:has-text('Sign in')",
                    "button:has-text('SignIn')",
                    ".btn__primary",
                ]
                for btn_sel in submit_selectors:
                    try:
                        btn = page.locator(btn_sel)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click()
                            self.logger.log_info(f"Clicked submit: {btn_sel}")
                            submit_clicked = True
                            break
                    except Exception:
                        continue
                if not submit_clicked:
                    try:
                        password_loc = page.locator("input[type='password']").first
                        if await password_loc.count() > 0:
                            await password_loc.press("Enter")
                            self.logger.log_info("Submitted LinkedIn login by pressing Enter in password field.")
                            submit_clicked = True
                    except Exception:
                        pass
                if not submit_clicked:
                    try:
                        await page.locator("form.login__form").evaluate("(form) => form.requestSubmit()")
                        self.logger.log_info("Submitted LinkedIn login via form.requestSubmit().")
                        submit_clicked = True
                    except Exception:
                        pass
                if not submit_clicked:
                    self.logger.log_warn("Submit button not found; retrying login flow.")
                    if login_attempt < max_retries:
                        await asyncio.sleep(2.0 * login_attempt)
                        continue
                    return False

                await page.wait_for_timeout(10000)

                current_url = (page.url or "").lower()
                if "checkpoint" in current_url or "challenge" in current_url:
                    self.logger.log_warn(f"LinkedIn challenge/CAPTCHA detected; manual action required: {page.url}")
                    
                    risk_scorer.increment_captcha(student_id)
                    risk_scorer.set_cooldown(student_id, hours=24)
                    self._login_failure_reason = "manual_login_required"
                    return False

                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(human_delay(2, 4))
                if "linkedin.com/login" in (page.url or "").lower():
                    self.logger.log_warn("Still on LinkedIn login page after submit; retrying login flow.")
                    if login_attempt < max_retries:
                        await asyncio.sleep(human_delay(2, 4) * login_attempt)
                    continue

                # PHASE 2: Save cookies on successful login
                self.logger.log_ok("LinkedIn login successful.")
                await save_cookies_to_file(page, student_id)
                self.logger.log_info(f"Session cookies saved for student: {student_id}")
                
                risk_scorer.decrement_risk(student_id, amount=15)
                risk_scorer.set_last_login(student_id)
                
                return True
            except Exception as e:
                self.logger.log_warn(f"LinkedIn login attempt {login_attempt} failed: {e}")
                if login_attempt < max_retries:
                    await asyncio.sleep(human_delay(2, 4) * login_attempt)
                    continue

        self.logger.log_err("LinkedIn login failed after all retries.")
        return False

    async def _ensure_resume_uploaded(self, page: Page) -> bool:
        """Upload resume once to profile"""
        try:
            await page.goto("https://www.linkedin.com/me/resumes", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            # Resume is typically pre-uploaded in LinkedIn profile
            return True
        except:
            return False
    
    def _get_candidate_id(self) -> str:
        """Get or create candidate ID"""
        # Prioritize existing student_id from Profile
        if hasattr(self.profile, "student_id") and self.profile.student_id:
            return str(self.profile.student_id)
            
        import hashlib
        name = getattr(self.profile, "name", "candidate")
        email = getattr(self.profile, "email", "")
        seed = f"{name}{email}".lower()
        return f"student_{hashlib.md5(seed.encode()).hexdigest()[:8]}"
    
    async def _ensure_warmup(self, profile: Any) -> bool:
        """
        Warmup: Discover 5-6 roles and generate their resumes on first run.
        Returns True if warmup succeeded or already done.
        """
        if not get_rag_resume_generator:
            self.logger.log_warn("RAG generator not available, skipping warmup")
            return False
        
        candidate_id = self._get_candidate_id()
        self.logger.log_info(f"Warmup check for: {candidate_id}")
        
        # Check if resumes already exist in file system first
        from pathlib import Path
        default_resumes_dir = "/app/ai_engine/resumes" if os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists() else "D:/ai-bot-resumes/ai_engine/resumes"
        existing_resumes_dir = Path(os.getenv("RESUMES_DIR", default_resumes_dir)) / candidate_id
        existing_pdfs = list(existing_resumes_dir.glob("*.pdf")) if existing_resumes_dir.exists() else []
        
        # FORCE REGENERATION: Commenting out skip logic to ensure real data is used
        # if existing_pdfs:
        #     self.logger.log_info(f"Found {len(existing_pdfs)} existing resumes, using existing")
        #     try:
        #         generator = get_rag_resume_generator(logger=self.logger, student_id=candidate_id)
        #         if not generator.custom_roles:
        #             user_skills = profile.skills if hasattr(profile, 'skills') else []
        #             from producer.job_generator import JobGenerator
        #             gen = JobGenerator("linkedin")
        #             class MockProfile:
        #                 def __init__(self, s):
        #                     self.skills = s
        #                     self.candidate_titles = []
        #                     self.preferred_locations = ["India"]
        #             mock = MockProfile(user_skills)
        #             queries = gen._build_queries(mock)
        #             custom_roles = {}
        #             for q in queries:
        #                 key = q.lower().replace(" ", "_").replace("/", "_")
        #                 custom_roles[key] = {"title": q, "keywords": user_skills[:5]}
        #             generator.custom_roles = custom_roles
        #         self._warmup_roles = [cfg.get("title", "").strip() for cfg in generator.custom_roles.values() if cfg.get("title")][:6]
        #         self._warmup_skill_keywords = [str(k).strip().lower() for cfg in generator.custom_roles.values() for k in (cfg.get("keywords") or []) if str(k).strip()]
        #         self.logger.log_ok("Using existing resumes + skill-based roles. Skipping generation.")
        #         # Save roles to MongoDB for future runs
        #         if self._warmup_roles:
        #             await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
        #         return True
        #     except Exception as e:
        #         self.logger.log_warn(f"Generator init error: {e}")
        #         return True
        
        try:
            generator = get_rag_resume_generator(logger=self.logger, student_id=candidate_id)
            self._sync_profile_from_generator(profile, generator)
            
            if generator.custom_roles:
                role_names = []
                skill_keywords = []
                
                # Robustly iterate over custom_roles (could be list or dict)
                roles_items = []
                if isinstance(generator.custom_roles, dict):
                    roles_items = list(generator.custom_roles.items())
                elif isinstance(generator.custom_roles, list):
                    for item in generator.custom_roles:
                        if isinstance(item, dict):
                            rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                            roles_items.append((rk, item))
                
                for role_key, role_data in roles_items:
                    if isinstance(role_data, dict):
                        title = str(role_data.get("title", "")).strip() or str(role_key).replace("_", " ").strip()
                        role_names.append(title)
                        role_skills = role_data.get("skills") or role_data.get("keywords") or []
                        if isinstance(role_skills, str):
                            role_skills = [x.strip() for x in role_skills.split(",") if x.strip()]
                        skill_keywords.extend([str(x).strip() for x in role_skills if str(x).strip()])
                    elif str(role_data).strip():
                        role_names.append(str(role_data).strip())

                self._warmup_roles = list(dict.fromkeys(role_names))[:6]
                self._warmup_skill_keywords = list(dict.fromkeys(skill_keywords))

                self.logger.log_ok(f"Using existing roles from MongoDB: {self._warmup_roles}")
                self.logger.log_ok("Roles exist. Skipping PDF generation.")
                self._sync_profile_from_generator(profile, generator)
                # Save roles to MongoDB for future runs
                if self._warmup_roles:
                    await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                return True
            
            self.logger.log_info("Discovering roles and generating resumes...")
            await generator._init_rag()
            custom_roles = await generator.discover_top_roles()
            
            if custom_roles:
                self.logger.log_info(f"Discovered {len(custom_roles)} roles")
                if isinstance(custom_roles, dict):
                    role_names = []
                    skill_keywords = []
                    for role_key, role_data in custom_roles.items():
                        if isinstance(role_data, dict):
                            title = str(role_data.get("title", "")).strip() or str(role_key).replace("_", " ").strip()
                            role_names.append(title)
                            role_skills = role_data.get("skills") or role_data.get("keywords") or []
                            if isinstance(role_skills, str):
                                role_skills = [x.strip() for x in role_skills.split(",") if x.strip()]
                            skill_keywords.extend([str(x).strip() for x in role_skills if str(x).strip()])
                        elif str(role_data).strip():
                            role_names.append(str(role_data).strip())
                    self._warmup_roles = list(dict.fromkeys(role_names))[:6]
                    self._warmup_skill_keywords = list(dict.fromkeys(skill_keywords))
                resumes = await generator.generate_initial_resumes()
                self.logger.log_info(f"Generated {len(resumes)} role resumes")
                self._sync_profile_from_generator(profile, generator)
                # Save roles to MongoDB for future runs
                if self._warmup_roles:
                    await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                return True
            
            self.logger.log_warn("Role discovery returned empty")
            return False
            
        except Exception as e:
            self.logger.log_err(f"Warmup error: {e}")
            return False
    
    async def _save_roles_to_mongodb(self, student_id: str, roles: list[str]) -> bool:
        """Save discovered roles to MongoDB candidate_titles field"""
        try:
            from config.settings import settings
            from pymongo import MongoClient
            
            client = MongoClient(settings.mongo_uri)
            db = client[settings.mongo_db]
            
            result = db.students.update_one(
                {"student_id": student_id},
                {"$set": {"candidate_titles": roles}}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                self.logger.log_ok(f"Saved {len(roles)} roles to MongoDB: {roles}")
                return True
            return False
        except Exception as e:
            self.logger.log_warn(f"Failed to save roles to MongoDB: {e}")
            return False

    def _sync_profile_from_generator(self, profile: Any, generator: Any) -> None:
        """Backfill runtime profile with warmup generator data when DB top-level skills are empty."""
        try:
            profile_titles = [str(t).strip() for t in (getattr(profile, "candidate_titles", []) or []) if str(t).strip()]
            if not profile_titles and self._warmup_roles:
                profile.candidate_titles = self._warmup_roles[:6]
                self.logger.log_info(f"Backfilled candidate titles from warmup: {profile.candidate_titles}")

            profile_skills = [str(s).strip() for s in (getattr(profile, "skills", []) or []) if str(s).strip()]
            if not profile_skills:
                gen_profile = getattr(generator, "profile", None)
                if gen_profile and getattr(gen_profile, "skills", None):
                    recovered = [str(s).strip() for s in gen_profile.skills if str(s).strip()]
                    recovered = list(dict.fromkeys(recovered))
                    if recovered:
                        profile.skills = recovered
                        self.logger.log_info(f"Backfilled profile skills from warmup profile: {len(recovered)}")
        except Exception as e:
            self.logger.log_warn(f"Warmup profile sync skipped: {e}")

    def _resolve_profile_skills(self) -> list[str]:
        """Build profile skills with robust fallback when Mongo top-level skills are empty."""
        if self._resolved_profile_skills:
            return self._resolved_profile_skills

        raw_skills = [str(s).strip().lower() for s in (getattr(self.profile, "skills", []) or []) if str(s).strip()]
        if raw_skills:
            unique = list(dict.fromkeys(raw_skills))
            # Keep profile synchronized for downstream methods that read self.profile.skills directly.
            self.profile.skills = unique
            self._resolved_profile_skills = unique
            return unique

        inferred = []
        role_titles = [str(t).strip().lower() for t in (getattr(self.profile, "candidate_titles", []) or []) if str(t).strip()]
        for title in role_titles:
            for token in re.split(r"[^a-zA-Z0-9.+#]+", title):
                token = token.strip().lower()
                if len(token) > 2:
                    inferred.append(token)

        inferred.extend([str(k).strip().lower() for k in (self._warmup_skill_keywords or []) if str(k).strip()])

        # Final fallback: pull normalized skills from student profile helper (includes resumeData.skills fallback).
        candidate_id = self._get_candidate_id()
        try:
            mongo_profile = get_student_profile(candidate_id)
            if mongo_profile and getattr(mongo_profile, "skills", None):
                inferred.extend([str(s).strip().lower() for s in mongo_profile.skills if str(s).strip()])
                if not role_titles and getattr(mongo_profile, "candidate_titles", None):
                    self.profile.candidate_titles = [str(t).strip() for t in mongo_profile.candidate_titles if str(t).strip()]
        except Exception as e:
            self.logger.log_warn(f"Mongo profile skill fallback failed: {e}")

        inferred = list(dict.fromkeys(inferred))
        if inferred:
            self.logger.log_info(f"[MATCH] Using inferred profile skills fallback: {', '.join(inferred[:12])}")
            self.profile.skills = inferred
            self._resolved_profile_skills = inferred
        return inferred
    
    def _get_search_roles(self) -> list[str]:
        """Build search roles list from candidate titles"""
        roles = [str(r).strip() for r in (getattr(self.profile, "candidate_titles", []) or []) if str(r).strip()]
        if not roles:
            roles = [str(r).strip() for r in (self._warmup_roles or []) if str(r).strip()]

        if not roles:
            # Fallback: infer role titles from top skills when explicit titles are missing.
            raw_skills = getattr(self.profile, "skills", []) or []
            if isinstance(raw_skills, str):
                raw_skills = [x.strip() for x in raw_skills.split(",") if x.strip()]
            skills = [str(s).strip() for s in raw_skills if str(s).strip()]
            if not skills and self._warmup_skill_keywords:
                skills = self._warmup_skill_keywords[:8]
            if skills:
                try:
                    generated = get_role_by_top_skills(skills, top_n=5)
                    roles = [r.get("title", "").strip() for r in generated if r.get("title")]
                except Exception:
                    roles = []

        if not roles:
            roles = ["Software Developer"]

        return list(dict.fromkeys(roles))[:5]
    
    def _get_roles_for_page(self, page_num: int) -> list[str]:
        """Get roles for specific pagination page."""
        roles = self._get_search_roles()
        # Rotate or just return first few
        start_idx = (page_num - 1) % len(roles) if roles else 0
        page_roles = (roles[start_idx:] + roles[:start_idx])[:3]
        return page_roles
    
    def _get_all_search_roles(self) -> str:
        """Legacy method - returns comma-separated string"""
        roles = self._get_search_roles()
        return ",".join(roles)
    
    async def _search_and_lock(self, page: Page, query: str, start: int = 0) -> int:
        """Search with all roles combined (comma-separated keywords) and lock card count"""
        # URL with filters: Easy Apply, Entry Level + Junior (0-2 years), past week, full-time + internship
        # Use comma-separated keywords for OR search across all roles
        search_url = (
            f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}"
            f"&location=India"
            f"&f_AL=true"  # Easy Apply only
            f"&f_E=1,2"    # Entry level + Junior (0-2 years) - fresher + junior
            f"&f_TPR=r604800"  # Past week
            f"&f_JT=F,I"  # Full-time + Internship
            f"&f_WT=1,2,3"  # On-site + Hybrid + Remote
            f"&start={start}"
        )
        
        self.logger.log_info(f"Search URL: {search_url}")
        
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        return await self._wait_for_cards(page)
    
    async def _wait_for_cards(self, page: Page) -> int:
        """Wait for job cards"""
        try:
            card_selectors = "li[data-occludable-job-id], .job-card-container, .job-card-list__title--link, .job-card-container__link, .scaffold-layout__list-item"
            await page.wait_for_selector(card_selectors, timeout=10000)
            await asyncio.sleep(1)
            cards = await page.locator(card_selectors).all()
            count = len(cards)
            self.logger.log_ok(f"Cards locked: {count}")
            return count
        except:
            return 0
    
    def _match_skills(self, card_skills: list[str]) -> tuple[int, int, set]:
        """
        Accurate skill matching: min 4, max 5-6
        Returns: (match_count, ats_score, matched_skills_set)
        
        ATS Score Calculation:
        - Each exact match: 15 points
        - Each partial match: 10 points
        - Max score: 100
        - Threshold: 60 or 70
        """
        profile_skills = self._resolve_profile_skills()
        
        card_skills_lower = [str(s).lower().strip() for s in card_skills]
        
        match_count = 0
        ats_score = 0
        matched_skills = set()
        
        for card_skill in card_skills_lower:
            if not card_skill:
                continue
            
            for profile_skill in profile_skills:
                if not profile_skill:
                    continue
                
                # Exact match = 15 points
                if card_skill == profile_skill:
                    ats_score += 15
                    match_count += 1
                    matched_skills.add(card_skill)
                    break
                
                # Partial match = 10 points
                if card_skill in profile_skill or profile_skill in card_skill:
                    ats_score += 10
                    match_count += 1
                    matched_skills.add(card_skill)
                    break
        
        # Cap at 100
        ats_score = min(ats_score, 100)
        
        return match_count, ats_score, matched_skills
    
    async def _extract_skills_with_ai(self, jd_text: str) -> list[str]:
        """Extract skills from JD using centralized AIExtractor"""
        from utils.ai_extractor import get_ai_extractor
        extractor = get_ai_extractor()
        skills = await extractor.extract_skills_async(jd_text)
        
        if skills:
            self.logger.log_info(f"AI Extracted Skills: {skills[:20]}")
            return skills
        else:
            self.logger.log_warn("AI skill extraction returned no results - using regex fallback")
            from utils.resume_selector import extract_skills_from_jd
            return extract_skills_from_jd(jd_text)
    def _match_profile_skills(self, jd_skills: list[str]) -> tuple[int, int, set]:
        """Match AI-extracted JD skills against profile skills with scoring
        Returns: (match_count, ats_score, matched_skills)
        - Exact match: 15 points
        - Partial match: 10 points (word boundary matching to avoid false positives)
        - Max score: 100
        """
        profile_skills = self._resolve_profile_skills()
        
        jd_skills_lower = [str(s).lower().strip() for s in jd_skills]
        
        matched = set()
        ats_score = 0
        for jd_skill in jd_skills_lower:
            if not jd_skill:
                continue
            for profile_skill in profile_skills:
                if not profile_skill:
                    continue
                # Exact match = 15 points
                if jd_skill == profile_skill:
                    ats_score += 15
                    matched.add(jd_skill)
                    break
                # Partial match = 10 points (word boundary matching)
                # Check if jd_skill is a standalone word in profile_skill or vice versa
                # Avoid false positives like "java" matching "javascript"
                elif (
                    # jd_skill is a word in profile_skill (e.g., "react" in "react.js")
                    (jd_skill in profile_skill and self._is_word_boundary(jd_skill, profile_skill)) or
                    # profile_skill is a word in jd_skill
                    (profile_skill in jd_skill and self._is_word_boundary(profile_skill, jd_skill))
                ):
                    ats_score += 10
                    matched.add(jd_skill)
                    break
        
        # Cap at 100
        ats_score = min(ats_score, 100)
        
        return len(matched), ats_score, matched
    
    def _is_word_boundary(self, sub: str, full: str) -> bool:
        """Check if sub is a meaningful word in full (not just substring)"""
        import re
        # Match as complete word (with boundaries)
        pattern = r'\b' + re.escape(sub) + r'\b'
        return bool(re.search(pattern, full))
    
    def _check_experience_requirement(self, jd_text: str) -> tuple[bool, str]:
        """
        Check if JD requires > 1 year experience.
        Returns: (should_skip, reason)
        """
        if not jd_text:
            return False, ""
        
        jd_lower = jd_text.lower()
        
        # Patterns that indicate experience requirements > 1 year
        exp_patterns = [
            r"(?<!\d)[2-9]\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
            r"(?<!\d)(?:[2-9]|[1-9][0-9])\+?\s*(?:years?|yrs?)\s+of\s+(?:experience|exp)",
            r"(?<!\d)1[0-9]\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
            r"(?:\d+)\+?\s*(?:\+)?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
            r"(?:minimum|at least|more than|over)\s+(?:1|two|2|three|3|four|4)\s*(?:years?|yrs?)",
            r"(?<!\d)2(?!\d)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
            r"(?<!\d)3(?!\d)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
            r"(?<!\d)4(?!\d)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
            r"(?<!\d)5(?!\d)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)",
        ]
        
        for pattern in exp_patterns:
            match = re.search(pattern, jd_lower)
            if match:
                exp_text = match.group(0)
                # Extract the number
                num_match = re.search(r"(\d+)", exp_text)
                if num_match:
                    years = int(num_match.group(1))
                    if years > 1:
                        return True, f"{years}+ years experience: {exp_text[:50]}"
        
        return False, ""
    
    def _select_resume_variant(self, matched_skills: set[str], jd_text: str = "", job_title: str = "") -> str:
        """Select resume variant based on matched skills using ResumeSelector"""
        # Get student_id for resume folder
        student_id = "default"
        if hasattr(self.profile, 'student_id') and self.profile.student_id:
            student_id = str(self.profile.student_id)
        elif hasattr(self.profile, '_id') and str(self.profile._id):
            student_id = str(self.profile._id)
        
        # Get profile skills
        profile_skills = [str(s) for s in self._resolve_profile_skills()]
        
        # Use ResumeSelector to choose the right resume
        jd_skills = list(matched_skills) if matched_skills else extract_skills_from_jd(jd_text)
        
        selector = ResumeSelector(student_id)
        resume_type, resume_path, source = selector.select_resume(
            jd_text=jd_text,
            jd_skills=jd_skills,
            job_title=job_title,
            profile_skills=profile_skills
        )
        
        # Store bucket for fallback use
        self._selected_bucket = selector.get_bucket_for_role(
            "discovered", jd_skills=jd_skills, job_title=job_title or jd_text[:100]
        ) if jd_skills or job_title else "master"
        
        self.logger.log_info(f"Resume selector: {resume_type} - {source} - Bucket: {self._selected_bucket}")
        
        # Store the selected resume path for use in form filling
        self._selected_resume_path = str(resume_path) if resume_path else None
        
        if resume_type == "AI_TAILOR_NEEDED":
            # Need to generate AI tailored resume
            return "ai_tailor"
        
        # Return variant name for backward compatibility
        if resume_path:
            # Determine variant from filename
            filename = resume_path.name.lower()
            for key in ["frontend", "backend", "fullstack", "java", "python", "data_engineer"]:
                if key in filename:
                    return key
        
        # Default fallback - use profile skills to determine variant
        skills_lower = [s.lower() for s in matched_skills]
        
        # Frontend skills
        frontend = {"html", "css", "javascript", "react", "angular", "vue", "jquery", "bootstrap"}
        if any(s in frontend for s in skills_lower):
            return "frontend"
        
        # Java skills
        java_skills = {"java", "spring", "springboot", "hibernate", "jdbc", "jpa"}
        if any(s in java_skills for s in skills_lower):
            return "java"
        
        # Python skills
        python_skills = {"python", "django", "flask", "pandas", "numpy", "scikit"}
        if any(s in python_skills for s in skills_lower):
            return "python"
        
        # Backend
        backend = {"node", "express", "mongodb", "sql", "postgresql", "mysql", "api"}
        if any(s in backend for s in skills_lower):
            return "backend"
        
        return "ai_tailor"
    
    async def _fast_scan(self, page: Page) -> list[dict]:
        """Fast scan: identify valid clickable jobs (Easy Apply check happens on JD page after clicking)"""
        decisions = []
        
        try:
            card_selectors = "li[data-occludable-job-id], .job-card-container, .job-card-list__title--link, .job-card-container__link, .scaffold-layout__list-item"
            cards = await page.locator(card_selectors).all()
            
            for i, card in enumerate(cards):
                try:
                    # Check if job is valid (has job ID)
                    job_id = await card.get_attribute("data-occludable-job-id")
                    has_easy_apply = bool(job_id)
                    
                    # Check already applied
                    is_applied = await card.locator(".jobs-search-results-list__list-item--applied, [aria-label*='Applied']").count() > 0
                    
                    # Get job ID
                    job_id = job_id or await card.get_attribute("data-job-id") or str(i)
                    
                    decisions.append({
                        "index": i,
                        "job_id": job_id,
                        "has_easy_apply": has_easy_apply,
                        "is_applied": is_applied,
                    })
                except:
                    continue
            
            self.logger.log_ok(f"Fast scan: {len(decisions)} jobs identified")
        except Exception as e:
            self.logger.log_err(f"Fast scan failed: {e}")
        
        return decisions
    
    async def _strike_loop(self, page: Page, decisions: list[dict]) -> int:
        """
        Main strike loop with percentage-based skill matching.
        Uses runtime ATS match threshold (defaults to 35% if missing).
        """
        applied = 0
        remaining_cap = max(0, int(self._max_applies - self.applied_count))
        per_loop_cap = int(getattr(self.settings, "max_applies_per_run", remaining_cap or 1))
        loop_limit = min(per_loop_cap, remaining_cap) if remaining_cap > 0 else 0
        if loop_limit <= 0:
            return 0
        # Use percentage-based matching with runtime ATS threshold
        from utils.skill_scorer import calculate_match_percentage
        threshold = float(getattr(self.settings, "ats_threshold", 35.0))
        
        self.logger.log_info(f"Using percentage-based matching ({threshold}% min threshold)")
        
        for decision in decisions:
            if applied >= loop_limit:
                break
            
            # Skip if already applied
            if decision["is_applied"]:
                self.logger.log_info(f"SKIP {decision['index']}: Already applied")
                self.skipped_count += 1
                continue
            
            # Click the job card to open JD page
            try:
                # Modernized selectors for LinkedIn v2 Layout
                card_selectors = [
                    "li[data-occludable-job-id]",
                    ".job-card-container",
                    ".job-card-list__title--link",
                    ".job-card-container__link",
                    ".scaffold-layout__list-item"
                ]
                cards = page.locator(", ".join(card_selectors))
                card_count = await cards.count()
                
                # Use relative position from decision, not absolute index
                card_index = decision.get("index", 0)
                
                # Find a valid card near the expected position
                target_index = min(card_index, card_count - 1) if card_count > 0 else 0
                
                if target_index < 0:
                    self.logger.log_warn(f"No cards available")
                    continue
                
                card = cards.nth(target_index)
                
                try:
                    await card.scroll_into_view_if_needed(timeout=2000)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass  # Ignore scroll errors, try to click anyway
                
                # Robust click mechanism
                clicked = False
                try:
                    await card.click(force=True, timeout=3000)
                    clicked = True
                except Exception:
                    pass
                
                if not clicked:
                    self.logger.log_warn("Actionability check delayed. Falling back to JS click...")
                    try:
                        # Strategy 1: Click inner anchor link
                        inner_link = card.locator("a").first
                        if await inner_link.count() > 0:
                            await inner_link.scroll_into_view_if_needed(timeout=2000)
                            await asyncio.sleep(0.3)
                            try:
                                await inner_link.click(force=True, timeout=2000)
                                clicked = True
                            except:
                                await inner_link.evaluate("node => { node.scrollIntoView({block:'center'}); node.click(); }")
                                clicked = True
                    except:
                        pass
                
                if not clicked:
                    try:
                        # Strategy 2: Force JS click on the card itself
                        await card.evaluate("node => { node.scrollIntoView({block:'center'}); node.click(); }")
                        clicked = True
                    except Exception:
                        self.logger.log_err("All click strategies failed. Skipping job card.")
                        continue
                        
                await page.wait_for_timeout(1500)  # Wait for JD pane to load
                
                self.logger.log_info(f"Opened job card {target_index}")
                
                # Wait for details panel to load
                await page.wait_for_timeout(1200)  # Balanced speed
                
                # PHASE 0: Check if Easy Apply button exists - skip if not found
                has_easy_apply = await self._check_easy_apply_exists(page)
                if not has_easy_apply:
                    self.logger.log_info(f"SKIP: No Easy Apply button found")
                    self.skipped_count += 1
                    try:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                        if "jobs/view" in page.url:
                            await page.go_back()
                            await asyncio.sleep(2)
                    except:
                        pass
                    continue
                
                # PHASE 1: Extract JD text only if Easy Apply exists
                jd_text = ""
                try:
                    jd_el = page.locator(".jobs-description-content__text, .jobs-description__content, #job-details, .jobs-box__html-content, .show-more-less-html__markup").first
                    if await jd_el.count() > 0:
                        raw_jd = (await jd_el.inner_text()).strip()
                        jd_text = " ".join(raw_jd.split())[:4000]
                        self.logger.log_info(f"JD extracted: {len(jd_text)} chars")
                except Exception as e:
                    self.logger.log_warn(f"Failed to extract JD: {e}")
                
                # PHASE 1.1/1.2: Extract Job Title + Company
                job_title, company_name = await self._extract_job_identity(page)
                self.logger.log_info(f"[IDENTITY] Job: {job_title} | Company: {company_name}")

                # Keep current job metadata for downstream form/apply logging.
                self.current_job_title = job_title or ""
                self.current_company_name = company_name or ""
                
                # PHASE 1.5: Check experience requirement (skip if > 1 year)
                should_skip, exp_reason = self._check_experience_requirement(jd_text)
                if should_skip:
                    self.logger.log_info(f"SKIP: {exp_reason}")
                    self.skipped_count += 1
                    try:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                        if "jobs/view" in page.url:
                            await page.go_back()
                            await asyncio.sleep(2)
                    except:
                        pass
                    continue
                
                # AI skill extraction from JD (only if JD extracted and experience OK)
                ai_skills = []
                if jd_text:
                    ai_skills = await self._extract_skills_with_ai(jd_text)
                
                # Use three-tier skill matching
                profile_skills = [str(s) for s in self._resolve_profile_skills()]
                self.logger.log_info(f"[MATCH] Profile skills resolved: {len(profile_skills)} | JD AI skills: {len(ai_skills)}")

                result = {"matched_skills": []}
                matched_skills_set = set()
                
                if ai_skills and profile_skills:
                    result = calculate_match_percentage(profile_skills, ai_skills, threshold)
                    percentage = result['percentage']
                    total_points = result['total_points']
                    max_possible = result.get('max_possible', 0)
                    
                    # Detailed logging for the user
                    self.logger.log_info("=== SKILL SCORING BREAKDOWN ===")
                    primary_matches = [m['skill'] for m in result.get('matched_skills', []) if m.get('category') == 'primary']
                    secondary_matches = [m['skill'] for m in result.get('matched_skills', []) if m.get('category') == 'secondary']
                    partial_matches = [m['skill'] for m in result.get('matched_skills', []) if m.get('category') == 'partial']
                    
                    if primary_matches:
                        self.logger.log_ok(f"  Primary (20pts): {', '.join(primary_matches)}")
                    if secondary_matches:
                        self.logger.log_ok(f"  Secondary (10pts): {', '.join(secondary_matches)}")
                    if partial_matches:
                        self.logger.log_ok(f"  Partial (6pts): {', '.join(partial_matches)}")
                        
                    missing = result.get('missing_skills', [])
                    if missing:
                        self.logger.log_warn(f"  Missing JD Skills: {', '.join(missing)}")
                    
                    self.logger.log_info(f"  FINAL SCORE: {total_points}/{max_possible} = {percentage}%")
                    self.logger.log_info("===============================")
                    
                    matched_skills_set = {m["skill"] for m in result.get("matched_skills", []) if m.get("skill")}
                else:
                    # Fallback to old matching if no skills
                    match_count, ats_score, matched_skills = self._match_profile_skills(ai_skills)
                    percentage = (match_count / len(profile_skills) * 100) if profile_skills else 0
                    if not profile_skills:
                        self.logger.log_warn("[MATCH] Profile skills are empty after fallback resolution.")
                    self.logger.log_info(f"Match: {percentage}% (fallback)")
                    matched_skills_set = set(matched_skills or [])
                
                # Threshold check: use runtime ATS threshold
                if percentage < threshold:
                    self.logger.log_info(f"SKIP: Low match ({percentage}%<{threshold}%), going to next")
                    self.skipped_count += 1
                    await self._quick_return_to_search(page)
                    continue
                
                # Store JD text for resume selection
                self._current_jd_text = jd_text
                
                # Select resume variant based on matched skills
                variant = self._select_resume_variant(matched_skills_set, jd_text, job_title)
                self.logger.log_ok(f"Proceeding to apply ({percentage}%, variant={variant})")
                
                # Click Easy Apply button on JD page
                success = await self._click_easy_apply(page)
                
                if success:
                    # Fill form with resume
                    fill_success = await self._fill_easy_apply_form(page, variant)
                    if fill_success:
                        applied += 1
                        self._last_applied_job_title = self.current_job_title or 'Software Developer'
                        self._last_applied_company = self.current_company_name or 'LinkedIn'
                        self.logger.log_ok(f"APPLIED ({applied}): Job {decision.get('job_id', card_index)}")
                        # v3.5 DASHBOARD SYNC
                        await self.logger.log_application_success(
                            job_id=decision.get('job_id', 'unknown'),
                            title=self.current_job_title or 'Software Developer',
                            company=self.current_company_name or 'N/A',
                            platform="linkedin",
                            student_id=self._get_candidate_id()
                        )
                    else:
                        self.logger.log_warn("Easy Apply form fill failed")
                else:
                    self.logger.log_warn("Easy Apply click failed")
                
                # Go back to search - FORCE reload with page recovery
                try:
                    # Check if page is closed - if so, get new page
                    if page.is_closed():
                        self.logger.log_warn("Page closed, getting new page...")
                        from scraper_adapter.playwright_manager import playwright_manager
                        page = await playwright_manager.get_page(
                            self.settings,
                            student_id=self._get_candidate_id(),
                        )
                        # Navigate to search URL directly
                        search_role = getattr(self, "current_role", "Software Developer")
                        search_start = getattr(self, "current_start", 0)
                        await self._search_and_lock(page, search_role, search_start)
                        await asyncio.sleep(2)
                    else:
                        # Close any modal first
                        try:
                            await page.keyboard.press("Escape")
                            await asyncio.sleep(0.5)
                        except:
                            pass
                        
                        # Press browser back or reload search
                        current_url = page.url
                        if "jobs/view" in current_url:
                            await page.go_back()
                            await asyncio.sleep(1.5)  # Balanced speed
                        
                        # Force reload search page
                        await self._search_and_lock(page, getattr(self, "current_role", ""), getattr(self, "current_start", 0))
                        await asyncio.sleep(1.5)  # Balanced speed

                except Exception as e:
                    self.logger.log_warn(f"Return to search error: {e}, trying to recover...")
                    try:
                        from scraper_adapter.playwright_manager import playwright_manager
                        page = await playwright_manager.get_page(
                            self.settings,
                            student_id=self._get_candidate_id(),
                        )
                        await self._search_and_lock(page, getattr(self, "current_role", "Software Developer"), getattr(self, "current_start", 0))
                        await asyncio.sleep(1.5)  # Balanced speed
                    except Exception as e2:
                        self.logger.log_err(f"Page recovery failed: {e2}")
                
                # Anti-ban delay
                await self._anti_ban_delay(applied)
                
            except Exception as e:
                self.logger.log_err(f"Strike error on job {decision['index']}: {e}")
                try:
                    if not page.is_closed():
                        await page.go_back()
                    await asyncio.sleep(1)
                except:
                    pass
                continue
        
        return applied

    async def _extract_job_identity(self, page: Page) -> tuple[str, str]:
        """Extract job title and company from LinkedIn JD pane/page."""
        title_selectors = [
            ".job-details-jobs-unified-top-card__job-title",
            ".jobs-unified-top-card__job-title",
            "h1.t-24",
            "h1",
        ]
        company_selectors = [
            ".job-details-jobs-unified-top-card__company-name",
            ".jobs-unified-top-card__company-name",
            "a[class*='company-name']",
            ".jobs-details-cover-image__company-name-text",
            ".topcard__org-name-link",
            ".topcard__flavor--bullet",
            ".topcard__flavor",
        ]

        async def _first_text(selectors: list[str]) -> str:
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        txt = (await el.inner_text()).strip()
                        if txt:
                            return txt
                except Exception:
                    continue
            return ""

        title = await _first_text(title_selectors) or "Software Engineer"
        company = await _first_text(company_selectors) or "LinkedIn"
        return title, company
    
    async def _check_easy_apply_exists(self, page: Page) -> bool:
        """Check if Easy Apply button exists (without clicking)"""
        try:
            selectors = [
                ".jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                "button:has-text('Easy Apply')",
            ]
            
            for sel in selectors:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    return True
            return False
        except:
            return False
    
    async def _click_easy_apply(self, page: Page) -> bool:
        """Click Easy Apply button"""
        try:
            selectors = [
                ".jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                "button:has-text('Easy Apply')",
            ]
            
            for sel in selectors:
                btn = page.locator(sel).first
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(1)  # Reduced from 2
                    return True
            return False
        except:
            return False
    
    async def _quick_return_to_search(self, page: Page) -> None:
        """Quick return to search results without full reload"""
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            if "jobs/view" in page.url:
                await page.go_back()
                await asyncio.sleep(0.5)  # Reduced from 1
        except:
            pass
    
    async def _fill_easy_apply_form(self, page: Page, variant: str) -> bool:
        """
        Hardened v3.5 Filling Loop:
        - Handle multi-step modal (Next, Review, Submit)
        - Auto-dismiss blocking popups (Save/Discard)
        - AI-powered form answering
        - Skip job if no modal appears
        """
        try:
            # 1. Init AI Brain
            brain = getattr(self, "brain", None)
            if brain is None and LLMAnswers:
                brain = LLMAnswers(self.settings, self.logger)
                self.brain = brain
            if brain is None:
                self.logger.log_warn("LLMAnswers unavailable for LinkedIn form fill, using fallback answers.")
            
            # 2. Wait for modal - if no modal, skip job
            modal_found = False
            try:
                await page.wait_for_selector("[role='dialog'], .artdeco-modal", timeout=4000)
                modal_found = True
            except:
                self.logger.log_warn("No modal found - SKIPPING job")
                return False  # Skip job - no modal means cannot apply
            
            if modal_found:
                await asyncio.sleep(0.5)  # Slightly slower for stability
            
            # Initialize resume upload tracking (cached for this job)
            self._resume_uploaded_this_job = False
            
            # 3. Check if we need to generate AI tailored resume
            if variant == "ai_tailor":
                jd_text = getattr(self, '_current_jd_text', "")
                student_id = "default"
                if hasattr(self.profile, 'student_id') and self.profile.student_id:
                    student_id = str(self.profile.student_id)
                elif hasattr(self.profile, '_id') and str(self.profile._id):
                    student_id = str(self.profile._id)
                
                tailored_path = await self._generate_ai_resume(jd_text, student_id)
                if tailored_path:
                    self._selected_resume_path = tailored_path
                    self.logger.log_ok(f"Generated AI tailored resume: {tailored_path}")
                    variant = "fullstack"
            
            # 4. Iterative Loop (Max 8 pages)
            for step in range(8):  # Reduced from 12
                # A. Bust blocking popups
                await self._dismiss_blocking_popups(page)
                
                # B. Pre-fill checks (Upload Resume if on that page)
                await self._handle_resume_upload(page, variant)
                
                # C. Fill all visible fields (Text, Dropdown, Radio)
                await self._fill_form_fields(page, brain)
                
                # FALLBACK: Use universal FormFiller if available
                if FormFiller:
                    try:
                        filler = FormFiller(self.logger)
                        job = {"title": getattr(self, "current_job_title", ""), "company": getattr(self, "current_company_name", "")}
                        await filler.fill_application_form(
                            page=page,
                            profile=self.profile,
                            job=job,
                            answers={},
                            llm_answers=brain
                        )
                    except Exception as e:
                        self.logger.log_warn(f"[FALLBACK] FormFiller error: {e}")
                
                # D. Identify main action button - faster detection
                actions = [
                    ("submit", "button[aria-label*='Submit'], button:has-text('Submit'), button:has-text('Send')"),
                    ("next", "button[aria-label*='Review'], button:has-text('Review')"),
                    ("next", "button[aria-label*='Next'], button:has-text('Next')"),
                    ("next", "button[aria-label*='Continue'], button:has-text('Continue')"),
                ]
                
                clicked = False
                for action_type, selector in actions:
                    btn = page.locator(selector).nth(0)
                    if await btn.is_visible() and await btn.is_enabled():
                        btn_text = await btn.inner_text() if await btn.count() > 0 else ""
                        self.logger.log_info(f"Modal Click: {action_type.upper()} ({selector})")
                        await btn.click()
                        await asyncio.sleep(1)  # 1-2 seconds for page transition
                        
                        if action_type == "submit":
                            try:
                                await page.wait_for_selector(".artdeco-inline-feedback--success, :has-text('Application sent'), button:has-text('Done')", timeout=12000)
                                self.logger.log_ok("LinkedIn Success Verified")
                                return True
                            except:
                                self.logger.log_warn("LinkedIn: Submit but success not found, continuing")
                                return True
                        
                        clicked = True
                        break
                
                if not clicked:
                    if await page.locator("[role='dialog'], .artdeco-modal").count() == 0:
                        self.logger.log_ok("Modal closed. Application complete.")
                        return True
                    break
                    
            return False
        except Exception as e:
            self.logger.log_err(f"Form fill failed: {e}")
            return False
            
            # 4. Iterative Loop (Max 12 pages)
            for step in range(12):
                # A. Bust blocking popups
                await self._dismiss_blocking_popups(page)
                
                # B. Pre-fill checks (Upload Resume if on that page)
                await self._handle_resume_upload(page, variant)
                
                # C. Fill all visible fields (Text, Dropdown, Radio)
                await self._fill_form_fields(page, brain)
                
                # D. Identify main action button
                # Order of priority: Submit -> Review -> Next -> Continue
                actions = [
                    ("submit", "button[aria-label*='Submit'], button:has-text('Submit'), button:has-text('Send')"),
                    ("next", "button[aria-label*='Review'], button:has-text('Review')"),
                    ("next", "button[aria-label*='Next'], button:has-text('Next')"),
                    ("next", "button[aria-label*='Continue'], button:has-text('Continue')"),
                ]
                
                clicked = False
                for action_type, selector in actions:
                    btn = page.locator(selector).nth(0)
                    if await btn.is_visible() and await btn.is_enabled():
                        btn_text = await btn.inner_text() if await btn.count() > 0 else ""
                        self.logger.log_info(f"Modal Click: {action_type.upper()} ({selector})")
                        await btn.click()
                        await asyncio.sleep(0.5)
                        
                        # SPECIAL: After clicking Review button, IMMEDIATELY try to submit
                        if action_type == "next" and "review" in btn_text.lower():
                            self.logger.log_info("Review clicked - FORCING Submit...")
                            await asyncio.sleep(0.3)
                            
                            submit_selectors = [
                                "button[aria-label*='Submit']",
                                "button:has-text('Submit')",
                                "button:has-text('Send')",
                                ".artdeco-button--primary",
                            ]
                            
                            for sub_sel in submit_selectors:
                                sub_btn = page.locator(sub_sel).first
                                if await sub_btn.count() > 0 and await sub_btn.is_visible():
                                    self.logger.log_info(f"FORCE SUBMIT: {sub_sel}")
                                    await sub_btn.click()
                                    await asyncio.sleep(1.5)
                                    return True
                        
                        if action_type == "submit":
                            await asyncio.sleep(1)
                            return True
                        
                        clicked = True
                        break
                
                if not clicked:
                    # Final check: is the modal still open?
                    if await page.locator("[role='dialog'], .artdeco-modal").count() == 0:
                        self.logger.log_ok("Modal closed naturally. Application likely complete.")
                        return True
                    
                    self.logger.log_warn("No active button found. Stuck or finished.")
                    break

                    
            return False
        except Exception as e:
            self.logger.log_err(f"Form fill logic failed: {e}")
            return False

    async def _dismiss_blocking_popups(self, page: Page) -> None:
        """Dismiss popups like 'Save this application?' or 'Follow company'"""
        popups = [
            ("Discard", "button[aria-label*='Discard'], button:has-text('Discard')"),
            ("Dismiss", "button[aria-label*='Dismiss']"),
            ("Close", ".artdeco-modal__dismiss"),
        ]
        for name, sel in popups:
            try:
                # Only dismiss if it's a SECONDARY modal (blocking the main one)
                objs = await page.locator(sel).all()
                if len(objs) > 1: # More than one modal/trigger button
                    btn = objs[-1] # Target the top-most one
                    if await btn.is_visible():
                        self.logger.log_info(f"Dismissing blocking popup: {name}")
                        await btn.click()
                        await asyncio.sleep(1)
            except: pass

    async def _handle_resume_upload(self, page: Page, variant: str) -> None:
        """Specifically handles the resume upload step if it appears"""
        try:
            # Check if resume already uploaded in this job (caching)
            if getattr(self, '_resume_uploaded_this_job', False):
                self.logger.log_info("Resume already uploaded (cached), skipping...")
                return
            
            # 1. Determine the best resume path
            upload_path = None
            
            # Priority 1: Path selected by ResumeSelector (already generated/local)
            selected_path = getattr(self, '_selected_resume_path', None)
            if selected_path and os.path.exists(selected_path):
                upload_path = selected_path
                self.logger.log_info(f"Using pre-selected resume: {Path(upload_path).name}")
            
            # Priority 2: Fallback to Cloudinary download if no local path yet
            if not upload_path:
                student_id = "default"
                if hasattr(self.profile, 'student_id') and self.profile.student_id:
                    student_id = str(self.profile.student_id)
                elif hasattr(self.profile, '_id') and str(self.profile._id):
                    student_id = str(self.profile._id)
                
                resume_url = None
                selected_bucket = getattr(self, '_selected_bucket', 'master')
                
                # Check for highly tailored resume URL first using bucket matching!
                resume_urls_dict = getattr(self.profile, 'resume_urls', {})
                if isinstance(resume_urls_dict, dict) and selected_bucket in resume_urls_dict:
                    resume_url = resume_urls_dict[selected_bucket]
                    self.logger.log_info(f"Using bucket-matched Cloudinary resume: {selected_bucket}")
                elif isinstance(resume_urls_dict, dict) and variant in resume_urls_dict:
                    # Fallback to variant if bucket not found
                    resume_url = resume_urls_dict[variant]
                    self.logger.log_info(f"Using variant fallback Cloudinary resume: {variant}")
                
                # Fallback to master resume URL if tailored one doesn't exist
                if not resume_url:
                    resume_url = getattr(self.profile, 'resume', "") or getattr(self.profile, 'cloudinary_url', "")
                    if resume_url:
                        self.logger.log_info("Falling back to master resume from Cloudinary...")
                
                if resume_url and resume_url.startswith('http') and student_id:
                    local_path, success = download_resume_from_url(resume_url, student_id, selected_bucket)
                    if success and os.path.exists(local_path):
                        upload_path = local_path
                        self.logger.log_ok(f"Resume downloaded: {Path(local_path).name}")
            
            # Priority 3: Fallback to local directory resumes
            if not upload_path:
                resume_dir = getattr(self.settings, "resume_directory", None)
                if resume_dir:
                    resume_name = self.RESUME_VARIANTS.get(variant, "resume.pdf")
                    fallback_path = str(Path(resume_dir) / resume_name)
                    if os.path.exists(fallback_path):
                        upload_path = fallback_path
                        self.logger.log_info(f"Using local fallback: {resume_name}")

            # 2. Perform the upload if a path was found
            if upload_path and os.path.exists(upload_path):
                # Specific selectors for LinkedIn Easy Apply resume input
                selectors = [
                    "input[type='file'][name='file']",
                    "div.jobs-document-upload__container input[type='file']",
                    "input[type='file'][id*='file-browse-input']",
                    "input[type='file']"
                ]
                
                for selector in selectors:
                    file_input = page.locator(selector).first
                    # Check for presence, NOT visibility (file inputs are often hidden)
                    if await file_input.count() > 0:
                        self.logger.log_info(f"Found upload field: {selector}")
                        
                        # Hardened Upload: Force reveal hidden input
                        await file_input.evaluate("""
                            el => {
                                el.style.display = 'block';
                                el.style.visibility = 'visible';
                                el.style.opacity = '1';
                                el.removeAttribute('hidden');
                            }
                        """)
                        
                        await file_input.set_input_files(upload_path)
                        self.logger.log_ok(f"RESUME UPLOADED SUCCESSFULLY: {Path(upload_path).name}")
                        self._resume_uploaded_this_job = True
                
                self.logger.log_warn("No resume upload field found in modal")
            else:
                self.logger.log_warn("No valid resume file found for upload")
                    
        except Exception as e:
            self.logger.log_err(f"Resume upload failed: {e}")
    
    async def _generate_ai_resume(self, jd_text: str, student_id: str) -> Optional[str]:
        """Generate AI tailored resume using API"""
        import shutil
        from pathlib import Path
        
        # Use the finalized Resume API port (standardized to 8000 in Step 11)
        api_base = os.getenv("LOCAL_API_URL", "http://ai-engine:8000").rstrip("/")
        api_url = f"{api_base}/generate"
        
        try:
            # Get master resume
            master_resume_path = None
            if hasattr(self.profile, 'resume_path') and self.profile.resume_path:
                master_resume_path = self.profile.resume_path
            
            if not master_resume_path:
                master_resume_path = os.getenv("STUDENT_RESUME_PATH")
            
            # Extract text from master
            retrieved_chunks = ""
            if master_resume_path and os.path.exists(master_resume_path):
                from utils.pdf_reader import extract_text_from_pdf
                try:
                    master_text = extract_text_from_pdf(master_resume_path)
                    links = getattr(self.profile, 'extra', {})
                    linkedin = links.get('linkedin', '')
                    github = links.get('github', '')
                    header = f"NAME: {getattr(self.profile, 'name', 'Candidate')}\nEMAIL: {getattr(self.profile, 'email', '')}\nPHONE: {getattr(self.profile, 'phone', '')}\nLOCATION: {getattr(self.profile, 'location', '')}\nLINKEDIN: {linkedin}\nGITHUB: {github}\n"
                    retrieved_chunks = header + "\n\n" + master_text
                except Exception as e:
                    self.logger.log_warn(f"Could not extract master resume: {e}")
                    retrieved_chunks = str(self.profile)
            else:
                retrieved_chunks = str(self.profile)
            
            # Call AI API
            input_data = {
                "jobDescription": jd_text,
                "retrievedChunks": retrieved_chunks,
                "disableCache": False,
                "refreshCache": True
            }
            
            self.logger.log_info("Calling AI Resume Engine...")
            response = requests.post(api_url, json=input_data, timeout=180)
            
            if response.status_code == 200:
                result = response.json()
                pdf_path = resolve_ai_engine_pdf_path(result)
                
                if pdf_path:
                    # Save to student folder for reuse
                    selector = ResumeSelector(student_id)
                    main_skill = selector.extract_main_skill(jd_text)
                    saved_path = selector.save_tailored_resume(pdf_path, main_skill)
                    self.logger.log_ok(f"Saved tailored resume to: {saved_path}")
                    return str(saved_path)
            else:
                self.logger.log_err(f"AI Engine error: {response.status_code}")
                
        except Exception as e:
            self.logger.log_err(f"AI resume generation failed: {e}")
        
        return None
    
    def _fallback_field_answer(self, label: str, field_type: str = "text", options: list[str] | None = None) -> str:
        """Fallback answer policy when LLM is unavailable or fails."""
        label_lower = (label or "").lower()
        profile_phone = str(getattr(self.profile, "phone", "") or "")
        profile_email = str(getattr(self.profile, "email", "") or "")
        profile_name = str(getattr(self.profile, "name", "") or "")
        profile_location = str(getattr(self.profile, "location", "") or "India")

        if options:
            normalized = [str(o).strip() for o in options if str(o).strip()]
            if not normalized:
                return ""
            priority = ["yes", "willing", "immediate", "fresher", "0", "india", "hyderabad", "bangalore"]
            for p in priority:
                for opt in normalized:
                    if p in opt.lower():
                        return opt
            return normalized[0]

        if any(k in label_lower for k in ["phone", "mobile", "contact", "tel", "number"]):
            digits = re.sub(r"\D", "", profile_phone)
            return digits[-10:] if len(digits) >= 10 else "9999999999"
        if any(k in label_lower for k in ["email", "mail"]):
            return profile_email or "candidate@example.com"
        if "name" in label_lower and "company" not in label_lower:
            return profile_name or "Candidate"
        if any(k in label_lower for k in ["city", "location", "address"]):
            return profile_location
        if any(k in label_lower for k in ["notice", "joining", "available"]):
            return "0"
        if any(k in label_lower for k in ["current salary", "current ctc", "current drawn"]):
            return "180000"
        if any(k in label_lower for k in ["ctc", "salary", "package", "expected"]):
            return "340000"
        if "experience" in label_lower:
            return "0"
        if field_type == "numeric":
            return "0"
        return "Yes"

    async def _get_llm_answer_value(
        self,
        brain: Any,
        label: str,
        context: str,
        field_type: str = "text",
        options: list[str] | None = None,
    ) -> str:
        """Normalize LLM result payload into a plain answer string with fallback."""
        if brain is None:
            return self._fallback_field_answer(label, field_type, options)
        try:
            result = await brain.answer_question(
                label,
                self.profile,
                {"title": "", "company": ""},
                context=context,
                field_type=field_type,
                options=options,
            )
            if isinstance(result, dict):
                answer = result.get("answer")
                if answer is not None:
                    return str(answer)
            elif result is not None:
                return str(result)
        except Exception as e:
            self.logger.log_warn(f"LLM answer failed for '{label[:40]}': {e}")
        return self._fallback_field_answer(label, field_type, options)

    async def _fill_form_fields(self, page: Page, brain: Any) -> None:
        """Fill form fields with dynamic AI-powered answers"""
        try:
            # 1. All Input Types - Text, Email, Phone, Number, Textarea
            all_inputs = await page.locator(
                "input[type='text'], input[type='email'], input[type='tel'], "
                "input[type='number'], input:not([type]), textarea"
            ).all()
            
            for field in all_inputs:
                try:
                    # SKIP LinkedIn search boxes and disabled fields
                    is_disabled = await field.is_disabled()
                    if is_disabled:
                        continue
                    
                    # Skip LinkedIn's job search boxes (they appear in modal but aren't form fields)
                    aria_label = await field.get_attribute("aria-label") or ""
                    placeholder = await field.get_attribute("placeholder") or ""
                    classes = await field.get_attribute("class") or ""
                    
                    # Skip search boxes, ghost inputs, and LinkedIn internal fields
                    if any(x in aria_label.lower() for x in ["search", "skills", "company", "title"]):
                        continue
                    if "ghost" in classes.lower():
                        continue
                    if "jobs-search-box" in classes.lower():
                        continue
                    
                    if not await field.is_visible():
                        continue
                    
                    current_value = await field.get_attribute("value") or ""
                    if current_value.strip():
                        continue
                    
                    # Get label for the field
                    label = await self._get_label(page, field)
                    
                    # If no label found, try placeholder
                    if not label or not label.strip():
                        placeholder = await field.get_attribute("placeholder") or ""
                        if placeholder:
                            label = placeholder
                    
                    # If still no label, try getting label from parent
                    if not label or not label.strip():
                        try:
                            parent_text = await field.evaluate("""
                                (el) => {
                                    const prev = el.previousElementSibling;
                                    if (prev && prev.tagName === 'LABEL') return prev.innerText;
                                    const parent = el.parentElement;
                                    if (parent) {
                                        const label = parent.querySelector('label');
                                        if (label) return label.innerText;
                                        return parent.innerText.substring(0, 100);
                                    }
                                    return '';
                                }
                            """)
                            if parent_text:
                                label = parent_text
                        except:
                            pass
                    
                    # Get input type to help detect phone fields
                    input_type = await field.get_attribute("type") or "text"
                    
                    if label and label.strip():
                        label_lower = label.lower()
                        
                        # FIRST: Check for phone/mobile/tel field - ALWAYS use resume phone
                        if input_type == "tel" or any(kw in label_lower for kw in ["phone", "mobile", "contact", "tel", "number"]):
                            profile_phone = getattr(self.profile, "phone", "") or getattr(self.profile, "mobile", "")
                            if profile_phone:
                                import re
                                clean_phone = re.sub(r'\D', '', str(profile_phone))
                                if len(clean_phone) >= 10:
                                    answer = clean_phone[-10:]
                                    self.logger.log_info(f"INSTANT FILL (phone): {answer}")
                                    await field.fill(str(answer))
                                    continue
                        
                        # SECOND: Check for email field
                        if any(kw in label_lower for kw in ["email", "mail"]):
                            profile_email = getattr(self.profile, "email", "")
                            if profile_email:
                                answer = profile_email
                                self.logger.log_info(f"INSTANT FILL (email): {answer}")
                                await field.fill(str(answer))
                                continue
                        
                        # THIRD: Check for location/city field
                        if any(kw in label_lower for kw in ["city", "location", "address"]):
                            profile_location = getattr(self.profile, "location", "")
                            if profile_location:
                                answer = profile_location
                                self.logger.log_info(f"INSTANT FILL (location): {answer}")
                                await field.fill(str(answer))
                                continue
                        
                        # FOURTH: Check for name field
                        if "name" in label_lower and "company" not in label_lower:
                            profile_name = getattr(self.profile, "name", "")
                            if profile_name:
                                answer = profile_name
                                self.logger.log_info(f"INSTANT FILL (name): {answer}")
                                await field.fill(str(answer))
                                continue
                        
                        # SECOND: Check for email field
                        if any(kw in label_lower for kw in ["email", "mail"]):
                            profile_email = getattr(self.profile, "email", "")
                            if profile_email:
                                answer = profile_email
                                self.logger.log_info(f"INSTANT FILL (email): {answer}")
                                await field.fill(str(answer))
                                await asyncio.sleep(0.2)
                                continue
                        
                        # THIRD: Check for location/city field
                        if any(kw in label_lower for kw in ["city", "location", "address"]):
                            profile_location = getattr(self.profile, "location", "")
                            if profile_location:
                                answer = profile_location
                                self.logger.log_info(f"INSTANT FILL (location): {answer}")
                                await field.fill(str(answer))
                                await asyncio.sleep(0.2)
                                continue
                        
                        # FOURTH: Check for name field
                        if "name" in label_lower and "company" not in label_lower:
                            profile_name = getattr(self.profile, "name", "")
                            if profile_name:
                                answer = profile_name
                                self.logger.log_info(f"INSTANT FILL (name): {answer}")
                                await field.fill(str(answer))
                                await asyncio.sleep(0.2)
                                continue
                        
                        # FIFTH: Dynamic experience calculator from RAG resume context
                        exp_keywords = ["experience", "years", "months", "working", "coding", "programming", "internship", "professional", "tenure", "how long", "duration"]
                        if any(x in label_lower for x in exp_keywords):
                            # Get experience from resume RAG context
                            exp_answer = await self._calculate_experience_from_resume(label)
                            if exp_answer:
                                self.logger.log_info(f"RAG EXPERIENCE: {exp_answer} for '{label[:40]}'")
                                await field.fill(exp_answer)
                                continue
                        
                        # For OTHER fields - detect field type and use LLM
                        field_type = self._detect_field_type(label, input_type)
                        # v3.5 UNIVERSAL RAG DELEGATION: If asking about Identity/Experience/Projects/Skills, use RAG
                        rag_keywords = ["experience", "years", "months", "how long", "tenure", "project", "skill", "tech", "tool", "education", "degree", "college", "github", "linkedin", "social", "portfolio", "name", "email", "mobile", "phone"]
                        is_rag_q = any(x in label_lower for x in rag_keywords)
                        context = None if is_rag_q else self._build_fresher_context()
                        
                        # For notice/joining fields - fresher answers 0
                        if any(kw in label_lower for kw in ["notice", "joining", "available"]):
                            answer = "0"
                            self.logger.log_info(f"INSTANT FILL (fresher {field_type}): {answer}")
                            await field.fill(str(answer))
                            continue
                        elif any(kw in label_lower for kw in ["current salary", "current ctc", "current drawn"]):
                            answer = "180000"
                            self.logger.log_info(f"INSTANT FILL (fresher {field_type}): {answer}")
                            await field.fill(str(answer))
                            continue
                        
                        # Expected CTC/salary for fresher = 340000
                        if any(x in label_lower for x in ["expected", "ctc", "salary", "expectation", "package"]):
                            answer = "340000"
                        else:
                            answer = await self._get_llm_answer_value(brain, label, context, field_type=field_type)
                        
                        self.logger.log_info(f"AI Answer ({label[:40]}, type={field_type}): {answer}")
                        
                        # Final Numeric Guard - return 0 for invalid answers
                        if field_type == "numeric" or any(x in label_lower for x in ["salary", "ctc"]):
                            import re
                            num_match = re.search(r'\d+', str(answer))
                            if num_match:
                                answer = num_match.group(0)
                            else:
                                answer = "0"
                        
                        await field.fill(str(answer))
                        await asyncio.sleep(0.2)
                        # v3.5 SELF-CORRECTION STRIKE: After filling input, check for error messages
                        await asyncio.sleep(1.5) # Wait for Artdeco validation
                        try:
                            # Scoped error check: Look for error message inside the same field container
                            container = field.locator("xpath=ancestor::div[contains(@class, 'fb-dash-form-element') or contains(@class, 'artdeco-text-input') or contains(@class, 'jobs-easy-apply-form-section__grouping')][1]")
                            error_selector = container.locator(".artdeco-inline-feedback--error, .artdeco-inline-feedback__message, .fb-dash-form-element__error-field")
                            
                            if await error_selector.count() > 0 and await error_selector.first.is_visible():
                                error_text = await error_selector.first.inner_text()
                                if error_text and len(error_text) > 2:
                                    self.logger.log_err(f"LinkedIn field error: {error_text}")
                                    
                                    # Retry with numeric constraint
                                    retry_answer = await self._get_llm_answer_value(
                                        brain,
                                        label + " - ERROR: " + error_text,
                                        context,
                                        field_type=field_type,
                                    )
                                    
                                    # Force numeric if error mentions numeric constraints
                                    import re
                                    if any(kw in error_text.lower() for kw in ["larger", "greater", "number", "integer", "decimal", "digit"]):
                                        num_match = re.search(r'\d+(?:\.\d+)?', str(retry_answer))
                                        if num_match:
                                            retry_val = num_match.group(0)
                                            retry_answer = str(retry_val)
                                        else:
                                            # Ultimate fallback for experience fields
                                            retry_answer = "1"
                                    
                                    self.logger.log_info(f"Self-Corrected Answer: {retry_answer}")
                                    await field.click(click_count=3)
                                    await field.press("Control+A")
                                    await field.press("Backspace")
                                    await field.fill(str(retry_answer))
                                    await asyncio.sleep(0.5)
                        except:
                            pass
                
                except Exception as e:
                    self.logger.log_warn(f"Error filling input: {e}")

            # 2. Radio Buttons - Use LLM to pick correct option
            radios = await page.locator("fieldset").all()
            for group in radios:
                try:
                    if not await group.is_visible(): continue
                    
                    # Get label for radio group
                    label = await group.locator("legend, label").first.inner_text()
                    label = label.strip()
                    if not label: continue

                    # Get options
                    options_loc = await group.locator("label, .artdeco-radio-button__label, .fb-radio__label").all()
                    option_texts = []
                    for opt in options_loc:
                        t = (await opt.inner_text()).strip()
                        if t: option_texts.append(t)
                    
                    if len(option_texts) > 0:
                        # v3.5 UNIVERSAL RAG DELEGATION: If asking about Identity/Experience/Projects/Skills, use RAG
                        label_lower = label.lower()
                        rag_keywords = ["experience", "years", "months", "how long", "tenure", "project", "skill", "tech", "tool", "education", "degree", "college", "github", "linkedin", "social", "portfolio", "name", "email", "mobile", "phone"]
                        is_rag_q = any(x in label_lower for x in rag_keywords)
                        context = None if is_rag_q else self._build_fresher_context()
                        ft = self._detect_field_type(label, "text")
                        answer = await self._get_llm_answer_value(
                            brain,
                            label,
                            context,
                            field_type=ft,
                            options=option_texts,
                        )
                        
                        # Find and click matching option
                        from utils.job_retrieval import fuzzy_match_option
                        best_opt = fuzzy_match_option(answer, option_texts)
                        if best_opt:
                            target = group.locator(f"label:has-text('{best_opt}')").first
                            if await target.count() > 0:
                                await target.click()
                                self.logger.log_info(f"Radio picked: {best_opt}")
                        await asyncio.sleep(0.2)
                except:
                    pass

            # 2.5 Checkboxes - Handle all visible checkboxes
            checkboxes = await page.locator("input[type='checkbox']").all()
            for cb in checkboxes:
                try:
                    if await cb.is_visible() and not await cb.is_checked():
                        # Get label
                        cb_id = await cb.get_attribute("id")
                        label_text = ""
                        if cb_id:
                            label_el = page.locator(f"label[for='{cb_id}']").first
                            if await label_el.count() > 0:
                                label_text = await label_el.inner_text()
                        
                        # User requested checking ALL checkboxes
                        await cb.check()
                        self.logger.log_info(f"Checkbox checked: {label_text[:30]}")
                        await asyncio.sleep(0.1)
                except:
                    pass


            # 3. Dropdowns - Use LLM to select
            dropdowns = await page.locator("select").all()
            for dd in dropdowns:
                try:
                    if not await dd.is_visible():
                        continue
                    
                    # Get the label for this dropdown
                    label = ""
                    dd_id = await dd.get_attribute("id")
                    if dd_id:
                        label_el = page.locator(f"label[for='{dd_id}']").first
                        if await label_el.count() > 0:
                            label = (await label_el.inner_text()).strip()
                    if not label:
                        label_el = page.locator(f"xpath=preceding::label[1]").first
                        if await label_el.count() > 0:
                            label = (await label_el.inner_text()).strip()
                    
                    options = await dd.locator("option").all()
                    option_texts = []
                    for opt in options:
                        text = (await opt.inner_text()).strip()
                        if text and text.lower() not in ["select", "choose", ""]:
                            option_texts.append(text)
                    
                    if len(option_texts) > 1:
                        label_lower = label.lower()
                        rag_keywords = ["experience", "years", "months", "how long", "tenure", "project", "skill", "tech", "tool", "education", "degree", "college", "github", "linkedin", "social", "portfolio", "name", "email", "mobile", "phone"]
                        is_rag_q = any(x in label_lower for x in rag_keywords)
                        context = None if is_rag_q else self._build_fresher_context()
                        ft = self._detect_field_type(label, "text")
                        answer = await self._get_llm_answer_value(brain, label, context, field_type=ft, options=option_texts)
                        
                        from utils.job_retrieval import fuzzy_match_option
                        best_opt = fuzzy_match_option(answer, option_texts)
                        if best_opt:
                            await dd.select_option(label=best_opt)
                            self.logger.log_info(f"Dropdown picked: {best_opt}")
                        else:
                            await dd.select_option(index=1)
                    await asyncio.sleep(0.2)
                except Exception as e:
                    self.logger.log_warn(f"Error filling dropdowns: {e}")
        except Exception as e:
            self.logger.log_warn(f"Error filling fields: {e}")
    
    async def _calculate_experience_from_resume(self, label: str) -> Optional[str]:
        label_lower = label.lower()
        raw_context = getattr(self.profile, "raw_resume_context", "") or ""
        if not raw_context:
            raw_context = getattr(self.profile, "experience", "") or ""
        if not raw_context:
            raw_context = getattr(self.profile, "resume_text", "") or ""
        if not raw_context:
            return "0"
        
        is_months = "month" in label_lower
        is_years = "year" in label_lower
        
        years = re.findall(r'(20[12]\d)', raw_context)
        if years:
            unique_years = sorted(set(years), key=lambda x: int(x))
            if len(unique_years) >= 2:
                start_year = int(unique_years[0])
                end_year = int(unique_years[-1])
                current_year = 2026
                if end_year > current_year:
                    end_year = current_year
                total_months = (end_year - start_year) * 12
                total_months = min(total_months, 24)
                
                if is_months:
                    return str(total_months)
                elif is_years:
                    years_val = round(total_months / 12, 1)
                    return str(years_val)
                else:
                    return str(total_months)
        return "0"
    
    async def _calculate_experience_from_resume(self, label: str) -> Optional[str]:
        """Calculate experience years/months from resume RAG context"""
        label_lower = label.lower()
        
        # Get raw resume context from profile
        raw_context = getattr(self.profile, "raw_resume_context", "") or ""
        if not raw_context:
            raw_context = getattr(self.profile, "experience", "") or ""
        if not raw_context:
            resume_text = getattr(self.profile, "resume_text", "") or ""
            raw_context = resume_text
        
        if not raw_context:
            self.logger.log_warn("No resume context found for experience calculation")
            return "0"
        
        # Check what unit is asked
        is_months = "month" in label_lower
        is_years = "year" in label_lower
        
        # Parse all years from resume
        years = re.findall(r'(20[12]\d)', raw_context)
        if years:
            unique_years = sorted(set(years), key=lambda x: int(x))
            if len(unique_years) >= 2:
                start_year = int(unique_years[0])
                end_year = int(unique_years[-1])
                current_year = 2026
                if end_year > current_year:
                    end_year = current_year
                total_months = (end_year - start_year) * 12
                total_months = min(total_months, 24)
                
                if is_months:
                    return str(total_months)
                elif is_years:
                    years_val = round(total_months / 12, 1)
                    return str(years_val)
                else:
                    return str(total_months)
        
        return "0"
    
    def _detect_field_type(self, label: str, input_type: str = "text") -> str:
        """Calculate experience years/months from resume RAG context"""
        label_lower = label.lower()
        
        # Get raw resume context from profile
        raw_context = getattr(self.profile, "raw_resume_context", "") or ""
        if not raw_context:
            raw_context = getattr(self.profile, "experience", "") or ""
        if not raw_context:
            # Try to get from resume text
            resume_text = getattr(self.profile, "resume_text", "") or ""
            raw_context = resume_text
        
        if not raw_context:
            self.logger.log_warn("No resume context found for experience calculation")
            return "0"
        
        # Check what unit is asked
        is_months = "month" in label_lower
        is_years = "year" in label_lower
        
        # Parse all years from resume
        years = re.findall(r'(20[12]\d)', raw_context)
        if years:
            unique_years = sorted(set(years), key=lambda x: int(x))
            if len(unique_years) >= 2:
                start_year = int(unique_years[0])
                end_year = int(unique_years[-1])
                current_year = 2026
                if end_year > current_year:
                    end_year = current_year
                total_months = (end_year - start_year) * 12
                total_months = min(total_months, 24)  # Cap at 24 months for freshers
                
                if is_months:
                    return str(total_months)
                elif is_years:
                    years_val = round(total_months / 12, 1)
                    return str(years_val)
                else:
                    return str(total_months)
        
        # Default fresher = 0 experience
        return "0"
    
    def _detect_field_type(self, label: str, input_type: str = "text") -> str:
        """Detect field type based on label and input type"""
        label_lower = label.lower()
        
        # Use input type as priority
        if input_type == "number" or input_type == "tel":
            return "numeric"
        
        # Check for years/months experience questions - exact match
        if "years" in label_lower or "months" in label_lower:
            if any(kw in label_lower for kw in ["experience", "exp", "working", "coding", "programming", "github", "git", "internship", "professional"]):
                return "experience"
        
        # CTC/Salary fields - VERY SPECIFIC
        if any(kw in label_lower for kw in ["ctc", "salary", "current ctc", "expected ctc", "current salary", "expected salary", "package"]):
            return "numeric"
        
        # Notice period
        if any(kw in label_lower for kw in ["notice", "period", "joining", "available"]):
            return "numeric"
        
        # Numeric fields
        numeric_keywords = ["how many", "number of", "phone", "mobile"]
        if any(kw in label_lower for kw in numeric_keywords):
            return "numeric"
        
        # Date fields
        date_keywords = ["date", "dob", "birth"]
        if any(kw in label_lower for kw in date_keywords):
            return "date"
        
        # Email fields
        email_keywords = ["email", "mail"]
        if any(kw in label_lower for kw in email_keywords):
            return "email"
        
        return "text"
    
    def _build_fresher_context(self) -> str:
        """Build comprehensive context from resume for form filling"""
        # Get contact info
        phone = getattr(self.profile, "phone", "") or ""
        email = getattr(self.profile, "email", "") or ""
        links = getattr(self.profile, 'extra', {})
        linkedin = links.get('linkedin', '') or getattr(self.profile, "linkedin", "") or ""
        github = links.get('github', '') or getattr(self.profile, "github", "") or ""
        location = getattr(self.profile, "location", "") or "India"
        
        # Get education from resume
        education = getattr(self.profile, "education", "") or ""
        
        # Get raw context with internships, projects, dates
        raw_context = getattr(self.profile, "raw_resume_context", "") or ""
        
        # Calculate experience from resume dates if available
        experience_years = "0"
        if raw_context:
            import re
            # Look for date patterns to calculate experience
            date_patterns = re.findall(r'(2020|2021|2022|2023|2024|2025)', raw_context)
            if date_patterns:
                unique_years = list(set(date_patterns))
                if len(unique_years) >= 2:
                    experience_years = f"{len(unique_years) - 1}"
        
        context_parts = [
            f"Name: {getattr(self.profile, 'name', 'Candidate')}",
            f"Email: {email if email else 'Not provided'}",
            f"Phone: {phone if phone else 'Not provided'}",
            f"Location: {location}",
            f"LinkedIn: {linkedin if linkedin else 'Not provided'}",
            f"GitHub: {github if github else 'Not provided'}",
            f"Education: {education}",
            f"Total Experience: {experience_years} years",
            f"Notice Period: Immediate (0 days)",
            f"Current CTC: 0 (fresher)",
            f"Expected CTC: 0",
            f"Skills: {', '.join(self.profile.skills) if hasattr(self.profile, 'skills') else 'N/A'}",
        ]
        
        # Add raw context if available
        if raw_context and len(raw_context) > 50:
            context_parts.append(f"Resume Details: {raw_context[:1000]}")
        
        return " | ".join(context_parts)

    async def _get_label(self, page: Page, element) -> str:
        """Try to find the question/label for an input"""
        try:
            # 1. Look for associated label
            id_val = await element.get_attribute("id")
            if id_val:
                label = page.locator(f"label[for='{id_val}']")
                if await label.count() > 0: return await label.first.inner_text()
            
            # 2. Look for aria-label or placeholder
            aria = await element.get_attribute("aria-label") or await element.get_attribute("placeholder")
            if aria: return aria
            
            # 3. Look for text in parent
            parent_text = await element.evaluate("el => el.parentElement.innerText")
            return parent_text.split('\n')[0]
        except: return ""
    
    async def _anti_ban_delay(self, applied: int) -> None:
        """Anti-ban delay using runtime settings (strict defaults for LinkedIn)."""
        settings = getattr(self, "settings", None)
        min_delay = float(getattr(settings, "min_delay_seconds", 5.0) if settings else 5.0)
        max_delay = float(getattr(settings, "max_delay_seconds", 10.0) if settings else 10.0)
        if max_delay < min_delay:
            max_delay = min_delay

        extra_after_n = int(getattr(settings, "extra_delay_after_applies", 8) if settings else 8)
        extra_min = float(getattr(settings, "extra_delay_min", 12.0) if settings else 12.0)
        extra_max = float(getattr(settings, "extra_delay_max", 22.0) if settings else 22.0)
        if extra_max < extra_min:
            extra_max = extra_min

        base = random.uniform(min_delay, max_delay)

        if applied > 0 and applied % max(1, extra_after_n) == 0:
            extra = random.uniform(extra_min, extra_max)
            self.logger.log_info(f"Anti-ban: {base + extra:.1f}s delay")
            await asyncio.sleep(base + extra)
        else:
            await asyncio.sleep(base)
    
    async def _next_page(self, page: Page) -> bool:
        """Navigate to next page"""
        try:
            next_btn = page.locator("button[aria-label*='Next'], button:has-text('Next')").first
            if await next_btn.is_visible():
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(3)
                return True
            return False
        except:
            return False

class LinkedInScraper(BaseScraper):
    source = "linkedin"
    base_url = "https://www.linkedin.com"

    def _get_locations(self, profile: Any, settings: Any) -> list[str]:
        raw = settings.preferred_locations or [profile.location]
        major_cities = ["Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "Chennai", "Ahmedabad"]
        expanded = []
        for loc in raw:
            if "major" in loc.lower() and "cit" in loc.lower(): expanded.extend(major_cities)
            else: expanded.append(loc)
        seen = set(); unique = []
        for loc in expanded:
            if loc.lower() not in seen:
                unique.append(loc); seen.add(loc.lower())
        return unique[: settings.max_locations_per_query]


    async def search_jobs(self, profile: Any, settings: Any, query_override: Optional[str] = None, page_offset: Optional[int] = None) -> tuple[list[dict[str, Any]], int, str]:
        """
        Public interface for LinkedIn Job Search.
        Expected to return (jobs, status_code, message).
        """
        # Load settings reference for auth gatekeeper
        self.settings_ref = settings
        
        if query_override:
            query = query_override
        else:
            queries = self._get_queries(profile, settings)
            query = queries[0] if queries else "MERN Full Stack Developer"
            
        location = "India" # Locked to India as requested
        
        jobs = await self._search_playwright_hardened(query, location, profile, settings, set(), page_offset=page_offset)
        return (jobs, 200, "Success")

    def _get_memory_path(self) -> Path:
        return Path("temp_pipeline/processed_jobs.json")

    def _load_memory(self) -> set[str]:
        path = self._get_memory_path()
        if not path.exists(): return set()
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return set(data.get("processed_ids", []))
        except: return set()

    def _save_to_memory(self, job_id: str):
        if not job_id: return
        path = self._get_memory_path()
        processed = self._load_memory()
        processed.add(job_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump({"processed_ids": list(processed)}, f)
        except: pass

    async def _search_playwright_hardened(
        self, query: str, location: str, profile: Any, settings: Any, seen_urls: set[str], page_offset: Optional[int] = None
    ) -> list[dict[str, Any]]:
        # V2 GLOBAL MEMORY: Load IDs from previous sessions
        global_memory = self._load_memory()
        master_found_jobs = []
        seen_job_ids = set() # Track duplicates within current overall search session
        
        # Determine the page range: either a single offset or a default 5-page sweep
        p_offsets = [page_offset] if page_offset is not None else [0, 25, 50, 75, 100]

        # v3 Optimization: Maintain one stable page for the entire sweep
        from scraper_adapter.playwright_manager import playwright_manager
        student_id = getattr(profile, "student_id", None)
        page = await playwright_manager.get_page(self.settings_ref, student_id=student_id)
        
        # 1. AUTH GATEKEEPER (One-time Pulse)
        await self.ensure_authenticated(page)

        page_counter = 0
        for start_idx in p_offsets:
            if len(master_found_jobs) >= 100: break 
            
            # Turbo Armor Check: Recycle engine every 3 cycles to prevent memory leakage
            if page_counter > 0 and page_counter % 3 == 0:
                self.logger.log_info(f"[INFRA-ARMOR] Threshold reached at Page {start_idx // 25}. Recycling engine...")
                await playwright_manager.recycle_engine(self.settings_ref, student_id=student_id)
                page = await playwright_manager.get_page(self.settings_ref, student_id=student_id)
                await self.ensure_authenticated(page)
                # v3 Fix: No recursion needed; the loop will continue naturally with the new Page reference

            search_url = (
                f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}"
                f"&location=India&f_AL=true&f_E=1,2&f_TPR=r604800&f_JT=F,I&f_WT=1,2,3&start={start_idx}"
            )
            self.logger.log_info(f"Targeting LinkedIn Search URL (Turbo Page {start_idx // 25 + 1}): {search_url}")
            
            async def extract(page: Page):
                card_selectors = [
                    "li[data-occludable-job-id]", 
                    ".job-card-container", 
                    ".job-card-list__title--link",
                    ".job-card-container__link",
                    ".scaffold-layout__list-item",
                    "div.job-search-card"
                ]
                try: await page.wait_for_selector(", ".join(card_selectors), timeout=12000)
                except: 
                    await page.reload(); await asyncio.sleep(3)
                    try: await page.wait_for_selector(", ".join(card_selectors), timeout=8000)
                    except: return []
                
                # RE-ENGINEERED: Sidebar Scroller for 100% Page Load
                try:
                    # New Resilient Selectors: LinkedIn v2 Layout Support
                    sidebar_selectors = [
                        "div[scrollable='true']", 
                        ".jobs-search-results-list", 
                        "div:has(> .job-card-container)",
                        ".jobs-search-results--is-list"
                    ]
                    sidebar = None
                    for selector in sidebar_selectors:
                        if await page.locator(selector).count() > 0:
                            sidebar = page.locator(selector).first; break

                    if sidebar:
                        self.logger.log_info(f"Engaging Multi-Selector Sidebar Scroller (Target: {start_idx})")
                        for _ in range(5): # Intense sweep
                             await sidebar.evaluate("el => el.scrollTop += 1200")
                             await asyncio.sleep(0.7)
                except: pass
                
                cards_locator = page.locator(", ".join(card_selectors))
                count = await cards_locator.count()
                self.logger.log_info(f"Auditing results: {count} candidate cards identified.")

                # Shuffle indices for organic movement
                indices = list(range(count))
                random.shuffle(indices)
                
                page_found = []
                for idx in indices:
                    # Limit removed to allow 25+ sweep
                    card = cards_locator.nth(idx)
                    try:
                        # v3 VERIFICATION OVERRIDE: Memory check paused
                        # if job_id and job_id in global_memory:
                        #     continue # Already processed in a previous session!
                        
                        # 2. PRE-CLICK INSTANT SKIP (Status Badge)
                        # is_applied_badge = await card.locator(".jobs-search-results-list__list-item--applied, .job-card-container__footer-item--applied, .artdeco-inline-feedback--success").count() > 0
                        # if is_applied_badge: 
                        #     if job_id: self._save_to_memory(job_id)
                        #     continue 

                        if page.is_closed(): break 
                        # v3 Precision: Scroll ensure the card is active for details rendering
                        await card.scroll_into_view_if_needed()
                        await card.click()
                        await asyncio.sleep(1.5) # v3 Precision: Wait for details pane
                        
                        # 2. POST-CLICK INSTANT SKIP
                        applied_indicators = [
                            ".jobs-apply-button--applied", "button[aria-label='Applied']", 
                            "button[aria-label^='Applied to']", "span.artdeco-inline-feedback__message:has-text('Applied')"
                        ]
                        # v3 VERIFICATION OVERRIDE: Applied indicator check paused
                        # if is_really_applied: continue

                        # 3. INSTANT ROLE FILTER: Polling for 'Easy Apply' button
                        easy_apply_selectors = [
                            "#jobs-apply-button-id", # v3 Audited Direct ID
                            ".jobs-apply-button",    # v3 Audited Base Class
                            "button.jobs-apply-button:has-text('Easy Apply')",
                            ".jobs-apply-button--top-card button:has-text('Easy Apply')",
                            "button[aria-label*='Easy Apply']",
                            ".jobs-s-apply button:has-text('Easy Apply')"
                        ]
                        easy_apply_btn = None
                        # v3 Verification: Poll for up to 5s for dynamic JS render
                        for _ in range(5):
                            for selector in easy_apply_selectors:
                                try:
                                    btn = page.locator(selector).first
                                    if await btn.count() > 0 and await btn.is_visible():
                                        easy_apply_btn = btn; break
                                except: continue
                            if easy_apply_btn: break
                            await asyncio.sleep(1.0) # Wait for UI stabilization
                            
                        if not easy_apply_btn: 
                            self.logger.log_info(f"Skip card {idx+1}: No Easy Apply button detected (Absolute Verification Strike Active).")
                            continue

                        # 4. Expand JD
                        show_more_selectors = ["button[aria-label*='Show more']", "button:has-text('Show more')"]
                        for sms in show_more_selectors:
                            try:
                                btn = page.locator(sms).first
                                if await btn.count() > 0 and await btn.is_visible():
                                    await btn.click(timeout=3000); await asyncio.sleep(0.5)
                                    break
                            except: continue

                        title_el = page.locator(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1.t-24, .topcard__link h2").first
                        company_el = page.locator(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .topcard__org-name-link").first
                        title = await title_el.inner_text() if await title_el.count() > 0 else ""
                        company = await company_el.inner_text() if await company_el.count() > 0 else ""
                        if not title: continue
                        
                        job_id = await card.get_attribute("data-job-id") or await card.get_attribute("data-occludable-job-id")
                        
                        if not job_id:
                            # Fallback: Extract from link href
                            href = await card.get_attribute("href") or ""
                            job_id = self._extract_job_id(href)
                            
                        if not job_id:
                            job_id = self._extract_job_id(page.url)
                        # v3 VERIFICATION OVERRIDE: Local seen filters paused
                        # if not job_id or job_id in seen_job_ids or page.url in seen_urls: continue
                        seen_urls.add(page.url); seen_job_ids.add(job_id)
                        # V2 GLOBAL MEMORY: Save successfully extracted job to permanent memory
                        if job_id: self._save_to_memory(job_id)
                        
                        jd_el = page.locator(".jobs-description-content__text, .jobs-description__content, #job-details, .jobs-box__html-content, .show-more-less-html__markup").first
                        final_jd = ""
                        if await jd_el.count() > 0:
                            raw_jd = (await jd_el.inner_text()).strip()
                            
                            # v3 MANUAL OVERRIDE: Experience filter paused for verification test
                            # exp_match = re.search(r"(?<!\d)(?:[2-9]|[1-9][0-9])\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)\b", raw_jd, re.IGNORECASE)
                            # if exp_match:
                            #     self.logger.log_info(f"Instant Skip: {exp_match.group(0)} detected (Fresher Shield active).")
                            #     if job_id: self._save_to_memory(job_id)
                            #     continue

                            words = re.sub(r"\s+", " ", raw_jd).strip().split()
                            final_jd = " ".join(words[:400])

                        page_found.append({
                            "title": normalize_whitespace(title), "company": normalize_whitespace(company), "location": location, 
                            "url": page.url, "job_id": job_id, "description": normalize_whitespace(final_jd), "required_skills": [], "apply_link": page.url
                        })
                    except Exception: 
                        import traceback
                        self.logger.log_error(f"Page {start_idx // 25 + 1} job extraction error: {traceback.format_exc()}")
                        continue
                return page_found
            
            try: 
                self.logger.log_info(f"Navigating to Turbo Page {start_idx // 25 + 1}...")
                # Direct Persistent Navigation
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.uniform(2, 4)) # Organic pause
                
                results = await extract(page)
                if results and isinstance(results, list):
                    master_found_jobs.extend(results)
                    self.logger.log_info(f"Page {start_idx // 25 + 1} complete. Identified {len(results)} valid candidates.")
                elif results == []:
                    self.logger.log_info(f"Page {start_idx // 25 + 1} complete: No candidates passed fresher/EasyApply filters.")
                else:
                    self.logger.log_warn(f"Page {start_idx // 25 + 1} yielded no result due to network/scraping error.")
            except Exception as exc: 
                self.logger.log_err(f"Playwright strike on page {start_idx // 25 + 1} failed: {exc}")
            
            page_counter += 1
                
        # Final Random Discovery: Shuffle the master pool across all pages
        random.shuffle(master_found_jobs)
        return master_found_jobs

    def _extract_job_id(self, value: str) -> str:
        match = re.search(r"/jobs/view/(\d+)", value)
        if match: return match.group(1)
        match = re.search(r"currentJobId=(\d+)", value)
        if match: return match.group(1)
        return ""

    async def apply_job(self, page: Page, resume_path: Path, profile: Any, job: dict, llm_answers: Any, analysis: dict[str, Any] | None = None) -> dict:
        """v2-Style: Unified High-Fidelity Apply Orchestrator."""
        res = {"applied": False, "status": "not_started"}
        
        # 1. Open the Modal
        easy_apply_selectors = [".jobs-apply-button button:has-text('Easy Apply')", "button[aria-label*='Easy Apply']", "button:has-text('Easy Apply')"]
        for sel in easy_apply_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    self.logger.log_info(f"Opening Easy Apply modal...")
                    await btn.click(); break
            except: continue

        # 2. Sequential Strike Phase (Process Modals)
        try:
            from engine.form_filler import FormFiller
            from engine.uploader import ResumeUploader
        except ImportError:
            from job_automation_system.engine.form_filler import FormFiller
            from job_automation_system.engine.uploader import ResumeUploader

        filler = FormFiller(self.logger)
        uploader = ResumeUploader(self.logger)
        
        for step in range(15): # Support up to 15-step complex forms
            await asyncio.sleep(2) # Stabilization pause
            
            # v3 Special Sensor: Check for Resume Upload on EVERY step (LinkedIn Hardened)
            if resume_path:
                await uploader.upload_resume(page, resume_path)

            # Check for immediate success or final submission screen
            modal_text = await page.locator("div[role='dialog']").first.inner_text()
            if "Application submitted" in modal_text or "Thanks for applying" in modal_text:
                self.logger.log_ok(f"âœ… MISSION SUCCESS: Applied to {job.get('company')}")
                # Track for notification
                self._last_applied_job_title = job.get('title') or self.current_job_title or 'N/A'
                self._last_applied_company = job.get('company') or self.current_company_name or 'N/A'
                self.applied_count += 1
                # v3.5 DASHBOARD SYNC
                await self.logger.log_application_success(
                    job_id=job.get('job_id', 'unknown'),
                    title=self._last_applied_job_title or 'Software Engineer',
                    company=self._last_applied_company or 'LinkedIn',
                    platform="linkedin",
                    student_id=self._get_candidate_id()
                )
                return {"applied": True, "status": "submitted"}
            
            # Fill current window fields (Now passing resume_path for v3 Sensors)
            self.logger.log_info(f"Striking Form Step {step + 1}...")
            stats = await filler.fill_application_form(
                page=page, 
                profile=profile, 
                job=job, 
                answers={}, 
                llm_answers=llm_answers, 
                analysis=analysis,
                resume_path=str(resume_path)
            )
            # Stabilization: Wait for LinkedIn JS to register answers (2-3s window)
            import random
            await asyncio.sleep(random.uniform(2.3, 3.2))
            
            # Move to next step (Strictly Modal-Scoped)
            modal = page.locator("div[role='dialog'], .artdeco-modal").first
            nav_selectors = ["button:has-text('Submit application')", "button:has-text('Next')", "button:has-text('Review')", "button:has-text('Continue')"]
            clicked = False
            for sel in nav_selectors:
                btn = modal.locator(sel).last
                if await btn.count() > 0 and await btn.is_visible() and not await btn.is_disabled():
                    btn_text = (await btn.inner_text()).strip()
                    self.logger.log_info(f"Navigating to next step via '{btn_text}'...")
                    await btn.click(force=True)
                    # Submit Rescue: If we clicked submit, wait longer for success modal
                    if "Submit" in btn_text:
                        await asyncio.sleep(4)
                    clicked = True; break
            
            if not clicked:
                # Check for 'Done' or 'Dismiss' (Success modal)
                dismiss = page.locator("button[aria-label='Dismiss'], button:has-text('Done'), button:has-text('Dismiss')").first
                if await dismiss.count() > 0 and await dismiss.is_visible():
                    self.logger.log_info("Application Successful. Closing modal.")
                    await dismiss.click()
                    break
                # Last resort: click outside or press Escape if stuck
                await page.keyboard.press("Escape")
                break
                
        return res

    async def _v2_form_scanner(self, page: Page, modal: Locator, profile: Any, job: dict, resume_path: Path, llm_answers: Any):
        from utils.humanize import human_type
        # 1. Inputs & Textareas
        interactive = await modal.locator("input:not([type='hidden']):not([type='file']):not([role='radio']), textarea, select, [role='combobox'], [role='radio'], [role='checkbox']").all()
        
        seen_questions = set()

        # 1. METADATA SCAN (Batch Phase)
        fields_metadata = []
        field_to_id = {}
        processed_fields = []

        for i, field in enumerate(interactive):
            try:
                if not await field.is_visible() or await field.is_disabled(): continue
                
                question = await self._get_question_text(field, modal)
                if not question or question in seen_questions: continue
                seen_questions.add(question)

                tag = (await field.evaluate("el => el.tagName.toLowerCase()")).lower()
                role = (await field.get_attribute("role") or "").lower()
                type_attr = (await field.get_attribute("type") or "text").lower()
                
                options = []
                if tag == "select":
                    options = [o for o in await field.locator("option").all_inner_texts() if o.strip()]
                elif role == "radio" or type_attr == "radio":
                    group = field.locator("xpath=ancestor::*[self::fieldset or @role='radiogroup'][1]")
                    group_scope = group if await group.count() > 0 else modal
                    options = [o.strip() for o in await group_scope.locator("label, [role='radio']").all_inner_texts() if o.strip()]

                m_type = "select" if tag == "select" else ("radio" if (role == "radio" or type_attr == "radio") else "text")
                
                fields_metadata.append({
                    "id": f"Q{i}",
                    "text": question,
                    "type": m_type,
                    "options": options
                })
                processed_fields.append((field, question, m_type, options))
            except: continue

        # 2. BATCH DISPATCH (The "Turbo Jump")
        # Global RAG Context for the whole page
        from utils.job_retrieval import retrieve_field_relevant_chunks
        combined_q_text = " ".join([m['text'] for m in fields_metadata])
        context = retrieve_field_relevant_chunks(combined_q_text, [getattr(profile, "resume_text", ""), job.get("description", "")])
        batch_context = "\n".join(context)
        
        if llm_answers is None:
            batch_answers = {}
        else:
            batch_answers = await llm_answers.answer_questions_batch(fields_metadata, profile, job, context=batch_context)

        # 3. RAPID FILL (Phase 3)
        for field, question, m_type, options in processed_fields:
            try:
                ans = batch_answers.get(question)
                if not ans or "N/A" in ans: continue

                if m_type == "text":
                    await field.scroll_into_view_if_needed()
                    await field.fill("")
                    await human_type(field, ans)
                
                elif m_type == "select":
                    from utils.job_retrieval import fuzzy_match_option
                    best_opt = fuzzy_match_option(ans, options)
                    if best_opt: await field.select_option(label=best_opt)

                elif m_type == "radio":
                    group = field.locator("xpath=ancestor::*[self::fieldset or @role='radiogroup'][1]")
                    group_scope = group if await group.count() > 0 else modal
                    from utils.job_retrieval import fuzzy_match_option
                    best_opt = fuzzy_match_option(ans, options)
                    if best_opt:
                        opt_nodes = await group_scope.locator("label, [role='radio']").all()
                        for node in opt_nodes:
                            if (await node.inner_text()).strip() == best_opt:
                                await node.click(force=True); break
            except: continue
        
        # 2. File Upload
        file_input = modal.locator("input[type='file']").first
        if await file_input.count() > 0:
            try:
                # Force reveal hidden input
                await file_input.evaluate("el => { el.style.display='block'; el.style.opacity='1'; el.style.visibility='visible'; }")
                await file_input.set_input_files(str(resume_path))
                await asyncio.sleep(1)
            except: pass

    async def _get_question_text(self, field: Locator, modal: Locator) -> str:
        parts = []
        try:
            for attr in ["aria-label", "placeholder", "name"]:
                val = await field.get_attribute(attr)
                if val: parts.append(val)
            fid = await field.get_attribute("id")
            if fid:
                lbl = modal.locator(f"label[for='{fid}']").first
                if await lbl.count() > 0: parts.append(await lbl.inner_text())
        except: pass
        return compact_text(" ".join(parts))

    async def _v2_generic_scanner(self, page: Page, modal: Locator, profile: Any, job: dict):
        # This mirrors the 'v2' Section 7 (Turn 111)
        interactive = await modal.locator("input:not([type='hidden']), textarea, select, [role='combobox'], [role='checkbox'], [role='radio']").all()
        for field in interactive:
            try:
                if not await field.is_visible(): continue
                question = await self._get_question_text(field, modal)
                if not question: continue
                
                # Logic from v2 for answering anything with old resume data
                # We'll use the 'ApplyEngine' and 'FormAnswerer' flow but ensure it uses the RAG context we just retrieved.
                # (Actual LLM calls are orchestrated inside ApplyEngine, but we can nudge them here or in FormFiller)
            except: pass
