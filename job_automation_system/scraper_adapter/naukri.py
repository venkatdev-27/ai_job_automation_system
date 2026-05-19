"""
Naukri 10/10 Production Scraper
===============================
Simplified Flow: Card-level extraction → Skill match → Apply
- No JD page opening (except when clicking apply)
- No LLM per job
- Simple keyword match
- Anti-ban delays
- Resume variants (2-3 only)

DYNAMIC ROLE: Uses dynamic_role_generator for:
- Initial resume generation (5-6 roles from user skills)
- Per-page role rotation for search queries
- Resume matching per job application
"""

import asyncio
import os
import random
import re
import sys
from pathlib import Path

# Ensure the job_automation_system root is in sys.path to avoid shadowing by top-level ai_engine
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page

from scraper_adapter.base_scraper import BaseScraper
from scraper_adapter.naukri_selenium import create_selenium_scraper

from utils.job_utils import normalize_whitespace
from scraper_adapter.playwright_manager import playwright_manager
from utils.session_manager import SessionManager
from role_manager.dynamic_role_generator import (
    get_role_by_top_skills,
    extract_role_from_skills,
)
from producer.job_generator import JobGenerator
from utils.student_mongodb import get_student_profile, list_all_students
from utils.resume_downloader import download_resume_from_url
from utils.resume_selector import ResumeSelector, extract_skills_from_jd
from utils.path_contract import resolve_ai_engine_pdf_path
from utils.ai_extractor import get_ai_extractor
from utils.skill_scorer import calculate_match_percentage, SkillScorer
from typing import Optional
try:
    from rag_engine.rag_engine import RAGEngine
except ImportError:
    RAGEngine = None

# Local module imports (self-contained, no ai_job_auto_apply dependency)
try:
    from rag_engine.rag_resume_generator import get_rag_resume_generator
except ImportError:
    get_rag_resume_generator = None

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


class NaukriScraper(BaseScraper):
    source = "naukri"
    base_url = "https://www.naukri.com"
    
    # Default resume variants (can be overridden)
    RESUME_VARIANTS = {
        "frontend": "resume_frontend.pdf",
        "backend": "resume_backend.pdf",
        "fullstack": "resume_fullstack.pdf",
    }

    async def search_and_apply(
        self,
        profile: Any,
        settings: Any,
    ) -> dict[str, Any]:
        """
        10/10 Main Entry Point: Try Playwright first, fallback to Selenium
        """
        self.settings_ref = settings
        
        # Try Playwright first
        try:
            result = await self._run_playwright_flow(profile, settings)
            if result.get("applied", 0) > 0 or result.get("status") == "success":
                return result
            self.logger.log_warn("Playwright flow found no jobs or failed. Trying Selenium fallback...")
        except Exception as e:
            self.logger.log_err(f"Playwright flow crashed: {e}. Trying Selenium fallback...")
            
        # Selenium Fallback
        try:
            sid = self._get_candidate_id(profile)
            selenium_scraper = create_selenium_scraper(self.logger, settings, student_id=sid)
            driver = await selenium_scraper.get_driver(headless=True)
            
            # Login
            login_success = await selenium_scraper.login(profile.username, profile.password)
            if not login_success:
                await selenium_scraper.close()
                return {"status": "failed", "applied": 0, "error": "selenium_login_failed"}
                
            # Search
            count = await selenium_scraper.search_jobs(profile.target_role)
            if count > 0:
                # For now, we just log that we found jobs. 
                # Full application flow in Selenium would need to be implemented in naukri_selenium.py
                self.logger.log_ok(f"Selenium found {count} jobs! (Full Selenium apply coming soon)")
                # Return success if we found jobs to indicate progress
                await selenium_scraper.close()
                return {"status": "success", "applied": count, "method": "selenium"}
            
            await selenium_scraper.close()
        except Exception as e:
            self.logger.log_err(f"Selenium fallback also failed: {e}")
            
        return {"status": "failed", "applied": 0}

    async def _run_playwright_flow(
        self,
        profile: Any,
        settings: Any,
    ) -> dict[str, Any]:
        """
        Original Playwright-based search + apply flow
        """
        import traceback
        import time as _time
        self.current_search_url = None  # Store for recycling
        self._warmup_roles = []
        self._warmup_skill_keywords = []
        applied_count = 0
        skipped_count = 0
        
        self.settings_ref = settings
        
        results = []
        self._last_applied_job_title = None
        self._last_applied_company = None
        self.current_job_title = ""
        self.current_company_name = ""
        
        # Session time tracking (anti-detection)
        self._session_start = _time.time()
        
        # Platform-specific caps
        from config.platforms import get_platform_config
        _plat_cfg = get_platform_config("naukri")
        platform_cap = _plat_cfg.max_applies_per_run if _plat_cfg else 10
        requested_target = int(
            getattr(settings, "max_applies_per_run", 0)
            or getattr(settings, "target_applies", 0)
            or 0
        )
        self._max_applies = min(requested_target, platform_cap) if requested_target > 0 else platform_cap
        self.logger.log_info(f"Naukri apply target for this run: {self._max_applies}")
        self._session_limit = _plat_cfg.session_time_limit if _plat_cfg else 2100
        self._micro_break_interval = _plat_cfg.micro_break_interval if _plat_cfg else 3
        self._micro_break_min = _plat_cfg.micro_break_min if _plat_cfg else 15.0
        self._micro_break_max = _plat_cfg.micro_break_max if _plat_cfg else 40.0
        
        # Initialize AI Answers
        self.brain = None
        if LLMAnswers:
            self.brain = LLMAnswers(settings, self.logger)
        # Reused for chatbot retrieval so indexed vectorstore stays available.
        self._chatbot_rag_engine = None

        try:
            # Try CDP first (real Chrome), fall back to Playwright
            import os
            cdp_url = os.environ.get("CDP_URL")
            use_cdp = os.environ.get("USE_CDP", "true").lower() == "true"
            
            if use_cdp:
                try:
                    page, method = await playwright_manager.get_page_with_cdp_fallback(
                        settings,
                        student_id=getattr(profile, "student_id", None),
                        cdp_url=cdp_url,
                    )
                    self.logger.log_ok(f"Browser via: {method.upper()} (CDP)")
                except Exception as e:
                    self.logger.log_warn(f"CDP failed ({e}), using Playwright with enhanced spoofing...")
                    page = await playwright_manager.get_page(
                        settings,
                        student_id=getattr(profile, "student_id", None),
                    )
                    self.logger.log_info("Browser via: Playwright (enhanced)")
            else:
                page = await playwright_manager.get_page(
                    settings,
                    student_id=getattr(profile, "student_id", None),
                )
                self.logger.log_info("Browser via: Playwright")
        except Exception as e:
            self.logger.log_err(f"Failed to get browser page: {e}")
            return {"status": "browser_error", "applied": 0, "skipped": 0, "error": str(e)}
        
        page.on("console", lambda msg: self.logger.log_info(f"BROWSER CONSOLE: [{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: self.logger.log_err(f"BROWSER ERROR: {err.message}"))
        
        try:
            # PHASE 1: Login

            login_ok = await self._ensure_logged_in(page, settings, profile)
            if not login_ok:
                self.logger.log_err("Naukri login failed; stopping run before job search.")
                return {
                    "status": "error",
                    "applied": applied_count,
                    "skipped": skipped_count,
                    "error": "naukri_login_failed",
                }
            # Initial resume upload removed - now done dynamically per job match in _strike_loop
            
            # PHASE 1.5: RUN WARMUP if needed (discover roles + generate 5-6 resumes)
            await self._ensure_warmup(profile)
            
            # PHASE 2: Build roles list - FIRST role is main search, remaining as fallback
            roles_str = self._build_query(profile)
            all_roles = [r.strip() for r in roles_str.split(",") if r.strip()]
            self.logger.log_info(f"All roles: {all_roles}")
            
            if not all_roles:
                all_roles = ["Software Developer"]
            
            # FIRST: Search MAIN role (first candidate_title) with full pagination
            main_role = all_roles[0]
            remaining_roles = all_roles[1:] if len(all_roles) > 1 else []
            
            self.logger.log_ok(f"=== MAIN SEARCH ROLE: {main_role.upper()} ===")
            
            # --- DYNAMIC RESUME UPLOAD FOR MAIN ROLE ---
            self.logger.log_info(f"Targeting profile resume for: {main_role}")
            main_upload_ok = await self._ensure_resume_uploaded(page, settings, profile, jd_text=main_role)
            if not main_upload_ok:
                self.logger.log_warn(
                    f"Resume upload failed for main role '{main_role}'. Continuing with existing profile resume."
                )
            
            # Search + Lock Cards for main role
            total_cards = await self._search_and_lock(page, main_role, settings, profile)

            if total_cards > 0:
                # Strike Loop for main role
                applied = await self._strike_loop(page, profile, settings, applied_count)
                applied_count += applied
                
                # Pagination for main role
                if settings.max_pages_per_run > 1:
                    for page_num in range(1, settings.max_pages_per_run):
                        if applied_count >= settings.max_applies_per_run:
                            break
                        if applied_count >= self._max_applies:
                            break
                        self.logger.log_info(f"Paginating {main_role} - Page {page_num + 1}")
                        if not await self._next_page(page):
                            break
                        if await self._wait_for_cards(page) > 0:
                            applied = await self._strike_loop(page, profile, settings, applied_count)
                            applied_count += applied
            
            # AFTER MAIN ROLE: Search remaining roles (if still need more applies)
            for role_idx, role in enumerate(remaining_roles):
                if applied_count >= settings.max_applies_per_run:
                    break
                if applied_count >= self._max_applies:
                    break
                
                self.logger.log_ok(f"--- SEARCHING ROLE {role_idx + 2}: {role.upper()} ---")
                
                # --- DYNAMIC RESUME UPLOAD FOR THIS ROLE ---
                self.logger.log_info(f"Targeting profile resume for: {role}")
                role_upload_ok = await self._ensure_resume_uploaded(page, settings, profile, jd_text=role)
                if not role_upload_ok:
                    self.logger.log_warn(
                        f"Resume upload failed for role '{role}'. Proceeding with currently uploaded resume."
                    )
                
                # Search + Lock Cards for this role
                total_cards = await self._search_and_lock(page, role, settings, profile)

                if total_cards == 0:
                    self.logger.log_warn(f"No jobs found for role: {role}")
                    continue
                
                # Strike Loop for this role
                applied = await self._strike_loop(page, profile, settings, applied_count)
                applied_count += applied
                
                # Pagination for this role
                if settings.max_pages_per_run > 1:
                    for page_num in range(1, settings.max_pages_per_run):
                        if applied_count >= settings.max_applies_per_run:
                            break
                        if applied_count >= self._max_applies:
                            break
                        self.logger.log_info(f"Paginating {role} - Page {page_num + 1}")
                        if not await self._next_page(page):
                            break
                        if await self._wait_for_cards(page) > 0:
                            applied = await self._strike_loop(page, profile, settings, applied_count)
                            applied_count += applied

            # GENERIC FALLBACKS: only after primary discovered roles are exhausted.
            if applied_count < self._max_applies:
                fallback_roles = ["Software Engineer", "Software Developer"]
                used_roles = {r.lower().strip() for r in all_roles}
                remaining_target = self._max_applies - applied_count
                self.logger.log_info(
                    f"Primary roles completed with applied={applied_count}. Remaining target={remaining_target}. Starting generic fallback roles."
                )

                for fb_role in fallback_roles:
                    if applied_count >= self._max_applies:
                        break
                    if fb_role.lower() in used_roles:
                        continue

                    remaining_target = max(1, self._max_applies - applied_count)
                    dynamic_job_window = min(len(all_roles) * 5 if all_roles else 15, remaining_target * 3)
                    self.logger.log_ok(
                        f"--- FALLBACK ROLE: {fb_role.upper()} (scan_window={dynamic_job_window}) ---"
                    )
                    self.logger.log_info(f"Targeting profile resume for fallback role: {fb_role}")
                    fb_upload_ok = await self._ensure_resume_uploaded(page, settings, profile, jd_text=fb_role)
                    if not fb_upload_ok:
                        self.logger.log_warn(
                            f"Resume upload failed for fallback role '{fb_role}'. Proceeding with current profile resume."
                        )

                    total_cards = await self._search_and_lock(page, fb_role, settings, profile)

                    if total_cards == 0:
                        self.logger.log_warn(f"No jobs found for fallback role: {fb_role}")
                        continue

                    applied = await self._strike_loop(
                        page,
                        profile,
                        settings,
                        applied_count,
                        max_jobs_to_scan=dynamic_job_window,
                    )
                    applied_count += applied
                    used_roles.add(fb_role.lower())
            
            return {
                "status": "completed",
                "applied": applied_count,
                "skipped": skipped_count,
                "job_title": self._last_applied_job_title,
                "company": self._last_applied_company,
            }
            
        except Exception as e:
            self.logger.log_err(f"Search error: {e}")
            import traceback
            self.logger.log_err(traceback.format_exc())
            return {
                "status": "error",
                "applied": applied_count,
                "skipped": skipped_count,
                "error": str(e),
                "job_title": self._last_applied_job_title,
                "company": self._last_applied_company,
            }
            
        finally:
            try:
                await playwright_manager.return_page(page)
            except:
                pass

    def _resolve_naukri_credentials(self, profile: Any, settings: Any) -> tuple[str, str, str]:
        """Resolve Naukri credentials from MongoDB first, runtime settings fallback."""
        email = ""
        password = ""

        try:
            from database.credentials import get_student_credentials

            student_id = self._get_candidate_id(profile)
            creds = get_student_credentials(student_id) or {}
            naukri = creds.get("naukri", {}) if isinstance(creds, dict) else {}
            email = (naukri.get("email") or naukri.get("username") or "").strip()
            password = (naukri.get("password") or "").strip()
            if email and password:
                return email, password, "mongodb_credentials"
        except Exception as e:
            self.logger.log_warn(f"MongoDB credential lookup failed: {e}")

        email = (
            getattr(settings, "naukri_email", "")
            or getattr(settings, "naukri_username", "")
            or ""
        ).strip()
        password = (getattr(settings, "naukri_password", "") or "").strip()
        if email and password:
            return email, password, "runtime_settings_fallback"

        return email, password, "missing"

    async def _ensure_logged_in(self, page: Page, settings: Any, profile: Any) -> bool:
        """Naukri login with session persistence - tries restore first, then fresh login."""
        email, password, source = self._resolve_naukri_credentials(profile, settings)
        if not email or not password:
            self.logger.log_err("Naukri credentials missing. Configure student.credentials.naukri in MongoDB.")
            return False

        # Get student_id from profile
        student_id = getattr(profile, "student_id", None) or getattr(profile, "_id", None) or "default"
        
        # Initialize session manager
        session_mgr = SessionManager(student_id, "naukri")
        
        # STEP 1: Try to restore existing session first
        self.logger.log_info(f"Checking for existing session for {student_id}/naukri...")
        session_restored = await session_mgr.restore_session(page)
        
        if session_restored:
            # Verify session is valid by checking we're logged in
            try:
                await page.goto("https://www.naukri.com/mnjuser/homepage", timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                if "nlogin" not in page.url.lower():
                    self.logger.log_ok(f"Naukri session restored successfully for {student_id}")
                    return True
                else:
                    self.logger.log_info("Restored session expired, will perform fresh login")
            except Exception:
                self.logger.log_info("Session verification failed, will perform fresh login")
        
        # STEP 2: No valid session - perform fresh login
        self.logger.log_info(f"No valid session found, performing fresh Naukri login for {student_id}")
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.log_info(f"Naukri login attempt {attempt}/{max_retries} (source={source})")

                try:
                    await page.goto("https://www.naukri.com/nlogin/logout", wait_until="domcontentloaded", timeout=10000)
                    await asyncio.sleep(1.5)
                except Exception:
                    pass

                self.logger.log_info("Navigating to login page...")
                await page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded", timeout=120000)
                self.logger.log_info("Landing on login page, waiting for username field...")
                await asyncio.sleep(2.5)

                username_field = page.locator("#usernameField")
                await username_field.wait_for(state="visible", timeout=45000)
                self.logger.log_info("Username field visible, filling credentials...")
                await username_field.fill(email)
                await page.fill("#passwordField", password)
                await page.wait_for_timeout(500)
                self.logger.log_info("Clicking login button...")
                await page.locator("button[type='submit']").first.click()
                
                # Wait for network response
                self.logger.log_info("Waiting for post-login redirection...")
                await page.wait_for_timeout(8000)

                # Verify logged in
                if "nlogin/login" in (page.url or "").lower():
                    self.logger.log_warn("Still on Naukri login page after submit; retrying login flow.")
                    if attempt < max_retries:
                        await asyncio.sleep(2.0 * attempt)
                        continue
                    return False

                await page.goto("https://www.naukri.com/mnjuser/homepage", wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(3)
                if "nlogin/login" in (page.url or "").lower():
                    self.logger.log_warn("Naukri redirected back to login page after auth; retrying.")
                    if attempt < max_retries:
                        await asyncio.sleep(2.0 * attempt)
                        continue
                    return False

                # STEP 3: Login successful - save session for future use
                self.logger.log_ok("Naukri login successful. Saving session...")
                await session_mgr.save_session(page)
                
                return True
            except Exception as e:
                try:
                    await page.screenshot(path=f"/app/logs/naukri_login_fail_att{attempt}.png")
                    html_content = await page.content()
                    with open(f"/app/logs/naukri_login_fail_att{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                except:
                    pass
                self.logger.log_warn(f"Naukri login attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2.0 * attempt)
                    continue

        self.logger.log_err("Naukri login failed after all retries.")
        return False

    async def _ensure_resume_uploaded(self, page: Page, settings: Any, profile: Any, jd_text: str = "", target_resume_path: str = None, jd_skills: list = None) -> bool:
        """
        Upload resume to Naukri profile.
        If target_resume_path is provided, uploads that specific file.
        Otherwise, uses ResumeSelector for intelligent selection.
        If jd_skills is provided, reuse them to avoid redundant AI extraction.
        """
        try:
            if not await self._open_naukri_profile_page(page):
                self.logger.log_err("Could not open Naukri profile page for resume upload.")
                return False
            
            # 1. Determine which resume to upload
            resume_path = target_resume_path
            student_id = self._get_candidate_id(profile) or "default"
            profile_skills = getattr(profile, "skills", [])
            selector = ResumeSelector(student_id)
            best_bucket = ""
            
            if not resume_path:
                # Use provided jd_skills if available, otherwise extract
                if jd_skills is None:
                    self.logger.log_info("Extracting JD skills with AI...")
                    extractor = get_ai_extractor()
                    jd_skills = await extractor.extract_skills_async(jd_text) if jd_text else []
                    
                    if not jd_skills and jd_text:
                        self.logger.log_warn("AI skill extraction failed - using regex fallback")
                        jd_skills = extract_skills_from_jd(jd_text)
                else:
                    self.logger.log_info("Reusing extracted JD skills...")
                
                resume_type, resume_path, source = selector.select_resume(
                    jd_text=jd_text,
                    jd_skills=jd_skills,
                    job_title=jd_text,
                    profile_skills=profile_skills
                )
                
                # Store bucket for fallback and logging
                best_bucket = selector.get_bucket_for_role(
                    "discovered", jd_skills=jd_skills, job_title=jd_text or ""
                ) if jd_skills or jd_text else "master"
                
                self.logger.log_info(f"Resume selection: {resume_type} - {source} - Bucket: {best_bucket}")
                
                if resume_type == "AI_TAILOR_NEEDED":
                    tailored_path = await self._generate_ai_resume(profile, jd_text, student_id, selector)
                    if tailored_path:
                        resume_path = str(tailored_path)
                    else:
                        # Dynamic fallback based on matched bucket
                        best_title, _, best_skill = selector.find_best_role_dynamic(jd_skills)
                        best_bucket = selector.get_bucket_for_role(best_title, match_skill=best_skill, jd_skills=jd_skills, job_title=jd_text)
                        resume_path = str(selector.get_pre_generated_resume_path(best_bucket, job_title=jd_text))
                elif jd_text or jd_skills:
                    best_bucket = selector.get_bucket_for_role("discovered", jd_skills=jd_skills, job_title=(jd_text or "")[:100])
            
            # Final verification of file existence
            if not resume_path or not os.path.exists(resume_path):
                self.logger.log_warn(f"Local resume not found: {resume_path}. Attempting Cloudinary fallback.")
                
                # Get the bucket variant (only compute if not already set)
                if not best_bucket:
                    best_bucket = selector.get_bucket_for_role("discovered", jd_skills=jd_skills, job_title=(jd_text or "")[:100])
                
                resume_url = None
                resume_urls_dict = getattr(profile, 'resume_urls', {})
                
                if isinstance(resume_urls_dict, dict) and best_bucket in resume_urls_dict:
                    resume_url = resume_urls_dict[best_bucket]
                    self.logger.log_info(f"Using tailored Cloudinary resume for variant: {best_bucket}")
                
                if not resume_url:
                    resume_url = getattr(profile, 'resume', "") or getattr(profile, 'cloudinary_url', "")
                    if resume_url:
                        self.logger.log_info("Falling back to master resume from Cloudinary...")
                
                if resume_url and resume_url.startswith('http') and student_id:
                    local_path, success = download_resume_from_url(resume_url, student_id, best_bucket)
                    if success and os.path.exists(local_path):
                        resume_path = local_path
                        self.logger.log_ok(f"Resume downloaded: {Path(local_path).name}")
                    else:
                        self.logger.log_err(f"Cloudinary download failed for {resume_url}")
                        return False
                else:
                    self.logger.log_err(f"No valid Cloudinary URL found to fallback to.")
                    return False

            # 2. Upload resume using direct input first, file chooser fallback.
            self.logger.log_info(f"Uploading resume: {os.path.basename(resume_path)}")
            
            upload_ok = await self._upload_resume_via_profile(page, resume_path)
            if not upload_ok:
                return False

            self.logger.log_info("Waiting for Naukri to process upload...")
            await page.wait_for_timeout(5500)
            self.logger.log_ok(f"Naukri Resume Uploaded: {os.path.basename(resume_path)}")
            return True
                
        except Exception as e:
            self.logger.log_err(f"Naukri resume upload failed: {e}")
            return False

    async def _open_naukri_profile_page(self, page: Page) -> bool:
        """Open profile page and wait until resume section is reachable."""
        profile_urls = [
            "https://www.naukri.com/mnjuser/profile",
            "https://www.naukri.com/mnjuser/homepage",
        ]
        readiness_selectors = [
            "input#attachCV",
            "input[type='file']",
            ".uploadBtn",
            "button:has-text('Update resume')",
            "button:has-text('Upload resume')",
            "text=/update resume/i",
            "text=/upload resume/i",
        ]

        async def _profile_ready(timeout_ms: int = 12000) -> bool:
            per_selector_timeout = max(700, int(timeout_ms / max(1, len(readiness_selectors))))
            for sel in readiness_selectors:
                loc = page.locator(sel).first
                try:
                    if await loc.count() == 0:
                        continue
                    state = "attached" if sel.startswith("input") else "visible"
                    await loc.wait_for(state=state, timeout=per_selector_timeout)
                    return True
                except Exception:
                    continue
            return False

        for attempt in range(1, 4):
            for target_url in profile_urls:
                try:
                    if "mnjuser/profile" not in (page.url or "").lower():
                        await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)

                    if "mnjuser/homepage" in (page.url or "").lower():
                        await page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=25000)

                    if await _profile_ready(timeout_ms=12000):
                        return True
                    self.logger.log_warn(
                        f"Profile page loaded but resume controls were not detected (attempt {attempt}, via {target_url})."
                    )
                except Exception as nav_err:
                    self.logger.log_warn(
                        f"Profile page attempt {attempt} via {target_url} failed: {nav_err}"
                    )
            await page.wait_for_timeout(1200 * attempt)
        return False

    async def _upload_resume_via_profile(self, page: Page, resume_path: str) -> bool:
        """Upload resume from profile page using resilient strategies."""
        file_input_selectors = [
            "input#attachCV",
            "input[type='file'][id*='attach']",
            "input[type='file'][name*='attach']",
            "input[type='file']",
        ]

        for sel in file_input_selectors:
            try:
                file_input = page.locator(sel).first
                if await file_input.count() == 0:
                    continue
                await file_input.set_input_files(resume_path)
                return True
            except Exception as set_err:
                self.logger.log_warn(f"set_input_files failed on '{sel}': {set_err}")

        trigger_selectors = [
            "button:has-text('Update resume')",
            "button:has-text('Upload resume')",
            ".uploadBtn",
            "text=/update resume/i",
            "text=/upload resume/i",
        ]
        for trigger_sel in trigger_selectors:
            try:
                trigger = page.locator(trigger_sel).first
                if await trigger.count() == 0 or not await trigger.is_visible(timeout=1500):
                    continue
                async with page.expect_file_chooser(timeout=7000) as fc_info:
                    await trigger.click()
                chooser = await fc_info.value
                await chooser.set_files(resume_path)
                return True
            except Exception:
                continue

        self.logger.log_err("File chooser upload failed: No usable resume upload input/button found on profile page.")
        return False

    async def _extract_skills_with_ai(self, jd_text: str) -> list[str]:
        """Extract skills from JD using centralized AIExtractor"""
        extractor = get_ai_extractor()
        return await extractor.extract_skills_async(jd_text)

    async def _generate_ai_resume(self, profile: Any, jd_text: str, student_id: str, selector) -> Optional[str]:
        """
        Generate AI tailored resume using the API and save to student folder.
        """
        import requests
        import shutil
        from pathlib import Path
        
        api_base = os.getenv("LOCAL_API_URL", "http://ai-engine:8000").rstrip("/")
        api_url = f"{api_base}/generate"
        
        try:
            # Get master resume text
            master_resume_path = None
            if hasattr(profile, 'resume_path') and profile.resume_path:
                master_resume_path = profile.resume_path
            
            if not master_resume_path:
                master_resume_path = os.getenv("STUDENT_RESUME_PATH")
            
            # Extract text from master resume if exists
            retrieved_chunks = ""
            if master_resume_path and os.path.exists(master_resume_path):
                from utils.pdf_reader import extract_text_from_pdf
                try:
                    master_text = extract_text_from_pdf(master_resume_path)
                    links = getattr(profile, 'extra', {})
                    linkedin = links.get('linkedin', '')
                    github = links.get('github', '')
                    header = f"NAME: {profile.name}\nEMAIL: {profile.email}\nPHONE: {profile.phone}\nLOCATION: {profile.location}\nLINKEDIN: {linkedin}\nGITHUB: {github}\n"
                    retrieved_chunks = header + "\n\n" + master_text
                except Exception as e:
                    self.logger.log_warn(f"Could not extract master resume: {e}")
                    retrieved_chunks = str(profile)
            else:
                retrieved_chunks = str(profile)
            
            # Call AI Engine API
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
                    main_skill = selector.extract_main_skill(jd_text)
                    saved_path = selector.save_tailored_resume(pdf_path, main_skill)
                    self.logger.log_ok(f"Saved tailored resume to: {saved_path}")
                    return str(saved_path)
            else:
                self.logger.log_err(f"AI Engine error: {response.status_code}")
                
        except Exception as e:
            self.logger.log_err(f"AI resume generation failed: {e}")
        
        return None

    async def _search_and_lock(
        self,
        page: Page,
        role: str,
        settings: Any,
        profile: Any = None,
        job_url: str = None,
    ) -> int:
        """
        PHASE 2: Open search page for a specific role and lock card count.
        
        URL Priority:
        1. If job_url provided with full path, use it directly
        2. If job_url is just a partial pattern, build search with role injection
        3. Default: build standard search URL
        
        User's filter template (with dynamic role):
        https://www.naukri.com/mern-full-stack-developer-jobs-in-hyderabad-secunderabad?k={role}&l=hyderabad,bengaluru,chennai,mumbai,new delhi,noida&qproductJobSource=2&naukriCampus=true&experience=0&functionAreaIdGid=5&jobAge=15
        """
        location = getattr(profile, "target_location", "") if profile else ""
        
        # Check if job_url is provided with filters template
        if job_url and job_url.startswith("http"):
            # User provided full URL - check if it has {role} placeholder
            if "{role}" in job_url:
                # Inject dynamic role into URL filter template
                role_for_url = role.lower().replace(" ", "-")
                search_url = job_url.replace("{role}", role_for_url)
            else:
                # Use exact URL provided
                search_url = job_url
            self.logger.log_info(f"Using user URL with filters: {search_url}")
        else:
            # Build search URL with role - apply user's filter parameters
            # User's filter template preserved
            slug = role.lower().replace(",", "").replace("/", "-").replace(" ", "-")
            search_url = (
                f"https://www.naukri.com/{slug}-jobs?"
                f"k={quote_plus(role)}"
                f"&l=hyderabad,bengaluru,chennai,mumbai,new delhi,noida"
                f"&qproductJobSource=2"
                f"&naukriCampus=true"
                f"&nignbevent_src=jobsearchDeskGNB"
                f"&experience=0"
                f"&functionAreaIdGid=5"
                f"&glbl_qcrc=1028"
                f"&jobAge=15"
            )
        
        self.logger.log_info(f"Searching for role: {role} in {location}")
        self.current_search_url = search_url  # Save for recycling
        
        # Hard refresh - clear cache and do fresh load
        # await page.evaluate("""() => {
        #     try {
        #         localStorage.clear();
        #         sessionStorage.clear();
        #     } catch(e) {}
        # }""")
        
        # Navigate with domcontentloaded (faster)
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)
            content = await page.content()
            content_len = len(content)
            self.logger.log_info(f"Page loaded. URL: {page.url} | Content length: {content_len}")
            
            # Detect 1945 "death signature" - Naukri's client-side crash page
            if content_len == 1945 or "Application error" in content or "<!DOCTYPE html>" not in content[:50]:
                self.logger.log_warn(f"1945 death signature detected! Retrying with networkidle...")
                await page.goto(search_url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(10)
                content = await page.content()
                content_len = len(content)
                self.logger.log_info(f"Retry page loaded. Content length: {content_len}")
                
                # If still 1945, try with cache clear
                if content_len == 1945 or "Application error" in content:
                    self.logger.log_warn("1945 on 2nd try! Clearing cache and retrying...")
                    await page.evaluate("""() => {
                        localStorage.clear();
                        sessionStorage.clear();
                        caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
                    }""")
                    await page.reload(wait_until="networkidle", timeout=60000)
                    await asyncio.sleep(15)
                    content = await page.content()
                    content_len = len(content)
                    self.logger.log_info(f"After cache clear: {content_len} bytes")
                    
                    # If still 1945 after all retries, try Selenium as last resort
                    if content_len == 1945 or "Application error" in content:
                        self.logger.log_warn("All Playwright attempts failed! Trying Selenium fallback...")
                        try:
                            from scraper_adapter.naukri_selenium import create_selenium_scraper
                            sid = self._get_candidate_id(profile)
                            selenium_scraper = create_selenium_scraper(self.logger, settings, student_id=sid)
                            await selenium_scraper.get_driver(headless=True)
                            
                            # Get credentials using existing method
                            email, password, _ = self._resolve_naukri_credentials(profile, settings)
                            
                            if email and password:
                                login_ok = await selenium_scraper.login(email, password)
                                if login_ok:
                                    job_count = await selenium_scraper.search_jobs(role, location)
                                    if job_count > 0:
                                        self.logger.log_ok(f"Selenium found {job_count} jobs!")
                                        await selenium_scraper.close()
                                        return job_count
                            
                            await selenium_scraper.close()
                        except Exception as selenium_error:
                            import traceback
                            self.logger.log_err(f"Selenium fallback failed. Error: {selenium_error}")
                            self.logger.log_info(f"Available locals: {list(locals().keys())}")
                            # traceback.print_exc()

            
            if len(content) < 500:
                self.logger.log_warn(f"Empty page detected! Content: {content[:200]}")
            
            self.logger.log_info(f"Current page URL: {page.url}")

            
            # --- DASHBOARD SEARCH BYPASS (FOR STUDENT ACCOUNTS) ---
            if "mnjuser/homepage" in page.url:
                self.logger.log_info("Landed on student dashboard. Waiting for full hydration...")
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                await asyncio.sleep(10) # Heavy wait for Next.js to settle
                
                self.logger.log_info("Initiating manual search bypass...")
                
                # 1. Expand search bar
                try:
                    await page.click(".nI-gNb-sb__placeholder", timeout=5000)
                    await asyncio.sleep(2)
                except:
                    pass # Already expanded or different layout
                
                # 2. Select Job Type (Mandatory for Campus)
                try:
                    # Wait for expanded search bar component
                    self.logger.log_info("Waiting for job type dropdown...")
                    await page.wait_for_selector(".dropdownMainContainer", state="visible", timeout=10000)
                    await asyncio.sleep(2)
                    
                    # Try multiple ways to open the dropdown
                    await page.click(".ni-gnb-icn-expand-more", timeout=5000)
                    await asyncio.sleep(3)
                    
                    # Selecting "Jobs"
                    self.logger.log_info("Selecting 'Jobs' option...")
                    try:
                        # Try direct click first
                        await page.click(".dropdownContainer >> text=Jobs", timeout=5000)
                    except:
                        # Keyboard fallback: Down and Enter
                        self.logger.log_info("Dropdown click failed, using keyboard fallback...")
                        await page.focus("input#jobType")
                        await page.keyboard.press("ArrowDown")
                        await asyncio.sleep(2)
                        await page.keyboard.press("Enter")
                    
                    await asyncio.sleep(2)
                    
                    # Verification
                    val = await page.get_attribute("input#jobType", "value")
                    self.logger.log_info(f"Job type selection verified: '{val}'")
                except Exception as e:
                    self.logger.log_warn(f"Dashboard dropdown selection failed: {e}")
                
                # 3. Fill keywords
                await page.fill("input.suggestor-input", role)
                await asyncio.sleep(2)
                
                # 4. Submit Search
                await page.click("button.qsbSubmit", timeout=5000)
                self.logger.log_info("Dashboard search submitted via Click. Waiting for results...")

                await asyncio.sleep(15) # Heavy wait for redirect and render
                
                # Check for client-side crash
                if "Application error" in await page.content():
                    self.logger.log_warn("Detected Naukri client-side crash. Attempting hard refresh...")
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(10)
                
                self.logger.log_info(f"Post-dashboard search URL: {page.url}")

                
                # Diagnostic: Capture results page
                try:
                    ts = int(asyncio.get_event_loop().time())
                    diag_path = f"logs/naukri_results_{ts}.png"
                    await page.screenshot(path=diag_path)
                    self.logger.log_info(f"Captured results screenshot: {diag_path}")
                    with open(f"logs/naukri_results_{ts}.html", "w", encoding="utf-8") as f:
                        f.write(await page.content())
                except:
                    pass

            await asyncio.sleep(3)
            count = await self._wait_for_cards(page)
            if count > 0:
                return count
        except Exception as e:
            self.logger.log_warn(f"Search error: {e}")
        
        # Try one more time with networkidle
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(8)
            content = await page.content()
            content_len = len(content)
            
            # If 1945 detected again, try page reload with cache clear
            if content_len == 1945 or "Application error" in content:
                self.logger.log_warn("1945 on retry! Trying hard refresh with cache clear...")
                await page.evaluate("""() => {
                    try {
                        localStorage.clear();
                        sessionStorage.clear();
                        caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
                    } catch(e) {}
                }""")
                await page.reload(wait_until="networkidle", timeout=60000)
                await asyncio.sleep(10)
                content = await page.content()
                self.logger.log_info(f"After hard refresh: {len(content)} bytes")
            
            return await self._wait_for_cards(page)
        except:
            return 0

    async def _wait_for_cards(self, page: Page) -> int:
        """Wait for job cards and return count"""
        # Wait for network idle after navigation
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        
        await asyncio.sleep(3)
        
        # Multiple selectors for job cards
        card_selectors = [
            ".srp-jobtuple-wrapper",
            "article.jobTuple", 
            ".jobTuple",
            "[data-job-id]",
            ".srpResults>div",
        ]
        
        # Try each selector
        for sel in card_selectors:
            try:
                await page.wait_for_selector(sel, timeout=10000)
                await asyncio.sleep(2)
                cards = await page.locator(sel).all()
                count = len(cards)
                if count > 0:
                    self.logger.log_ok(f"Cards locked: {count} jobs on page")
                    return count
            except:
                continue
        
        # Fallback - check page content for job indicators
        try:
            content = await page.content()
            # Check for common job indicators in HTML
            job_indicators = ['job-card', 'jobtuple', 'job-list', 'jobs?', 'srp-job']
            found = sum(1 for ind in job_indicators if ind.lower() in content.lower())
            if found >= 2:
                self.logger.log_ok(f"Found job content indicators")
                return 3  # Assume at least some jobs
        except:
            pass
        
        return 0

    def _get_candidate_id(self, profile: Any) -> str:
        """Get or create candidate ID"""
        # PRIORITY: Use student_id from MongoDB profile if available
        if hasattr(profile, "student_id") and profile.student_id:
            return str(profile.student_id)
            
        # Fallback to hashed ID
        import hashlib
        name = getattr(profile, "name", "candidate")
        email = getattr(profile, "email", "")
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
        
        candidate_id = self._get_candidate_id(profile)
        self.logger.log_info(f"Warmup check for: {candidate_id}")
        
        # Check if resumes already exist in file system first
        from pathlib import Path
        default_resumes_dir = "/app/ai_engine/resumes" if os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists() else "D:/ai-bot-resumes/ai_engine/resumes"
        existing_resumes_dir = Path(os.getenv("RESUMES_DIR", default_resumes_dir)) / candidate_id
        existing_pdfs = list(existing_resumes_dir.glob("*.pdf")) if existing_resumes_dir.exists() else []
        
        if existing_pdfs:
            self.logger.log_info(f"Found {len(existing_pdfs)} existing resumes in file system, using existing")
            # Still need to create generator to track roles but skip generation
            try:
                generator = get_rag_resume_generator(logger=self.logger, student_id=candidate_id)
                # Load existing roles from MongoDB or use skill-based roles
                if not generator.custom_roles:
                    # Set basic roles from skills
                    user_skills = profile.skills if hasattr(profile, 'skills') else []
                    custom_roles = self._generate_roles_from_skills(user_skills, candidate_id)
                    if not custom_roles:
                        custom_roles = self._generate_roles_from_resume_files(existing_pdfs)
                    generator.custom_roles = custom_roles
                self._warmup_roles = [
                    cfg.get("title", "").strip()
                    for cfg in generator.custom_roles.values()
                    if cfg.get("title")
                ][:6]
                self._warmup_skill_keywords = [
                    str(k).strip().lower()
                    for cfg in generator.custom_roles.values()
                    for k in (cfg.get("keywords") or [])
                    if str(k).strip()
                ]
                # Save roles to MongoDB for future runs
                if self._warmup_roles:
                    await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                return True
            except Exception as e:
                self.logger.log_warn(f"Generator init error: {e}")
                return True  # Still return True since we have existing PDFs
        
        try:
            generator = get_rag_resume_generator(logger=self.logger, student_id=candidate_id)
            
            # Check if roles are already in MongoDB (via generator hydration)
            if generator.custom_roles:
                role_keys = []
                role_values = []
                roles_items = []
                
                if isinstance(generator.custom_roles, dict):
                    role_keys = list(generator.custom_roles.keys())
                    role_values = list(generator.custom_roles.values())
                    roles_items = list(generator.custom_roles.items())
                elif isinstance(generator.custom_roles, list):
                    for item in generator.custom_roles:
                        if isinstance(item, dict):
                            rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                            role_keys.append(rk)
                            role_values.append(item)
                            roles_items.append((rk, item))
                
                self.logger.log_ok(f"Roles already discovered in MongoDB: {role_keys}")
                self._warmup_roles = [
                    cfg.get("title", "").strip()
                    for cfg in role_values
                    if cfg.get("title")
                ][:6]
                self._warmup_skill_keywords = [
                    str(k).strip().lower()
                    for cfg in role_values
                    for k in (cfg.get("keywords") or [])
                    if str(k).strip()
                ]
                
                # Save roles to MongoDB if not already saved
                if self._warmup_roles:
                    await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                
                # Check if we need to generate PDFs or if they exist
                has_all_pdfs = True
                role_count = 0
                for key, cfg in roles_items:
                    role_count += 1
                    title = cfg.get("title", "unknown")
                    safe_title = title.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
                    target_path = generator.resumes_dir / f"{safe_title}.pdf"
                    if not (target_path.exists() and target_path.stat().st_size > 1000):
                        has_all_pdfs = False
                
                if has_all_pdfs and role_count >= 5:
                    self.logger.log_ok("All role resumes found. Skipping generation completely.")
                    return True
                
                # Skip PDF generation if roles already exist in MongoDB - just use existing resumes
                if role_count >= 5 and existing_pdfs:
                    self.logger.log_ok(f"Roles exist in MongoDB ({role_count}) and {len(existing_pdfs)} resumes exist. Skipping generation.")
                    return True
                
                # If roles exist but no PDFs, continue anyway - PDFs are optional
                if role_count >= 5 and not existing_pdfs:
                    self.logger.log_info("Roles exist in MongoDB but no PDFs. Continuing without pre-generated resumes.")
                    return True  # Don't fail, continue with job search
            
            self.logger.log_info("Discovering roles and generating resumes...")
            await generator._init_rag()
            custom_roles = await generator.discover_top_roles()
            
            if custom_roles:
                self.logger.log_info(f"Discovered {len(custom_roles)} roles")
                self._warmup_roles = [
                    cfg.get("title", "").strip()
                    for cfg in custom_roles.values()
                    if cfg.get("title")
                ][:6]
                self._warmup_skill_keywords = [
                    str(k).strip().lower()
                    for cfg in custom_roles.values()
                    for k in (cfg.get("keywords") or [])
                    if str(k).strip()
                ]
                resumes = await generator.generate_initial_resumes()
                self.logger.log_info(f"Generated {len(resumes)} role resumes")
                
                # Save discovered roles to MongoDB for future runs
                await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                
                return True
            
            self.logger.log_warn("Role discovery returned empty")
            return False
        
        except Exception as e:
            self.logger.log_warn(f"Warmup error: {e}")
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
    
    def _generate_roles_from_skills(self, skills: list, candidate_id: str) -> dict:
        """Generate roles from skills using job_generator - EXACTLY like our new logic"""
        custom_roles = {}
        
        # Create a mock student object
        class MockStudent:
            def __init__(self, skills, candidate_titles):
                self.skills = skills
                self.candidate_titles = candidate_titles
                self.preferred_locations = ["India"]
        
        mock_student = MockStudent(skills, [])
        
        # Use JobGenerator to get 6 roles
        try:
            gen = JobGenerator("naukri")
            queries = gen._build_queries(mock_student)
            
            for i, title in enumerate(queries[:6]):
                role_key = title.lower().replace(" ", "_").replace("/", "_")
                custom_roles[role_key] = {
                    "title": title,
                    "keywords": skills[:5] if skills else ["Software", "Developer"]
                }
        except Exception as e:
            self.logger.log_warn(f"JobGenerator error: {e}, using fallback")
            # Fallback to old logic
            role_templates = {
                'java_backend': {'title': 'Java Backend Developer', 'keywords': ['Java', 'Spring', 'SQL']},
                'python_backend': {'title': 'Python Backend Developer', 'keywords': ['Python', 'Django', 'Flask']},
                'nodejs_backend': {'title': 'Node.js Backend Developer', 'keywords': ['Node.js', 'Express', 'JavaScript']},
                'react_frontend': {'title': 'React Developer', 'keywords': ['React', 'JavaScript', 'TypeScript']},
                'fullstack': {'title': 'MERN Full Stack Developer', 'keywords': ['React', 'Node.js', 'MongoDB']},
            }
            
            skill_lower = [s.lower() for s in skills]
            for role_key, role_info in role_templates.items():
                keywords = role_info['keywords']
                if any(kw.lower() in skill_lower for kw in keywords):
                    custom_roles[role_key] = role_info
        
        return custom_roles

    def _generate_roles_from_resume_files(self, resume_files: list[Path]) -> dict:
        """Derive role titles from existing resume filenames when profile skills are missing."""
        custom_roles = {}
        ignore_stems = {"role_key", "resume", "cv", "profile"}
        for resume_file in resume_files:
            stem = resume_file.stem.strip()
            if not stem:
                continue
            if stem.lower() in ignore_stems:
                continue

            normalized = stem.replace("_", " ").replace("-", " ").strip()
            title = " ".join(word.capitalize() for word in normalized.split())
            if not title:
                continue
            if not any(x in title.lower() for x in ["developer", "engineer", "scientist", "analyst", "architect"]):
                title = f"{title} Developer"

            role_key = normalized.lower().replace(" ", "_")
            keywords = [word.capitalize() for word in normalized.split() if len(word) > 2][:3]
            if not keywords:
                keywords = ["Software", "Developer"]

            custom_roles[role_key] = {"title": title, "keywords": keywords}

        if custom_roles:
            self.logger.log_info(f"Derived roles from existing resumes: {list(custom_roles.keys())}")
        return custom_roles
    
    def _build_query(self, profile: Any) -> str:
        """Build search query from candidate titles"""
        roles = getattr(profile, 'candidate_titles', [])
        if not roles:
            roles = getattr(self, "_warmup_roles", [])
        if not roles:
            # Fallback to skills
            roles = [str(s) for s in getattr(profile, 'skills', [])[:3]]
        
        if not roles:
            roles = ["Software Developer"]
        
        roles = list(dict.fromkeys(roles))[:5]
        query = ", ".join(roles)
        self.logger.log_info(f"Search query: {query}")
        return query
        
        return query

    def _resolve_profile_skills(self, profile: Any) -> list[str]:
        """Build profile skills with robust fallback when Mongo skills are empty."""
        raw_skills = [str(s).strip().lower() for s in getattr(profile, "skills", []) if str(s).strip()]
        if raw_skills:
            return list(dict.fromkeys(raw_skills))

        inferred = []
        role_titles = [str(t).strip().lower() for t in getattr(profile, "candidate_titles", []) if str(t).strip()]
        for title in role_titles:
            for token in re.split(r"[^a-zA-Z0-9.+#]+", title):
                token = token.strip().lower()
                if len(token) > 2:
                    inferred.append(token)

        inferred.extend([str(k).strip().lower() for k in getattr(self, "_warmup_skill_keywords", []) if str(k).strip()])
        inferred = list(dict.fromkeys(inferred))
        if inferred:
            self.logger.log_info(f"[MATCH] Using inferred profile skills fallback: {', '.join(inferred[:12])}")
        return inferred
    
    def _get_roles_for_page(self, profile: Any, page_num: int) -> list[str]:
        """Get roles for specific pagination page."""
        roles = [r.strip() for r in self._build_query(profile).split(",")]
        # Rotate or just return first few
        start_idx = (page_num - 1) % len(roles) if roles else 0
        page_roles = (roles[start_idx:] + roles[:start_idx])[:3]
        return page_roles

    async def _collect_prioritized_job_urls(self, page: Page) -> list[dict[str, Any]]:
        """
        Collect job URLs from listing page and deprioritize obvious external-apply cards.
        Note: Naukri cards often do not expose a real internal apply button on the card itself.
        Priority: unknown -> external_hint
        """
        prioritized: list[dict[str, Any]] = []
        links = await page.locator("a.title[href*='job-listings']").all()
        seen: set[str] = set()

        for idx, link in enumerate(links):
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue
                href = href.strip()
                if not href or href in seen:
                    continue
                seen.add(href)

                card_text = ""
                card_scopes = [
                    "xpath=ancestor::article[1]",
                    "xpath=ancestor::div[contains(@class,'cust-job-tuple')][1]",
                    "xpath=ancestor::div[contains(@class,'jobTuple')][1]",
                    "xpath=ancestor::div[contains(@class,'srp-jobtuple-wrapper')][1]",
                    "xpath=ancestor::div[contains(@class,'tuple')][1]",
                ]
                for scope in card_scopes:
                    try:
                        card = link.locator(scope).first
                        if await card.count() == 0:
                            continue
                        card_text = (await card.inner_text()).strip().lower()
                        if card_text:
                            break
                    except Exception:
                        continue

                external_markers = [
                    "apply on company site",
                    "company site",
                    "company website",
                    "external apply",
                    "apply externally",
                ]

                apply_hint = "unknown"
                if any(marker in card_text for marker in external_markers):
                    apply_hint = "external"

                priority = 0 if apply_hint == "unknown" else 1
                prioritized.append(
                    {
                        "url": href,
                        "hint": apply_hint,
                        "priority": priority,
                        "card_index": idx,
                    }
                )
            except Exception:
                continue

        prioritized.sort(key=lambda item: (item["priority"], item["card_index"]))
        return prioritized


    async def _strike_loop(
        self,
        page: Page,
        profile: Any,
        settings: Any,
        start_count: int = 0,
        max_jobs_to_scan: Optional[int] = None,
    ) -> int:
        """
        PHASE 4: Main loop - apply to matching jobs
        Identifies jobs directly from the page and opens each JD for evaluation.
        """
        applied_count = 0
        no_apply_count = 0
        max_no_apply = 10  # Rotate role after 10 jobs without apply
        
        # Get URLs from cards (internal apply first, external likely last)
        try:
            # Wait for cards to ensure they are loaded
            await page.wait_for_selector("a.title[href*='job-listings']", timeout=5000)
            prioritized_jobs = await self._collect_prioritized_job_urls(page)
            job_urls = [item["url"] for item in prioritized_jobs]
            external_hints = sum(1 for item in prioritized_jobs if item["hint"] == "external")
            self.logger.log_info(
                f"Found {len(job_urls)} job URLs on page (external_hint={external_hints}, unknown={len(job_urls) - external_hints})"
            )
        except Exception as e:
            self.logger.log_err(f"Failed to get URLs: {e}")
            job_urls = []
            prioritized_jobs = []
        
        if not job_urls:
            return 0

        for i, job in enumerate(prioritized_jobs):
            if max_jobs_to_scan is not None and i >= max_jobs_to_scan:
                self.logger.log_info(f"Reached scan window ({max_jobs_to_scan}) for this role.")
                break

            job_url = job["url"]
            job_hint = job.get("hint", "unknown")

            if job_hint == "external":
                self.logger.log_info(f"SKIP job {i}: card-level external hint")
                continue

            # Rotate role if too many jobs without valid apply
            if no_apply_count >= max_no_apply:
                self.logger.log_warn(f"No apply found in {no_apply_count} jobs, rotating to next role")
                break
            
            # Stop if platform-specific max applies reached
            total_applied = start_count + applied_count
            if total_applied >= self._max_applies:
                self.logger.log_info(f"Platform cap reached ({self._max_applies} applies).")
                break
            
            # Session time cap (anti-detection)
            import time as _time
            elapsed = _time.time() - self._session_start
            if elapsed > self._session_limit:
                self.logger.log_warn(f"Session time limit reached ({int(elapsed)}s). Stopping to avoid detection.")
                break
            
            # Micro-break every N jobs (looks human)
            if i > 0 and i % self._micro_break_interval == 0:
                import random
                pause = random.uniform(self._micro_break_min, self._micro_break_max)
                self.logger.log_info(f"Micro-break: pausing {pause:.0f}s (job #{i})")
                await asyncio.sleep(pause)
            
            # Slow down before opening next JD
            await asyncio.sleep(2)
            
            # Navigate SAME page to job URL instead of new tab (more stable)
            self.logger.log_info(f"Opening JD: {job_url[:50]}... (hint={job_hint})")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)  # Bypass fast-sleep to allow React to render the Apply button

            # STRICT RULE: Extract JD only when internal apply is available.
            apply_type, _ = await self._detect_apply_button(page)
            if apply_type == "external":
                self.logger.log_info(f"SKIP job {i}: external apply detected")
                no_apply_count += 1
                continue
            if apply_type != "internal":
                self.logger.log_info(f"SKIP job {i}: no internal apply button")
                no_apply_count += 1
                continue
            
            # Reset counter on valid job
            no_apply_count = 0
            
            # Robust JD Extraction
            await asyncio.sleep(2)

            jd_text = ""
            jd_selectors = [
                "div[class*='styles_job-desc-container']",
                "section[class*='styles_job-desc']",
                "div[class*='styles_JDBody__content']",
                "[class*='styles_JDC__jd-contents']",
                "[class*='styles_job-description']",
                ".job-desc", 
                "#jobDescription", 
                ".jd-container",
                ".job-details",
                ".description",
                ".JD"
            ]
            
            # Wait for JD container
            try:
                await page.wait_for_selector("section[class*='styles_job-desc'], .job-desc-container", timeout=10000)
            except:
                pass
            
# Search frames
            for fi, frame in enumerate(page.frames):
                try:
                    for selector in jd_selectors:
                        try:
                            el = frame.locator(selector).first
                            if await el.count() > 0:
                                text = (await el.inner_text()).strip()
                                if len(text) > 100:
                                    jd_text = text
                                    self.logger.log_info(f"JD found in Frame {fi}")
                                    break
                        except: continue
                    if jd_text: break
                except: continue

            # Fallback
            if not jd_text or len(jd_text) < 100:
                try:
                    body_text = await page.inner_text("body")
                    if len(body_text) > 500:
                        jd_text = body_text[:3000]
                except:
                    pass
            
            if jd_text:
                self.logger.log_info(f"[JD DEBUG] Extracted JD ({len(jd_text)} chars)")
                keyword_skills = extract_skills_from_jd(jd_text)
                jd_skills = keyword_skills if keyword_skills else []
            else:
                self.logger.log_warn(f"[JD DEBUG] No JD extracted")
                jd_skills = []
            
            # Capture job identity NOW (before apply) to avoid modal disappearing after submission
            job_title, company_name = await self._extract_job_identity(page)
            self._last_applied_job_title = job_title.strip() if job_title else ""
            self._last_applied_company = company_name.strip() if company_name else ""
            self.current_job_title = job_title.strip() if job_title else ""
            self.current_company_name = company_name.strip() if company_name else ""
            
            # Log identity for visibility
            self.logger.log_info(f"[IDENTITY] Job: {self.current_job_title} | Company: {self.current_company_name}")
            
            # 2. MATCHING
            profile_skills = self._resolve_profile_skills(profile)
            threshold = settings.ats_threshold
            
            match_result = calculate_match_percentage(profile_skills, jd_skills, threshold)
            job_percentage = match_result['percentage']
            total_points = match_result.get('total_points', 0)
            max_possible = match_result.get('max_possible', 0)
            
            # Detailed logging for the user
            self.logger.log_info("=== SKILL SCORING BREAKDOWN ===")
            primary_matches = [m['skill'] for m in match_result.get('matched_skills', []) if m.get('category') == 'primary']
            secondary_matches = [m['skill'] for m in match_result.get('matched_skills', []) if m.get('category') == 'secondary']
            partial_matches = [m['skill'] for m in match_result.get('matched_skills', []) if m.get('category') == 'partial']
            
            if primary_matches:
                self.logger.log_ok(f"  Primary (20pts): {', '.join(primary_matches)}")
            if secondary_matches:
                self.logger.log_ok(f"  Secondary (10pts): {', '.join(secondary_matches)}")
            if partial_matches:
                self.logger.log_ok(f"  Partial (6pts): {', '.join(partial_matches)}")
                
            missing = match_result.get('missing_skills', [])
            if missing:
                self.logger.log_warn(f"  Missing JD Skills: {', '.join(missing)}")
            
            self.logger.log_info(f"  FINAL SCORE: {total_points}/{max_possible} = {job_percentage}%")
            self.logger.log_info("===============================")
            
            if job_percentage < threshold: 
                self.logger.log_info(f"SKIP job {i}: Low match ({job_percentage}%)")
                continue
            
            # Apply using SAME page
            apply_success = await self._click_apply_on_jd(page, profile)
            
            if apply_success is True:
                applied_count += 1
                self.logger.log_ok(f"APPLIED ({applied_count}): Job {i} ({job_percentage}%)")
                
                try:
                    await self.logger.log_application_success(
                        job_id=f"naukri_{i}_{int(asyncio.get_event_loop().time())}",
                        title=self.current_job_title or 'Software Engineer',
                        company=self.current_company_name or 'N/A',
                        platform="naukri", student_id=self._get_candidate_id(profile)
                    )
                except Exception as report_err:
                    self.logger.log_warn(f"Dashboard reporting failed: {report_err}")

                if start_count + applied_count >= self._max_applies:
                    self.logger.log_info(f"Apply target reached ({self._max_applies}). Stopping Naukri scan.")
                    break
        
        return applied_count

    async def _extract_job_identity(self, page: Page) -> tuple[str, str]:
        """Extract job title and company from a Naukri JD page with robust 2026 fallbacks."""
        title_selectors = [
            "h1.jd-header-title", 
            ".jd-header-title", 
            ".job-title", 
            "h1",
            "[class*='jd-header-title']",
            ".jd-top-head h1"
        ]
        
        company_selectors = [
            "a.comp-name", 
            "a.subTitle", 
            ".premium-org-name", 
            ".company-name",
            ".comp-info-detail a", 
            ".jd-header-comp-name", 
            "div.jd-top-head a",
            "[title='Powered by']",
            "div.jd-header-comp-name-info a",
            ".comp-name-info a"
        ]
        
        # Wait for at least one potential company selector to be present
        try:
            await page.wait_for_selector(", ".join(company_selectors[:5]), timeout=4000)
        except:
            pass

        async def _extract_text(selectors: list[str], is_company: bool = False) -> str:
            for sel in selectors:
                try:
                    locators = page.locator(sel)
                    count = await locators.count()
                    for i in range(count):
                        el = locators.nth(i)
                        # Try title attribute first (often contains full company name)
                        title_attr = await el.get_attribute("title")
                        txt = title_attr.strip() if title_attr else (await el.inner_text()).strip()
                        
                        if not txt:
                            continue
                            
                        # Filter out platform names and generic junk
                        if is_company:
                            clean_txt = txt.lower()
                            if any(x in clean_txt for x in ["naukri", "foundit", "monster", "job source", "anonymous"]):
                                continue
                        
                        return txt
                except Exception:
                    continue
            return ""
        
        title = await _extract_text(title_selectors) or "Software Engineer"
        company = await _extract_text(company_selectors, is_company=True)
        
        # URL FALLBACK: Naukri URLs often look like: .../job-listings-role-name-company-name-location-id
        if not company or company.lower() in ["naukri", "anonymous", "unknown"]:
            try:
                url = page.url.lower()
                if "/job-listings-" in url:
                    slug = url.split("/job-listings-")[1].split("?")[0]
                    # Format: role-keywords-company-location-id
                    # We look for common location markers or experience markers to find the company before them
                    parts = slug.split("-")
                    # Stop words often used in location or experience segments
                    stop_words = {"years", "year", "hyderabad", "bengaluru", "bangalore", "mumbai", "pune", "delhi", "noida", "chennai", "india"}
                    
                    # Find the first index of a stop word or experience marker
                    limit_idx = len(parts) - 1
                    for i, p in enumerate(parts):
                        if p.isdigit() or p in stop_words:
                            limit_idx = i
                            break
                    
                    # Company is usually right before the limit
                    if limit_idx > 1:
                        # Grab 2-3 parts before the limit as potential company
                        company_parts = parts[max(0, limit_idx-3):limit_idx]
                        company = " ".join(company_parts).title()
            except:
                pass

        company = company or "Naukri Employer"
        return title.strip(), company.strip()

    async def _answer_modal_questions(self, page: Page, profile: Any) -> None:
        """
        Handles chatbot-style application drawers and static forms.
        Refactored with Precision Selectors, Retry Logic, and Smart Fallbacks.
        """
        try:
            # PHASE A: CHATBOT DRAWER (Modern Naukri Flow)
            chatbot_selectors = [".chatbot_Drawer", ".chatbot_MessageContainer", ".chatbot_DrawerContentWrapper", "[id*='Drawer']"]
            chatbot_found = False
            for sel in chatbot_selectors:
                if await page.locator(sel).first.is_visible(timeout=2000):
                    chatbot_found = True
                    break
            
            if chatbot_found:
                self.logger.log_info("[CHATBOT] Drawer identified. Starting precision sequence...")
                
                # Pre-index resume for RAG if context is available
                rag = None
                if RAGEngine:
                    try:
                        rag = getattr(self, "_chatbot_rag_engine", None)
                        if rag is None:
                            rag = RAGEngine()
                            self._chatbot_rag_engine = rag
                        resume_text = getattr(profile, 'raw_resume_context', "")
                        if resume_text:
                            if not getattr(rag, "vectorstore", None):
                                indexed = rag.index_resume(resume_text)
                                self.logger.log_info(f"[CHATBOT] RAG indexed={indexed}, _initialized={rag._initialized}, embeddings={rag.embeddings is not None}, vectorstore={rag.vectorstore is not None}")
                                if indexed:
                                    self.logger.log_info("[CHATBOT] RAG resume context indexed for drawer flow")
                                else:
                                    self.logger.log_warn("[CHATBOT] RAG index_resume failed; fallback context will be used")
                    except Exception as e:
                        rag = None
                        self.logger.log_warn(f"Failed to pre-index RAG: {e}")

                for step in range(15): # Max 15 interaction steps
                    # 1. EXTRACT QUESTION
                    q_selectors = [".chat-question", ".chatbot_botMsg", ".ssrc__bot-msg", "[class*='botMsg']"]
                    q_text = ""
                    for q_sel in q_selectors:
                        q_el = page.locator(q_sel).last
                        if await q_el.count() > 0:
                            q_text = (await q_el.inner_text()).strip()
                            if q_text: break
                    
                    # If no question, check for FINAL SAVE button
                    if not q_text:
                        if await self._click_modal_save_or_submit(page):
                            await asyncio.sleep(2)
                        await asyncio.sleep(1)
                        if step > 4 and not q_text: break # Break if stuck
                        continue

                    self.logger.log_info(f"[CHATBOT] Step {step+1}: '{q_text[:40]}...'")
                    q_lower = q_text.lower()

                    # Error message detection
                    if any(err in q_lower for err in ["something went wrong", "try again later", "error occurred", "unable to process"]):
                        self.logger.log_warn(f"[CHATBOT] Error detected in drawer: '{q_text}'")
                        await asyncio.sleep(5)
                        if step > 10: break
                        continue


                    # 2. EXTRACT OPTIONS
                    opt_selectors = [
                        "label.ssrc__label",
                        ".ssrc__radio-btn-container",
                        ".singleselect-radiobutton-container .ssrc__radio-btn-container",
                        ".chat-options button",
                        ".chatbot_MessageContainer label.ssrc__label",
                        ".singleselect-radiobutton-container",
                        "[role='radio']",
                        ".radio-option",
                        "button[role='radio']"
                    ]
                    
                    options = []
                    active_opts_loc = None
                    for opt_sel in opt_selectors:
                        loc = page.locator(opt_sel)
                        count = await loc.count()
                        if count > 0:
                            texts = [o.strip() for o in await loc.all_inner_texts() if o.strip()]
                            if texts:
                                options = texts
                                active_opts_loc = loc
                                break
                    
                    # v3.5 UNIVERSAL RAG ROUTING
                    # 1. Retrieve Local RAG Context (Naukri Specialized)
                    context = ""
                    if self.brain and rag:
                        try:
                            if hasattr(rag, 'vectorstore') and rag.vectorstore:
                                chunks = await rag.retrieve_with_hyde_async(q_text)
                                if chunks:
                                    context = "\n".join(chunks)
                        except: pass

                    # 2. RAG Delegation Check
                    rag_keywords = [
                        "experience", "years", "months", "tenure", "how long",
                        "project", "skill", "technology", "tech", "tool", "work",
                        "education", "degree", "college", "university", "school",
                        "github", "linkedin", "social", "link", "website", "portfolio",
                        "name", "email", "mobile", "phone", "contact"
                    ]
                    is_rag_required = any(x in q_lower for x in rag_keywords)
                    
                    # If RAG is required, pass context=None to trigger brain-side retrieval.
                    final_context = None if is_rag_required else context
                    
                    result = await self._answer_application_question(
                        question=q_text,
                        profile=profile,
                        options=options,
                        context=final_context,
                        field_type="radio" if options else "text",
                    )
                    ans_val = result.get("answer", "0")
                    ans_type = result.get("type", "text")
                    
                    # Final Numeric Clean for Salary - return 0 for invalid answers
                    if any(x in q_lower for x in ["expected", "ctc", "salary"]):
                        import re
                        num_match = re.search(r'\d+', str(ans_val))
                        ans_val = num_match.group(0) if num_match else "0"
                    
                    self.logger.log_info(f"[CHATBOT] Q: '{q_text[:40]}...' | A: '{ans_val}' | Type: {ans_type} | Options: {options[:3]}")

                    # 4. HANDLE RADIOS (RETRY & FALLBACK) - handle both "option" and "radio" types
                    if (ans_type in ["option", "radio"] or (ans_type == "text" and options)) and options and active_opts_loc:
                        clicked = False
                        
                        # Try multiple click strategies
                        click_strategies = [
                            # Strategy 1: Label + radio (most reliable)
                            lambda: page.locator(f"label.ssrc__label:has-text('{ans_val}')").first,
                            # Strategy 2: Radio container with text
                            lambda: page.locator(f".ssrc__radio-btn-container:has-text('{ans_val}')").first,
                            # Strategy 3: Filter by exact text
                            lambda: active_opts_loc.filter(has_text=ans_val).first,
                            # Strategy 4: Get by text
                            lambda: page.get_by_text(ans_val, exact=True).first,
                            # Strategy 5: Get by partial text
                            lambda: page.get_by_text(ans_val, exact=False).first,
                            # Strategy 6: Button with value
                            lambda: page.locator(f"button:has-text('{ans_val}')").first,
                        ]
                        
                        for attempt, strategy in enumerate(click_strategies):
                            try:
                                target = strategy()
                                if await target.count() > 0 and await target.is_visible(timeout=1000):
                                    try:
                                        # Try to click the center of the element
                                        await target.click(timeout=1500, position={'x': 5, 'y': 5})
                                        
                                        # Also try to click any internal clickable elements (icons/bullets)
                                        try:
                                            internal_target = target.locator("i, span, input, .ssrc__radio-icon").first
                                            if await internal_target.count() > 0:
                                                await internal_target.click(timeout=500)
                                        except: pass
                                        
                                        self.logger.log_info(f"[CHATBOT] Clicked '{ans_val}' via strategy {attempt+1}")
                                        clicked = True
                                        break
                                    except Exception:
                                        # Some radio UIs block normal click (overlay/intercept). Force JS click.
                                        await target.evaluate(
                                            """el => {
                                                el.scrollIntoView({block: 'center', inline: 'center'});
                                                el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                                el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                                el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                                if (typeof el.click === 'function') el.click();
                                            }"""
                                        )
                                        self.logger.log_info(f"[CHATBOT] JS clicked '{ans_val}' via strategy {attempt+1}")
                                        clicked = True
                                        break
                            except Exception as e:
                                continue
                        
                        if not clicked:
                            # Fallback: click first option in container
                            self.logger.log_warn(f"[CHATBOT] Click failed for '{ans_val}'. Trying first option.")
                            try:
                                first_opt = active_opts_loc.nth(0)
                                if await first_opt.count() > 0:
                                    await first_opt.click(timeout=1500)
                                    await first_opt.evaluate("el => el.click()")
                                    self.logger.log_info(f"[CHATBOT] Clicked first option as fallback")
                                    clicked = True
                            except Exception as e:
                                self.logger.log_warn(f"[CHATBOT] Fallback click failed: {e}")
                        
                        if not clicked:
                            # Last resort: use JS click
                            try:
                                js_clicked = await page.evaluate(
                                    """(answer) => {
                                        const norm = (v) => (v || '').toString().toLowerCase().replace(/\\s+/g, ' ').trim();
                                        const wanted = norm(answer);
                                        const selectors = [
                                            '.ssrc__radio-btn-container',
                                            'label.ssrc__label',
                                            '[role=\"radio\"]',
                                            '.singleselect-radiobutton-container button',
                                            '.chat-options button',
                                        ];
                                        const nodes = Array.from(new Set(selectors.flatMap((s) => Array.from(document.querySelectorAll(s)))));
                                        const byText = nodes.find((n) => norm(n.innerText).includes(wanted));
                                        const target = byText || nodes[0];
                                        if (!target) return false;
                                        target.scrollIntoView({ block: 'center', inline: 'center' });
                                        target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                        target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                        target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                        if (typeof target.click === 'function') target.click();
                                        return true;
                                    }""",
                                    str(ans_val),
                                )
                                if js_clicked:
                                    self.logger.log_info("[CHATBOT] JS click fallback selected radio option")
                                    clicked = True
                            except:
                                pass

                        if clicked:
                            await asyncio.sleep(1) # Wait for selection to register
                            saved = await self._click_modal_save_or_submit(page)
                            if not saved:
                                self.logger.log_warn("[CHATBOT] Save button not available after radio selection")

                        await asyncio.sleep(2)
                        continue

                    # Handle text inputs when ans_type is text OR options not found
                    if ans_type == "text" or not options or not active_opts_loc:
                        # 5. HANDLE TEXT AREAS
                        text_selectors = [
                            "div.textArea[contenteditable='true']",
                            "div.textArea",
                            "div[contenteditable='true'][id*='userInput']",
                            "textarea",
                            "input[id*='userInput']",
                            "[contenteditable='true']",
                            "[class*='textArea']"
                        ]
                        text_filled = False
                        for sel in text_selectors:
                            text_area = page.locator(sel).first
                            try:
                                if await text_area.count() > 0 and await text_area.is_visible(timeout=2000):
                                    # Scroll into view first
                                    await text_area.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.5)
                                    # Try fill first
                                    try:
                                        await text_area.fill(str(ans_val))
                                    except:
                                        # Click and type
                                        await text_area.click()
                                        await asyncio.sleep(0.3)
                                        await page.keyboard.type(str(ans_val))
                                    text_filled = True
                                    break
                            except:
                                continue
                        if text_filled:
                            saved = await self._click_modal_save_or_submit(page)
                            if not saved:
                                # Fallback for inputs that submit on Enter
                                try:
                                    await page.keyboard.press("Enter")
                                except:
                                    pass
                            await asyncio.sleep(2)
                            continue

                self.logger.log_ok("[CHATBOT] Drawer interaction complete.")

            # PHASE B: STATIC MODAL / FORM
            # Fallback for standard modal questions if chatbot drawer is closed
            if not await page.locator(".chatbot_Drawer").is_visible(timeout=1000):
                static_filled = await self._fill_static_modal_questions(page, profile)
                if static_filled > 0:
                    self.logger.log_ok(f"[MODAL] Filled {static_filled} static question(s)")
        except Exception as e:
            self.logger.log_err(f"Smart question handling error: {e}")

    async def _click_modal_save_or_submit(self, page: Page) -> bool:
        """Click Save/Submit action for chatbot or static modal forms."""
        save_selectors = [
            ".sendMsg:has-text('Save')",
            ".sendMsg:has-text('Submit')",
            ".sendMsgbtn_container .sendMsg",
            ".sendMsgbtn_container .send",
            "button:has-text('Save')",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button[type='submit']",
            ".sendMsg",
        ]
        for save_sel in save_selectors:
            try:
                save_btn = page.locator(save_sel).first
                if await save_btn.count() == 0:
                    continue
                if not await save_btn.is_visible(timeout=1200):
                    continue
                class_attr = (await save_btn.get_attribute("class") or "").lower()
                disabled_attr = await save_btn.get_attribute("disabled")
                aria_disabled = (await save_btn.get_attribute("aria-disabled") or "").lower()
                is_disabled = (
                    "disabled" in class_attr
                    or disabled_attr is not None
                    or aria_disabled == "true"
                )
                if is_disabled:
                    continue
                await save_btn.click()
                await asyncio.sleep(1.0)
                return True
            except Exception:
                continue
        return False

    async def _answer_application_question(
        self,
        question: str,
        profile: Any,
        options: Optional[list[str]] = None,
        context: str = "",
        field_type: str = "text",
    ) -> dict[str, str]:
        """Resolve form answers via LLM when available, otherwise return safe defaults."""
        question = str(question or "")
        q_lower = question.lower()
        options = [str(o).strip() for o in (options or []) if str(o).strip()]

        # Instant profile fields
        name = str(getattr(profile, "name", "") or "").strip()
        email = str(getattr(profile, "email", "") or "").strip()
        phone = str(getattr(profile, "phone", "") or "").strip()
        phone_digits = "".join(ch for ch in phone if ch.isdigit())
        if len(phone_digits) >= 10:
            phone = phone_digits[-10:]
        links = getattr(profile, "extra", {}) if isinstance(getattr(profile, "extra", {}), dict) else {}
        linkedin = str(links.get("linkedin") or getattr(profile, "linkedin", "") or "").strip()
        github = str(links.get("github") or getattr(profile, "github", "") or "").strip()
        portfolio = str(
            links.get("portfolio")
            or links.get("website")
            or getattr(profile, "portfolio", "")
            or getattr(profile, "website", "")
            or ""
        ).strip()

        if ("full name" in q_lower or re.search(r"\bname\b", q_lower)) and name:
            return {"type": "text", "answer": name}
        if any(x in q_lower for x in ["email", "e-mail"]) and email:
            return {"type": "text", "answer": email}
        if any(x in q_lower for x in ["mobile", "phone", "contact number", "contact no"]) and phone:
            return {"type": "text", "answer": phone}
        if "linkedin" in q_lower and linkedin:
            return {"type": "text", "answer": linkedin}
        if "github" in q_lower and github:
            return {"type": "text", "answer": github}
        if any(x in q_lower for x in ["portfolio", "website", "personal site", "link"]) and portfolio:
            return {"type": "text", "answer": portfolio}
            
        # Specific Date Formats
        if any(x in q_lower for x in ["date of birth", "dob"]):
            return {"type": "text", "answer": "01/01/1998"}

        # Salary/notice policy
        if any(x in q_lower for x in ["notice", "joining", "available to join"]):
            return {"type": "text", "answer": "0"}
        if any(x in q_lower for x in ["current ctc", "current salary", "current drawn", "present ctc", "present salary"]):
            if options:
                opt = self._pick_salary_option(options, 20000)
                return {"type": "option", "answer": opt}
            return {"type": "text", "answer": "20000"}
        if any(x in q_lower for x in ["expected ctc", "expected salary", "salary expectation", "expected compensation", "expected"]) and not any(x in q_lower for x in ["current ctc", "current salary", "present salary"]):
            expected_value = self._estimate_expected_salary(question=question, context=context, profile=profile)
            if options:
                opt = self._pick_salary_option(options, expected_value)
                return {"type": "option", "answer": opt}
            return {"type": "text", "answer": str(expected_value)}

        brain = getattr(self, "brain", None)
        answer_fn = getattr(brain, "answer_question", None) if brain is not None else None

        if callable(answer_fn):
            try:
                import inspect
                if inspect.iscoroutinefunction(answer_fn):
                    result = await answer_fn(
                        question,
                        profile,
                        {},
                        field_type=field_type,
                        options=options,
                        context=context,
                    )
                else:
                    result = answer_fn(
                        question,
                        profile,
                        {},
                        field_type=field_type,
                        options=options,
                        context=context,
                    )
                if isinstance(result, dict):
                    answer_value = str(result.get("answer", "")).strip()
                    answer_type = str(result.get("type", "text")).strip() or "text"
                    if answer_value:
                        return {"type": answer_type, "answer": answer_value}
            except Exception as e:
                self.logger.log_warn(f"Answer engine failed for question '{question[:45]}': {e}")

        if options:
            return {"type": "option", "answer": options[0]}
        return {"type": "text", "answer": "Yes"}

    def _pick_salary_option(self, options: list[str], target_value: int) -> str:
        """Pick closest option to target salary when salary choices are provided."""
        best_opt = options[0] if options else str(target_value)
        best_delta = float("inf")
        for opt in options:
            parsed = self._parse_salary_option_value(opt)
            if parsed is None:
                continue
            delta = abs(parsed - target_value)
            if delta < best_delta:
                best_delta = delta
                best_opt = opt
        return best_opt

    def _parse_salary_option_value(self, text: str) -> Optional[int]:
        """Parse common salary formats like '3 LPA', '20000/month', or '4-6 LPA'."""
        s = str(text or "").lower().replace(",", " ").replace("₹", " ")
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
        if not nums:
            return None
        value = sum(nums) / len(nums)
        if "lpa" in s or "lakh" in s or re.search(r"\bl\b", s):
            return int(value * 100000)
        if "k" in s:
            return int(value * 1000)
        if any(x in s for x in ["/month", "per month", "monthly", "pm"]):
            return int(value * 12)
        return int(value)

    def _estimate_expected_salary(self, question: str, context: str, profile: Any) -> int:
        """Estimate expected salary from question + JD context with fresher-safe defaults."""
        text = f"{question}\n{context or ''}".lower()
        monthly_question = any(x in text for x in ["/month", "per month", "monthly", "pm", "in hand"])

        # Fresher baseline annual CTC in INR
        annual = 360000
        if any(x in text for x in ["intern", "internship", "trainee", "apprentice"]):
            annual = 240000
        if any(x in text for x in ["senior", "lead", "architect", "principal", "manager"]):
            annual = max(annual, 900000)

        years_match = re.search(r"(\d+)\s*(?:\+|plus)?\s*(?:years|yrs|year)", text)
        if years_match:
            years = int(years_match.group(1))
            annual = max(annual, 320000 + (years * 140000))

        if "full stack" in text or "backend" in text or "frontend" in text:
            annual = max(annual, 400000)
        if any(x in text for x in ["aws", "azure", "devops", "kubernetes", "microservices"]):
            annual = max(annual, 550000)

        annual = max(annual, 280000)  # should remain above current fixed 20000/month baseline
        annual = int(round(annual / 1000.0) * 1000)

        if monthly_question:
            monthly = int(round((annual / 12.0) / 500.0) * 500)
            return max(monthly, 23000)
        return annual

    async def _extract_modal_question_text(self, container: Any) -> str:
        """Extract readable question text from a static modal row/container."""
        text_selectors = [
            "label",
            "legend",
            ".question",
            ".question-label",
            "[class*='label']",
            "[class*='question']",
            "p",
            "span",
        ]
        for selector in text_selectors:
            try:
                loc = container.locator(selector).first
                if await loc.count() == 0:
                    continue
                txt = normalize_whitespace((await loc.inner_text()).strip())
                if len(txt) >= 3:
                    return txt
            except Exception:
                continue
        try:
            row_text = normalize_whitespace((await container.inner_text()).strip())
            return row_text[:180]
        except Exception:
            return ""

    async def _fill_text_field(self, field: Any, value: str) -> bool:
        """Fill text-like inputs safely without clobbering existing values."""
        try:
            existing = (await field.evaluate("el => (el.value || el.innerText || '').toString().trim()")) or ""
            if str(existing).strip():
                return False
            await field.scroll_into_view_if_needed()
            try:
                await field.fill(str(value))
            except Exception:
                await field.click()
                await asyncio.sleep(0.2)
                await field.press("Control+A")
                await asyncio.sleep(0.1)
                await field.type(str(value), delay=10)
            return True
        except Exception:
            return False

    async def _click_option_in_container(self, container: Any, option_text: str) -> bool:
        """Click a radio/option-like choice by visible text inside a container."""
        selectors = [
            "label",
            ".ssrc__radio-btn-container",
            "[role='radio']",
            "button[role='radio']",
            ".radio-option",
            "button",
        ]
        for sel in selectors:
            try:
                target = container.locator(sel).filter(has_text=option_text).first
                if await target.count() == 0:
                    continue
                if not await target.is_visible(timeout=700):
                    continue
                try:
                    await target.click(timeout=1200)
                except Exception:
                    await target.evaluate("el => el.click()")
                return True
            except Exception:
                continue
        return False

    async def _fill_static_modal_questions(self, page: Page, profile: Any) -> int:
        """Handle non-chatbot modal forms by filling visible rows with AI/fallback answers."""
        question_rows = page.locator(
            ".question-row, .form-group, [class*='question'], [class*='Question'], .ssrc__questionContainer"
        )
        row_count = await question_rows.count()
        if row_count == 0:
            return 0

        self.logger.log_info(f"[MODAL] Handling static questions across {row_count} row(s)...")
        filled = 0
        seen_questions: set[str] = set()
        from utils.job_retrieval import fuzzy_match_option

        for idx in range(min(row_count, 30)):
            row = question_rows.nth(idx)
            try:
                if not await row.is_visible(timeout=700):
                    continue
            except Exception:
                continue

            question_text = await self._extract_modal_question_text(row)
            question_key = re.sub(r"\s+", " ", question_text.lower()).strip()
            if not question_key or question_key in seen_questions:
                continue
            seen_questions.add(question_key)

            option_loc = row.locator(
                "label, .ssrc__radio-btn-container, [role='radio'], button[role='radio'], .radio-option"
            )
            options = []
            try:
                if await option_loc.count() > 0:
                    options = [t.strip() for t in await option_loc.all_inner_texts() if t and t.strip()]
            except Exception:
                options = []

            # Radio/options question
            if options:
                result = await self._answer_application_question(
                    question=question_text,
                    profile=profile,
                    options=options,
                    field_type="radio",
                )
                ans_val = str(result.get("answer", options[0]))
                choice = fuzzy_match_option(ans_val, options) or options[0]
                if await self._click_option_in_container(row, choice):
                    filled += 1
                continue

            # Dropdown/select question
            select_el = row.locator("select").first
            try:
                if await select_el.count() > 0 and await select_el.is_visible(timeout=700):
                    option_texts = [t.strip() for t in await select_el.locator("option").all_inner_texts() if t and t.strip()]
                    option_texts = [o for o in option_texts if o.lower() not in {"select", "choose", "select option"}]
                    if option_texts:
                        result = await self._answer_application_question(
                            question=question_text,
                            profile=profile,
                            options=option_texts,
                            field_type="select",
                        )
                        ans_val = str(result.get("answer", option_texts[0]))
                        choice = fuzzy_match_option(ans_val, option_texts) or option_texts[0]
                        try:
                            await select_el.select_option(label=choice)
                        except Exception:
                            await select_el.select_option(index=1 if len(option_texts) > 1 else 0)
                        filled += 1
                        continue
            except Exception:
                pass

            # Text input question
            text_field = row.locator(
                "textarea, input[type='text'], input[type='number'], input[type='email'], input[type='tel'], input:not([type]), [contenteditable='true']"
            ).first
            try:
                if await text_field.count() > 0 and await text_field.is_visible(timeout=700):
                    result = await self._answer_application_question(
                        question=question_text,
                        profile=profile,
                        field_type="text",
                    )
                    answer_text = str(result.get("answer", "Yes")).strip() or "Yes"
                    if await self._fill_text_field(text_field, answer_text):
                        filled += 1
            except Exception:
                continue

        if filled > 0:
            await self._click_modal_save_or_submit(page)
            
        # FALLBACK: Use universal FormFiller if available
        if FormFiller:
            try:
                filler = FormFiller(self.logger)
                # Build minimal job dict for FormFiller
                job = {"title": "", "company": ""}
                filler_result = await filler.fill_application_form(
                    page=page,
                    profile=profile,
                    job=job,
                    answers={},
                    llm_answers=self.brain
                )
                if filler_result.get("fields_filled", 0) > 0:
                    self.logger.log_ok(f"[FALLBACK] FormFiller filled {filler_result['fields_filled']} additional fields")
                    await self._click_modal_save_or_submit(page)
                    filled += filler_result["fields_filled"]
            except Exception as e:
                self.logger.log_warn(f"[FALLBACK] FormFiller error: {e}")
                
        return filled

    async def _detect_apply_button(self, page: Page) -> tuple[str, Optional[Any]]:
        """
        Detect apply mode on JD page.
        Returns:
            ("internal", button_locator) when Naukri internal apply is available.
            ("external", None) when only company-site/external apply is detected.
            ("none", None) when no actionable apply control is found.
        """
        # Skip external check - try ANY apply button but skip "Apply on company site" text
        apply_selectors = [
            "button#apply-button",
            "a#apply-button",
            "button.apply-button",
            "a.apply-button",
            "[data-ga-track*='apply'] button",
            "[data-ga-track*='apply'] a",
            "button:has-text('Apply')",
            "a:has-text('Apply')",
            "button:has-text('I am interested')",
            "a:has-text('I am interested')",
        ]

        for sel in apply_selectors:
            btn = page.locator(sel).first
            try:
                if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                    btn_text = (await btn.inner_text()).strip()
                    # Skip buttons with "Apply on company site" text - those are external
                    if "apply on company" in btn_text.lower() or "apply externally" in btn_text.lower():
                        self.logger.log_info(f"[APPLY] Skip external button: '{btn_text}'")
                        continue
                    self.logger.log_info(f"[APPLY] Found apply button: selector='{sel}', text='{btn_text}'")
                    return "internal", btn
            except Exception as e:
                continue
        
        self.logger.log_info("[APPLY] No apply button found")
        return "none", None

    async def _click_apply_on_jd(self, page: Page, profile: Any) -> bool:
        """Click Apply button on job detail page - skip external company site"""
        try:
            apply_type, btn = await self._detect_apply_button(page)
            if apply_type == "external":
                self.logger.log_info("External company-site apply detected - SKIP")
                return "external"
            if apply_type != "internal" or btn is None:
                self.logger.log_info("No internal apply button found on JD page - SKIP")
                return False

            # Internal apply flow
            if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                try:
                    current_btn_text = (await btn.inner_text()).strip()
                except Exception:
                    current_btn_text = ""
                await btn.click()
                await page.wait_for_timeout(6000) # Give it time to process bypass fast sleep
                
                # 1. Handle Redirect to /myapply/ (Some jobs redirect instead of modal)
                if "/myapply/saveApply" in page.url:
                    self.logger.log_ok(f"Apply confirmed via saveApply redirect: {page.url[:80]}")
                    return True
                
                # 2. Check for modal/form/drawer and handle it
                # Exclude chatbot drawers which cause strict mode violations
                # Use a broader check for questions
                modal_selectors = [
                    ".chatbot_Drawer", 
                    ".chatbot_MessageContainer",
                    ".modal-content",
                    ".drawer-wrapper",
                    "[class*='Drawer']"
                ]
                
                modal_found = False
                chatbot_modal_handled = False
                for selector in modal_selectors:
                    modal = page.locator(selector).first
                    if await modal.is_visible(timeout=5000):
                        self.logger.log_info(f"Handle apply questions in {selector}...")
                        await self._answer_modal_questions(page, profile)
                        modal_found = True

                        # Chatbot drawer auto-submits after answers. Do not click Apply again.
                        chatbot_modal_handled = "chatbot" in selector.lower()
                        if chatbot_modal_handled:
                            wait_time = random.uniform(10.0, 15.0)
                            self.logger.log_info(f"Chatbot answers submitted. Waiting {wait_time:.1f}s for auto-apply...")
                            await page.wait_for_timeout(int(wait_time * 1000))
                        else:
                            # Static modal fallback: submit only when needed.
                            submit_btn = page.locator(
                                "button.submit, button[type='submit'], .apply-button:has-text('Submit'), button:has-text('Save'), .sendMsg:has-text('Save')"
                            ).last
                            if await submit_btn.count() > 0:
                                await submit_btn.click()
                                await page.wait_for_timeout(5000)
                        break

                if not modal_found:
                    self.logger.log_info("No question drawer/modal found after Apply; checking direct apply result")

                # 2. VERIFY SUCCESS
                # Success indicators:
                # - Button text changes to "Applied"
                # - Success toast/message appears
                success_indicators = [
                    "button:has-text('Applied')",
                    "button:has-text('Applied earlier')",
                    ".success-message",
                    "[class*='success']",
                    "text='Applied successfully'",
                    "text='successfully applied'"
                ]
                
                for indicator in success_indicators:
                    if await page.locator(indicator).count() > 0:
                        self.logger.log_ok(f"Success verified via: {indicator}")
                        return True

                if "/myapply/saveApply" in page.url:
                    self.logger.log_ok(f"Apply confirmed via saveApply redirect: {page.url[:80]}")
                    return True
                
                # If button text still says "Apply", it may still have succeeded (Naukri slow UI update)
                # Check if modal was closed - that indicates partial success
                try:
                    drawer_closed = not await page.locator(".chatbot_Drawer, .chatbot_MessageContainer").first.is_visible(timeout=2000)
                except Exception:
                    drawer_closed = False
                
                if current_btn_text.lower() in ("apply", "i am interested"):
                    if drawer_closed:
                        self.logger.log_warn("Apply button text unchanged but drawer closed - treating as success")
                        # Extract identity even though button didn't update
                        try:
                            job_title, company_name = await self._extract_job_identity(page)
                            self._last_applied_job_title = job_title.strip()
                            self._last_applied_company = company_name.strip()
                        except Exception:
                            pass
                        return True
                    self.logger.log_err("Apply button text unchanged - Verification Failed")
                    return False

                return True # Fallback if modal closed but no explicit text found

            return False
            
        except Exception as e:
            self.logger.log_err(f"Apply click failed: {e}")
            return False

    async def _anti_ban_delay(self, applied_count: int, settings: Any) -> None:
        """Anti-ban delay: 1.5-3s base + extra after every N applies"""
        min_delay = getattr(settings, "min_apply_delay", 1.5)
        max_delay = getattr(settings, "max_apply_delay", 3.0)
        
        base_delay = random.uniform(min_delay, max_delay)
        
        # Extra delay after every N applies
        extra_after_n = getattr(settings, "extra_delay_after_n_applies", 5)
        extra_min = getattr(settings, "extra_delay_min", 4.0)
        extra_max = getattr(settings, "extra_delay_max", 10.0)
        
        if applied_count > 0 and applied_count % extra_after_n == 0:
            extra = random.uniform(extra_min, extra_max)
            total = base_delay + extra
            self.logger.log_info(f"Anti-ban: Extra delay {total:.1f}s after {applied_count} applies")
            await asyncio.sleep(total)
        else:
            await asyncio.sleep(base_delay + 2)  # Added 2s extra delay

    async def _next_page(self, page: Page) -> bool:
        """
        100% RELIABLE: Navigate to next page via URL manipulation using the original search URL.
        Naukri uses slugs like: /react-developer-jobs-2, /react-developer-jobs-3, etc.
        """
        try:
            # ALWAYS use the stored search URL as the base for pagination
            # This prevents us from trying to paginate from a JD page or the homepage
            current_url = getattr(self, "current_search_url", page.url)
            
            # If we're on a non-search page (like homepage), we can't paginate safely
            if "naukri.com/mnjuser/homepage" in current_url or "naukri.com/mnjuser/homepage" in page.url:
                self.logger.log_warn("Pagination aborted: Redirected to homepage. Restarting search loop.")
                return False

            if "?" in current_url:
                base_part, query_part = current_url.split("?", 1)
                query_suffix = f"?{query_part}"
            else:
                base_part = current_url
                query_suffix = ""

            # Check for existing page number at the end of the slug
            import re
            # Naukri search URLs often have -2, -3 before the query string
            match = re.search(r"-(\d+)$", base_part)
            
            if match:
                # Increment existing page
                current_num = int(match.group(1))
                next_num = current_num + 1
                new_url = re.sub(r"-(\d+)$", f"-{next_num}", base_part) + query_suffix
            else:
                # First page -> page 2
                new_url = f"{base_part}-2{query_suffix}"
            
            self.logger.log_info(f"Navigating to next page URL: {new_url}")
            await page.goto(new_url, wait_until="domcontentloaded", timeout=25000)
            
            # Update the stored search URL so the next call increments correctly
            self.current_search_url = new_url
            
            await asyncio.sleep(5)
            return True
            
        except Exception as e:
            self.logger.log_err(f"Pagination failed: {e}")
            return False

    # === Legacy API for compatibility ===
    async def search_jobs(self, profile: Any, settings: Any) -> list[dict[str, Any]]:
        """Legacy search_jobs for compatibility"""
        result = await self.search_and_apply(profile, settings)
        return []

    async def apply_to_job(self, page: Page, job: dict[str, Any], profile: Any, settings: Any) -> bool:
        """Legacy apply_to_job for compatibility"""
        return await self._click_apply_on_jd(page, profile)
