"""
FoundIt Scraper - Job Automation System
====================================
With role discovery and warmup integration.
Uses percentage-based skill matching (35% min threshold).
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

from typing import Any, Optional
from playwright.async_api import Page
from scraper_adapter.base_scraper import BaseScraper
from scraper_adapter.playwright_manager import playwright_manager
from utils.session_manager import SessionManager
from utils.resume_downloader import download_resume_from_url
from utils.resume_selector import ResumeSelector, extract_skills_from_jd
from utils.path_contract import resolve_ai_engine_pdf_path
from utils.ai_extractor import get_ai_extractor
from utils.skill_scorer import SkillScorer, calculate_match_percentage
import requests
from rag_engine.rag_engine import GroqLLM
try:
    from job_automation_system.ai_engine.llm_answers import LLMAnswers
except ImportError:
    try:
        from ai_engine.llm_answers import LLMAnswers  # type: ignore
    except ImportError:
        LLMAnswers = None

# Role discovery imports (same as Naukri/LinkedIn)
from role_manager.dynamic_role_generator import (
    get_role_by_top_skills,
)
from utils.student_mongodb import get_student_profile, list_all_students

# Warmup imports
try:
    from rag_engine.rag_resume_generator import get_rag_resume_generator
except ImportError:
    get_rag_resume_generator = None

class FoundItScraper(BaseScraper):
    source = "foundit"
    base_url = "https://www.foundit.in"
    LOGIN_URL = "https://www.foundit.in/rio/login"
    
    # Match threshold - use global
    MATCH_PERCENTAGE_MIN = None  # Set dynamically from settings
    
    def __init__(self, max_results: int = 20, timeout_seconds: int = 30, logger: Any = None):
        super().__init__(max_results, timeout_seconds, logger)
        self._logged_in = False
        self._warmup_roles: list[str] = []
        
        # Load global threshold with default (35.0 as requested)
        try:
            from config.settings import settings
            self.MATCH_PERCENTAGE_MIN = getattr(settings, "ats_threshold", 35.0)
        except:
            self.MATCH_PERCENTAGE_MIN = 35.0
            
        # Initialize AI Engine
        self.llm = GroqLLM()
        self.brain = LLMAnswers(self.llm, self.logger)
        
        # Initialize skill scorer
        self.skill_scorer = None

    def _get_candidate_id(self, profile: Any) -> str:
        """Get or create candidate ID"""
        # Prioritize existing student_id from MongoDB
        student_id = getattr(profile, "student_id", "")
        if student_id:
            return student_id
            
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
        self.logger.log_info(f"Checking warmup status for: {candidate_id}")
        
        try:
            # Get generator
            from rag_engine.rag_resume_generator import get_rag_resume_generator as get_gen
            generator = get_gen(logger=self.logger, student_id=candidate_id)

            # Sync profile hints from generator even before branching.
            self._sync_profile_from_generator(profile, generator)
            
            # Check if roles already discovered
            if generator.custom_roles:
                role_keys = []
                if isinstance(generator.custom_roles, dict):
                    role_keys = list(generator.custom_roles.keys())
                elif isinstance(generator.custom_roles, list):
                    for item in generator.custom_roles:
                        if isinstance(item, dict):
                            rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                            role_keys.append(rk)
                
                self.logger.log_ok(f"Roles already discovered in MongoDB: {role_keys}")
                self.logger.log_ok("Roles exist. Skipping PDF generation.")
                self._sync_profile_from_generator(profile, generator)
                # Save roles to MongoDB for future runs
                if self._warmup_roles:
                    await self._save_roles_to_mongodb(candidate_id, self._warmup_roles)
                return True
            
            # Need to discover roles
            self.logger.log_info("No roles found in MongoDB. Discovering roles and generating resumes...")
            await generator._init_rag()
            custom_roles = await generator.discover_top_roles()
            
            if custom_roles:
                self.logger.log_info(f"Discovered {len(custom_roles)} roles and generating resumes...")
                await generator.generate_initial_resumes()
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
        """Backfill runtime profile skills/titles from warmup generator state."""
        try:
            role_titles: list[str] = []
            custom_roles = getattr(generator, "custom_roles", {}) or {}
            if isinstance(custom_roles, dict):
                for role_cfg in custom_roles.values():
                    if isinstance(role_cfg, dict):
                        title = str(role_cfg.get("title", "")).strip()
                        if title:
                            role_titles.append(title)
            # Keep stable order and dedupe.
            self._warmup_roles = list(dict.fromkeys(role_titles))

            existing_titles = list(getattr(profile, "candidate_titles", []) or [])
            if not existing_titles and self._warmup_roles:
                profile.candidate_titles = self._warmup_roles[:6]
                self.logger.log_info(f"Backfilled candidate titles from warmup roles: {profile.candidate_titles}")

            existing_skills = [str(s).strip() for s in (getattr(profile, "skills", []) or []) if str(s).strip()]
            if not existing_skills:
                recovered_skills: list[str] = []
                gen_profile = getattr(generator, "profile", None)
                if gen_profile and getattr(gen_profile, "skills", None):
                    recovered_skills.extend([str(s).strip() for s in gen_profile.skills if str(s).strip()])
                if not recovered_skills and isinstance(custom_roles, dict):
                    for role_cfg in custom_roles.values():
                        if isinstance(role_cfg, dict):
                            recovered_skills.extend([str(s).strip() for s in (role_cfg.get("keywords") or []) if str(s).strip()])

                recovered_skills = list(dict.fromkeys(recovered_skills))
                if recovered_skills:
                    profile.skills = recovered_skills
                    self.logger.log_info(f"Backfilled profile skills from warmup profile: {len(recovered_skills)}")
        except Exception as e:
            self.logger.log_warn(f"Warmup profile sync skipped: {e}")
    
    def _build_query(self, profile: Any) -> str:
        """Build search query from candidate titles"""
        roles = list(getattr(profile, 'candidate_titles', []) or [])
        if not roles:
            roles = list(getattr(self, "_warmup_roles", []) or [])
        if not roles:
            # Fallback to skills
            roles = [str(s) for s in getattr(profile, 'skills', [])[:3]]
        
        if not roles:
            roles = ["Software Developer"]
        
        roles = list(dict.fromkeys(roles))[:6]
        query = ", ".join(roles)
        self.logger.log_info(f"Search query: {query}")
        return query
    
    def _get_roles_for_page(self, profile: Any, page_num: int) -> list[str]:
        """Get roles for pagination page using the same dynamic logic."""
        query_str = self._build_query(profile)
        all_roles = [r.strip() for r in query_str.split(",")]
        
        start_idx = (page_num - 1) * 3
        return all_roles[start_idx:start_idx + 3]

    async def search_jobs(self, profile: Any, settings: Any) -> list:
        return []

    async def search_and_apply(self, profile: Any, settings: Any) -> dict:
        # Using percentage-based matching (35% min threshold) - no old thresholds
        self.settings = settings
        self.profile = profile

        applied_count = 0
        skipped_count = 0
        self._last_applied_job_title = None
        self._last_applied_company = None

        # Session time tracking + platform-specific caps (anti-detection)
        import time as _time
        self._session_start = _time.time()
        from config.platforms import get_platform_config
        _plat_cfg = get_platform_config("foundit")
        self._max_applies = _plat_cfg.max_applies_per_run if _plat_cfg else 6
        requested_target = int(
            getattr(settings, "max_applies_per_run", 0)
            or getattr(settings, "target_applies", 0)
            or 0
        )
        if requested_target > self._max_applies:
            self.logger.log_info(f"Raising FoundIt apply cap to runtime target: {requested_target}")
            self._max_applies = requested_target
        self._session_limit = _plat_cfg.session_time_limit if _plat_cfg else 1800
        self._micro_break_interval = _plat_cfg.micro_break_interval if _plat_cfg else 3
        self._micro_break_min = _plat_cfg.micro_break_min if _plat_cfg else 20.0
        self._micro_break_max = _plat_cfg.micro_break_max if _plat_cfg else 50.0

        import os
        cdp_url = os.environ.get("CDP_URL")
        use_cdp = os.environ.get("USE_CDP", "true").lower() == "true"
        
        # NOTE: FoundIt blocks CDP consistently - try CDP first, fallback to Selenium
        try:
            if use_cdp:
                page, method = await playwright_manager.get_page_with_cdp_fallback(
                    settings, 
                    student_id=getattr(profile, "student_id", None),
                    cdp_url=cdp_url
                )
                # Check if CDP returned blocked content
                try:
                    content = await page.content()
                    if len(content) < 10000:
                        self.logger.log_warn(f"CDP blocked ({len(content)} bytes). Switching to Selenium...")
                        await page.close()
                        raise Exception("CDP blocked for FoundIt")
                except:
                    pass
                self.logger.log_ok(f"Browser via: {method.upper()} (CDP)")
            else:
                page = await playwright_manager.get_page(
                    settings,
                    student_id=getattr(profile, "student_id", None),
                )
                self.logger.log_info("Browser via: Playwright (Direct)")
        except Exception as e:
            self.logger.log_err(f"CDP/Playwright failed: {e}. Using FoundIt Selenium...")
            
            # FoundIt uses Selenium directly when CDP/Playwright fail
            try:
                from scraper_adapter.foundit_selenium import FoundItSelenium
                sel = FoundItSelenium(self.logger, settings, student_id=getattr(profile, "student_id", None))
                
                self.logger.log_info("Using FoundIt Selenium (direct)...")
                login_ok = sel.login(
                    getattr(profile, 'username', ''), 
                    getattr(profile, 'password', '')
                )
                
                if login_ok:
                    self.logger.log_ok("FoundIt Selenium login successful!")
                    await sel.close()
                    return {"status": "selenium_login_success", "applied": 0, "skipped": 0, "method": "selenium"}
                else:
                    self.logger.log_err("FoundIt Selenium login failed")
                    await sel.close()
                    return {"status": "selenium_login_failed", "applied": 0, "skipped": 0, "error": "selenium_login_failed"}
            except Exception as sel_err:
                self.logger.log_err(f"FoundIt Selenium also failed: {sel_err}")
                return {"status": "browser_error", "applied": 0, "skipped": 0, "error": str(sel_err)}


        try:
            # Step 1: Login
            self.logger.log_info("=== STEP 1: LOGIN ===")
            login_success = await self._ensure_logged_in(page, settings, profile)
            if not login_success:
                self.logger.log_err("FoundIt login failed; stopping run before job search.")
                return {
                    "status": "error",
                    "applied": applied_count,
                    "skipped": skipped_count,
                    "error": "foundit_login_failed",
                }

            # Step 1.5: Visit profile page to ensure resume is linked
            self.logger.log_info("=== STEP 1.5: VISIT PROFILE PAGE ===")
            self.logger.log_info("Navigating to: https://www.foundit.in/rio/profile")
            try:
                await page.goto("https://www.foundit.in/rio/profile", wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)
                current_url = page.url
                self.logger.log_ok(f"Profile page loaded - Current URL: {current_url}")
            except Exception as profile_err:
                self.logger.log_warn(f"Profile page visit failed: {profile_err}")

            # Step 1.75: RUN WARMUP if needed (discover roles + generate 5-6 resumes)
            await self._ensure_warmup(profile)

            # Step 2: Build dynamic role list and process roles one by one.
            # Searching with a huge comma-joined query often returns poor/generic matches.
            query = self._build_query(profile)
            role_queries = [r.strip() for r in query.split(",") if r.strip()]
            if not role_queries:
                role_queries = [query]
            processed_roles = {r.lower().strip() for r in role_queries}
            
            for title in role_queries:
                if applied_count >= self._max_applies:
                    break
                
                # Session time cap (anti-detection)
                import time as _time
                elapsed = _time.time() - self._session_start
                if elapsed > self._session_limit:
                    self.logger.log_warn(f"Session time limit reached ({int(elapsed)}s). Stopping to avoid detection.")
                    break
                    
                self.logger.log_ok(f"=== Processing role: {title} ===")
                url = self._build_search_url(title, "India")
                self.logger.log_info(f"URL: {url}")
                
                await page.goto(url, timeout=self.timeout_seconds * 1000)
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                
                # Wait for shimmer/skeleton loaders to disappear (FoundIt loads jobs async)
                self.logger.log_info("Waiting for job listings to load...")
                try:
                    await page.wait_for_selector(
                        ".animateShimmer, .shimmer, [class*='shimmer']",
                        state="hidden",
                        timeout=15000
                    )
                except:
                    pass  # Shimmer may not exist if page loaded fast
                
                # Wait for actual apply buttons to appear in DOM (up to 20s)
                try:
                    await page.wait_for_selector(
                        "button#applyBtn, button:has-text('Quick Apply'), button:has-text('Apply')",
                        state="visible",
                        timeout=20000
                    )
                except:
                    pass  # No jobs may genuinely exist for this query
                
                await asyncio.sleep(2)  # Small settle delay

                # Find job buttons
                apply_btns = page.locator("button#applyBtn")
                job_count = await apply_btns.count()
                self.logger.log_info(f"Found {job_count} jobs")

                # Step 3: Loop through jobs
                for i in range(min(job_count, 10)):
                    # Check if page is closed before each job
                    try:
                        if page.is_closed():
                            self.logger.log_warn("Page closed, stopping job processing")
                            break
                    except:
                        self.logger.log_warn("Page check failed, stopping")
                        break

                    if applied_count >= self._max_applies:
                        break
                    
                    elapsed = _time.time() - self._session_start
                    if elapsed > self._session_limit:
                        break
                    
                    # Micro-break every N jobs (looks human)
                    if i > 0 and i % self._micro_break_interval == 0:
                        import random
                        pause = random.uniform(self._micro_break_min, self._micro_break_max)
                        self.logger.log_info(f"Micro-break: pausing {pause:.0f}s (job #{i})")
                        await asyncio.sleep(pause)
                    
                    try:
                        result = await self._process_single_job(page, profile, i)
                        if result == "applied":
                            applied_count += 1
                        elif result == "skipped":
                            skipped_count += 1
                    except Exception as e:
                        self.logger.log_err(f"Job {i} error: {e}")
                        # Check if page is still valid after error
                        try:
                            if page.is_closed():
                                self.logger.log_warn("Page closed after error, stopping")
                                break
                        except:
                            break
                    
                    await self._random_delay(2, 4)

            # Generic fallback roles only after primary discovered roles are exhausted.
            if applied_count < self._max_applies:
                self.logger.log_info(
                    f"Primary roles completed with applied={applied_count}. Remaining target={self._max_applies - applied_count}. Starting generic fallback roles."
                )
                for fb_role in ["Software Engineer", "Software Developer"]:
                    if applied_count >= self._max_applies:
                        break
                    if fb_role.lower() in processed_roles:
                        continue

                    elapsed = _time.time() - self._session_start
                    if elapsed > self._session_limit:
                        self.logger.log_warn(f"Session time limit reached ({int(elapsed)}s). Stopping to avoid detection.")
                        break

                    self.logger.log_ok(f"=== FALLBACK ROLE: {fb_role} ===")
                    url = self._build_search_url(fb_role, "India")
                    self.logger.log_info(f"URL: {url}")

                    await page.goto(url, timeout=self.timeout_seconds * 1000)
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)

                    apply_btns = page.locator("button#applyBtn")
                    job_count = await apply_btns.count()
                    remaining_target = max(1, self._max_applies - applied_count)
                    dynamic_job_window = min(job_count, remaining_target * 3)
                    self.logger.log_info(
                        f"Fallback role jobs found={job_count}, scan_window={dynamic_job_window}, remaining_target={remaining_target}"
                    )

                    for i in range(dynamic_job_window):
                        if applied_count >= self._max_applies:
                            break

                        elapsed = _time.time() - self._session_start
                        if elapsed > self._session_limit:
                            break

                        try:
                            result = await self._process_single_job(page, profile, i)
                            if result == "applied":
                                applied_count += 1
                            elif result == "skipped":
                                skipped_count += 1
                        except Exception as e:
                            self.logger.log_err(f"Fallback role job {i} error: {e}")
                            try:
                                if page.is_closed():
                                    break
                            except:
                                break

                        await self._random_delay(2, 4)

                    processed_roles.add(fb_role.lower())

            return {"status": "success", "applied": applied_count, "skipped": skipped_count, "job_title": self._last_applied_job_title, "company": self._last_applied_company}
            
        except Exception as e:
            self.logger.log_err(f"Scraper error: {e}")
            return {"status": "error", "applied": applied_count, "skipped": skipped_count, "error": str(e), "job_title": self._last_applied_job_title, "company": self._last_applied_company}
        finally:
            try:
                await playwright_manager.return_page(page)
            except:
                pass

    async def _process_single_job(self, page: Page, profile: Any, job_index: int) -> str:
        """Process a single job using same-tab navigation (like Naukri)."""
        apply_btns = page.locator("button#applyBtn")
        if job_index >= await apply_btns.count():
            return "skipped"

        # Dismiss sticky overlays before clicking using JavaScript
        try:
            await page.evaluate("""
                () => {
                    const sticky = document.querySelectorAll('#select_all_section, .sticky, [class*="sticky"]');
                    sticky.forEach(el => el.style.display = 'none');
                    const backdrops = document.querySelectorAll('.modal-backdrop, [class*="backdrop"]');
                    backdrops.forEach(el => el.style.display = 'none');
                }
            """)
            await asyncio.sleep(0.5)
        except:
            pass

        button = apply_btns.nth(job_index)
        
        # Identify the card as the parent container
        card = button.locator("xpath=ancestor::div[contains(@class, 'srp') or contains(@class, 'card') or contains(@class, 'container')][1]")
        
        # Extract the job URL from the card link
        title_link = card.locator("h2 a, a[href*='/job/'], div.job-title a").first
        job_url = None
        try:
            if await title_link.count() > 0:
                job_url = await title_link.get_attribute("href")
                if job_url and not job_url.startswith("http"):
                    job_url = f"https://www.foundit.in{job_url}"
        except:
            pass

        if not job_url:
            self.logger.log_warn(f"Job {job_index}: No URL found, skipping")
            return "skipped"

        # Save current search URL to return later
        search_url = page.url
        
        self.logger.log_info(f"Job {job_index}: Opening JD...")
        
        # Navigate same tab to JD page
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        self.logger.log_info(f"Job {job_index}: JD page loaded - URL: {page.url}")

        # Extract full JD text
        self.logger.log_info(f"Job {job_index}: Extracting JD text...")
        jd_text = await self._extract_full_jd(page)
        self.logger.log_info(f"Job {job_index}: JD extracted - Length: {len(jd_text) if jd_text else 0} chars")
        
        if not jd_text:
            self.logger.log_warn(f"Job {job_index}: No JD text extracted")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            return "skipped"

        self.logger.log_info(f"JD length: {len(jd_text)} chars")

        # Extract details using AI (Skills, Qualifications, Experience)
        self.logger.log_info("Extracting JD details (skills & qualifications) with AI...")
        extractor = get_ai_extractor()
        jd_details = await extractor.extract_details_async(jd_text)
        
        jd_skills = jd_details.get("skills", [])
        jd_qualifications = jd_details.get("qualifications", [])
        jd_exp_years = jd_details.get("experience_years", "0")
        
        # Fallback to regex if AI fails for skills
        if not jd_skills:
            jd_skills = extract_skills_from_jd(jd_text)
        
        self.logger.log_info(f"=== JOB {job_index} SKILLS FROM JD ===")
        self.logger.log_info(f"JD Skills ({len(jd_skills)}): {', '.join(jd_skills[:15])}")
        if jd_qualifications:
            self.logger.log_info(f"JD Qualifications: {', '.join(jd_qualifications[:5])}")
        self.logger.log_info(f"JD Experience: {jd_exp_years} years")
        
        self.logger.log_info(f"=== PROFILE SKILLS ===")
        self.logger.log_info(f"Profile Skills ({len(profile.skills)}): {', '.join(profile.skills[:15])}")

        # Skill match logic - using new three-tier scorer
        self.logger.log_info(f"=== CALCULATING MATCH PERCENTAGE ===")
        result = calculate_match_percentage(
            resume_skills=profile.skills,
            jd_skills=jd_skills,
            min_percentage=self.MATCH_PERCENTAGE_MIN
        )
        self.logger.log_info(f"Match: {result.get('percentage', 0)}% ({result.get('total_points', 0)}/{result.get('max_possible', 0)} pts)")

        # Log matched skills breakdown
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
        
        self.logger.log_info("===============================")

        # Check percentage threshold
        match_pct = float(result.get('percentage') or 0)
        threshold = float(self.MATCH_PERCENTAGE_MIN or 35.0)
        if match_pct < threshold:
            self.logger.log_info(f"Job {job_index}: Low match ({match_pct}%), skipping")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            return "skipped"
        
        # Get student_id for resume selection
        student_id = "default"
        if hasattr(profile, 'student_id') and profile.student_id:
            student_id = str(profile.student_id)
        elif hasattr(profile, '_id') and str(profile._id):
            student_id = str(profile._id)

        job_title, company_name = await self._extract_job_identity(page)
        self.logger.log_info(f"Job {job_index}: Role='{job_title or 'Unknown'}' | Company='{company_name}'")
        
        # Track last applied for notification
        self._last_applied_job_title = job_title
        self._last_applied_company = company_name.strip() if company_name else None
        
        # Use ResumeSelector to choose the right resume
        profile_skills = profile.skills if hasattr(profile, 'skills') else []
        
        self.logger.log_info(f"=== RESUME SELECTION ===")
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
        
        self.logger.log_info(f"Resume Type: {resume_type}")
        self.logger.log_info(f"Resume Source: {source}")
        self.logger.log_info(f"Resume Path: {resume_path}")
        self.logger.log_info(f"Selected Bucket: {self._selected_bucket}")
        
        self._selected_resume_path = str(resume_path) if resume_path else None
        
        # If AI tailor needed, generate it
        if resume_type == "AI_TAILOR_NEEDED":
            self.logger.log_info("Generating AI tailored resume...")
            tailored_path = await self._generate_ai_resume(jd_text, student_id, profile)
            if tailored_path:
                self._selected_resume_path = tailored_path
                self.logger.log_ok(f"Generated AI tailored resume: {tailored_path}")

        # Ensure selected resume is synced to FoundIt profile for this specific job.
        # Some jobs use one-click apply and do not expose a file input in the apply modal.
        self._resume_synced_for_current_job = False
        try:
            self.logger.log_info(f"Job {job_index}: Syncing selected resume to FoundIt profile...")
            self._resume_synced_for_current_job = await self._update_profile_resume(page.context)
            if self._resume_synced_for_current_job:
                self.logger.log_ok(f"Job {job_index}: Profile resume synced for this job")
            else:
                self.logger.log_warn(f"Job {job_index}: Profile resume sync failed; will rely on modal upload if available")
        except Exception as sync_err:
            self.logger.log_warn(f"Job {job_index}: Profile resume sync error: {sync_err}")

        # Apply on the JD page (same tab)
        apply_success = await self._apply_from_jd_page(page)
        
        # Return to search results
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        
        if apply_success:
            self.logger.log_ok(f"Job {job_index}: Applied successfully!")
            
            try:
                await self.logger.log_application_success(
                    job_id=f"foundit_{job_index}_{int(asyncio.get_event_loop().time())}",
                    title=job_title if job_title else "Software Engineer",
                    company=company_name.strip() if company_name else "FoundIt",
                    platform="foundit",
                    student_id=self._get_candidate_id(profile)
                )
            except Exception as report_err:
                self.logger.log_warn(f"Dashboard reporting failed for Foundit: {report_err}")
                
            return "applied"
        return "skipped"

    async def _extract_job_identity(self, page: Page) -> tuple[str, str]:
        """Extract job title and company from a FoundIt JD page."""
        title_selectors = [
            "h1",
            ".job-title",
            "[class*='jobTitle']",
        ]
        company_selectors = [
            "div.company-name",
            "div.jd-header-company-name",
            "a.company-name",
            ".job-company-name",
            "[class*='companyName']",
            "h2.company-name",
            "a[href*='/company/']",
            "h2 + div span",
            "div.company-info h2",
        ]

        async def _first_text(selectors: list[str], is_company: bool = False) -> str:
            for sel in selectors:
                try:
                    locators = page.locator(sel)
                    count = await locators.count()
                    for i in range(count):
                        el = locators.nth(i)
                        txt = (await el.inner_text()).strip()
                        if not txt:
                            continue
                        
                        # ANTI-SOURCE FILTER: Skip "JOB SOURCE" or common source labels
                        if is_company and any(source in txt.upper() for source in ["JOB SOURCE", "SOURCE:", "LINKEDIN.COM", "NAUKRI.COM"]):
                            continue
                            
                        return txt
                except Exception:
                    continue
            return ""

        title = await _first_text(title_selectors) or "Software Engineer"
        company = await _first_text(company_selectors, is_company=True)
        
        # URL FALLBACK: If name is missing or generic, try to parse from the URL slug
        if not company or company.lower() in ["foundit", "monster", "unknown"]:
            try:
                # URL structure: https://www.foundit.in/job/role-keywords-company-name-location-id
                url_slug = page.url.split("/")[-1]
                if "-" in url_slug:
                    parts = url_slug.split("-")
                    # Filter out job title keywords and locations
                    ignore_words = {"java", "backend", "frontend", "developer", "engineer", "fullstack", "software", "senior", "junior", "lead", "india", "noida", "bengaluru", "bangalore", "pune", "hyderabad", "chennai", "mumbai", "job", "jobs"}
                    
                    # Search for the first part that isn't an ignored word or a number (ID)
                    potential_companies = [p for p in parts if p.lower() not in ignore_words and not p.isdigit()]
                    if potential_companies:
                        company = potential_companies[0].title()
            except:
                pass
        
        company = company or "FoundIt"
        return title, company

    async def _extract_skills_with_ai(self, jd_text: str) -> list:
        """Extract prioritized skills from JD using centralized AIExtractor"""
        extractor = get_ai_extractor()
        skills = await extractor.extract_skills_async(jd_text)
        
        if skills:
            return skills
        else:
            self.logger.log_warn("AI skill extraction returned no results for Foundit")
            return []

    async def _extract_full_jd(self, page: Page) -> str:
        """
        Extract all text from the job detail page.
        Focuses on subsections: Company Description, Role Description, Qualifications, etc.
        """
        try:
            # Step 1: Click 'View More' to expand content
            view_more_selectors = [
                "button:has-text('View More')", 
                "a:has-text('View More')", 
                "span:has-text('View More')",
                "div.view-more-button",
                ".show-more-btn"
            ]
            for sel in view_more_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await self._random_delay(1, 2)
                        break
                except:
                    continue
        except:
            pass

        try:
            # Step 2: Extract text from known JD containers
            # Priority selectors based on Foundit structure
            jd_selectors = [
                ".jobDesc", 
                ".keySkills", 
                "#jobDescription", 
                "div[class*='description']", 
                "div[class*='jd-']", 
                "section[class*='job']",
                ".job-details-info"
            ]
            
            full_text_parts = []
            
            # Iterate through selectors and collect non-empty text
            for sel in jd_selectors:
                elements = page.locator(sel)
                count = await elements.count()
                for i in range(count):
                    text = (await elements.nth(i).inner_text()).strip()
                    if text and text not in full_text_parts:
                        full_text_parts.append(text)
            
            # If nothing found with selectors, fallback to body text
            if not full_text_parts:
                text = await page.locator("body").inner_text()
                return text if text and len(text) > 100 else ""
            
            return "\n\n".join(full_text_parts)
        except Exception as e:
            self.logger.log_warn(f"JD extraction error: {e}")
            return ""

    def _calculate_skill_match(self, jd_text: str, profile_skills: list) -> int:
        """Simple case-insensitive skill matching."""
        if not jd_text or not profile_skills:
            return 0
        jd_lower = jd_text.lower()
        count = 0
        for skill in profile_skills:
            if skill.lower() in jd_lower:
                count += 1
        return count

    async def _apply_from_jd_page(self, page: Page) -> bool:
        """Locate and click apply buttons on the job detail page with verification."""
        try:
            # Step 1: Click the first apply button found
            apply_selectors = ["button#applyBtn", "button:has-text('Apply')", "button:has-text('Apply Now')", "button:has-text('Quick Apply')"]
            for sel in apply_selectors:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=5000):
                    await btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await self._random_delay(2, 3)
                    
                    # Step 2: Upload resume if modal appears AND has file input
                    # Check if there's a file input first
                    file_input_locator = page.locator("input[type='file']")
                    has_file_input = await file_input_locator.count() > 0
                    
                    if has_file_input:
                        self.logger.log_info("Modal with file input detected. Uploading resume...")
                        await self._upload_resume_from_profile(page)
                    else:
                        if getattr(self, "_resume_synced_for_current_job", False):
                            self.logger.log_info("No file input in modal. Using profile-based resume synced for current job.")
                        else:
                            self.logger.log_warn(
                                "No file input in modal and profile resume not confirmed for current job. "
                                "Application may use previous resume."
                            )

                    # Step 3: Handle any confirmation or submission button
                    submit_selectors = ["button:has-text('Submit')", "button:has-text('Apply')", "button:has-text('Send Application')"]
                    submit_clicked = False
                    for sub_sel in submit_selectors:
                        sub_btn = page.locator(sub_sel).first
                        if await sub_btn.is_visible(timeout=3000):
                            self.logger.log_info(f"Clicking submission button: {sub_sel}")
                            await sub_btn.click()
                            await self._random_delay(2, 4)
                            submit_clicked = True
                            break
                    
                    # Step 4: Verification (covers both one-click and multi-step apply)
                    success_indicators = [
                        "div:has-text('Applied successfully')",
                        "div:has-text('application has been submitted')",
                        "button:has-text('Applied')",
                        ".applied-label",
                        ".success-icon",
                        "div:has-text('Thanks for applying')"
                    ]
                    
                    # Wait a bit for success message to appear
                    await asyncio.sleep(2)
                    
                    for indicator in success_indicators:
                        if await page.locator(indicator).count() > 0:
                            self.logger.log_ok(f"FoundIt Success Verified: {indicator}")
                            return True
                            
                    # Final check: Check if the original button itself turned to "Applied"
                    try:
                        final_btn = page.locator(sel).first
                        if await final_btn.count() > 0:
                            btn_text = await final_btn.inner_text()
                            if "applied" in btn_text.lower():
                                self.logger.log_ok("FoundIt Success Verified: Button text is 'Applied'")
                                return True
                    except:
                        pass
                    
                    if submit_clicked:
                        self.logger.log_warn("FoundIt: Application submitted but success not verified")
                        return True # Assume success if we clicked submit and no error occurred
                    
                    # If we reached here without seeing a submit button, it might have been a one-click apply
                    # or it might have failed. Check if we are still on the same page state.
                    return True # Assume success for now if no obvious error
            return False
        except Exception as e:
            self.logger.log_err(f"Apply error: {e}")
            return False
    
    async def _update_profile_resume(self, context: Any) -> bool:
        """Update resume on the profile page to ensure tailored version is used."""
        try:
            selected_path = getattr(self, '_selected_resume_path', None)
            if not selected_path or not os.path.exists(selected_path):
                self.logger.log_warn("No tailored resume selected for profile update")
                return False

            # Open profile in a new tab to avoid losing JD state
            profile_page = await context.new_page()
            await profile_page.goto("https://www.foundit.in/rio/profile", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Try to upload on profile page
            success = await self._upload_resume_from_profile(profile_page)
            
            await profile_page.close()
            if success:
                self.logger.log_ok("Profile resume updated successfully")
            return success
        except Exception as e:
            self.logger.log_err(f"Profile resume update failed: {e}")
            return False

    async def _upload_resume_from_profile(self, page: Page) -> bool:
        """Upload resume to the current page (either apply modal or profile page)."""
        try:
            # Check if we have a selected resume path from ResumeSelector
            selected_path = getattr(self, '_selected_resume_path', None)
            
            if selected_path and os.path.exists(selected_path):
                # Try multiple selectors for file input
                file_selectors = [
                    "input[type='file']",
                    "input[type='file'][accept*='pdf']",
                    "input[type='file'][accept*='document']",
                    "input[name='resume']",
                    "input[name='resumeFile']",
                    "input#resume-upload",
                ]
                
                for sel in file_selectors:
                    file_input = page.locator(sel).first
                    try:
                        # Wait for input to be present (but not necessarily visible yet)
                        if await file_input.count() == 0:
                            try:
                                await file_input.wait_for(state="attached", timeout=5000)
                            except:
                                continue

                        # File inputs are often hidden - reveal them first
                        await file_input.evaluate("""
                            el => {
                                el.style.display = 'block';
                                el.style.visibility = 'visible';
                                el.style.opacity = '1';
                                el.style.height = 'auto';
                                el.style.width = 'auto';
                            }
                        """)
                        
                        self.logger.log_info(f"Uploading resume: {Path(selected_path).name}")
                        await file_input.set_input_files(selected_path)
                        await asyncio.sleep(3) # Wait for upload to process
                        
                        # Verify if upload was accepted
                        # On Profile Page: Look for Save/Update
                        # In Modal: Usually handled by 'Submit' in caller
                        if "profile" in page.url.lower():
                            update_selectors = [
                                "button:has-text('Update')", 
                                "button:has-text('Save')", 
                                ".save-resume-btn",
                                ".upload-resume-btn",
                                "button.btn-primary:has-text('Save')"
                            ]
                            for u_sel in update_selectors:
                                update_btn = page.locator(u_sel).first
                                if await update_btn.is_visible(timeout=2000):
                                    await update_btn.click()
                                    self.logger.log_info(f"Clicked update button: {u_sel}")
                                    await asyncio.sleep(3)
                                    break

                        self.logger.log_ok(f"Resume uploaded/selected: {Path(selected_path).name}")
                        return True
                    except Exception as upload_err:
                        self.logger.log_warn(f"Upload try failed for {sel}: {upload_err}")
                        continue
                
                self.logger.log_warn("No file input found for resume upload")
            
            # FALLBACK: Only if no tailored resume was provided (or generation failed)
            if not selected_path:
                profile = getattr(self, 'profile', None)
                if not profile:
                    return False
                
                student_id = getattr(profile, 'student_id', "") or str(getattr(profile, '_id', ""))
                resume_url = None
                variant = "master"
                
                # 1. Try to find a tailored URL in resume_urls using bucket matching
                resume_urls = getattr(profile, 'resume_urls', {})
                selected_bucket = getattr(self, '_selected_bucket', 'master')
                
                if isinstance(resume_urls, dict) and resume_urls:
                    # First, try to find exact bucket match
                    if selected_bucket in resume_urls and resume_urls[selected_bucket]:
                        resume_url = resume_urls[selected_bucket]
                        variant = selected_bucket
                        self.logger.log_info(f"Found bucket-matched Cloudinary fallback: {selected_bucket}")
                    else:
                        # Fall back to first available tailored resume
                        for key, url in resume_urls.items():
                            if url:
                                resume_url = url
                                variant = key
                                self.logger.log_info(f"Found tailored Cloudinary fallback: {key}")
                                break
                
                # 2. Fallback to master resume URL if no tailored URL found
                if not resume_url:
                    resume_url = getattr(profile, 'resume', "") or getattr(profile, 'resumeUrl', "")
                    if resume_url:
                        self.logger.log_info("Falling back to master resume from Cloudinary...")
                
                if resume_url and resume_url.startswith('http') and student_id:
                    local_path, success = download_resume_from_url(resume_url, student_id, variant)
                    if success and os.path.exists(local_path):
                        file_input = page.locator("input[type='file']").first
                        if await file_input.count() > 0:
                            await file_input.set_input_files(local_path)
                            await asyncio.sleep(2)
                            self.logger.log_ok(f"Fallback resume uploaded: {Path(local_path).name}")
                            return True
            
            return False
        except Exception as e:
            self.logger.log_warn(f"Resume upload failed: {e}")
            return False

    def _resolve_foundit_credentials(self, settings: Any, profile: Any = None) -> tuple[str, str, str]:
        """Resolve FoundIt credentials from MongoDB first, runtime settings fallback."""
        username = ""
        password = ""

        try:
            from database.credentials import get_student_credentials

            candidate_id = self._get_candidate_id(profile or getattr(self, "profile", None))
            creds = get_student_credentials(candidate_id) or {}
            foundit = creds.get("foundit", {}) if isinstance(creds, dict) else {}
            username = (foundit.get("email") or foundit.get("username") or "").strip()
            password = (foundit.get("password") or "").strip()
            if username and password:
                return username, password, "mongodb_credentials"
        except Exception as e:
            self.logger.log_warn(f"MongoDB credential lookup failed: {e}")

        username = (
            getattr(settings, "foundit_email", None)
            or getattr(settings, "foundit_username", None)
            or ""
        ).strip()
        password = (getattr(settings, "foundit_password", None) or "").strip()
        if username and password:
            return username, password, "runtime_settings_fallback"

        return username, password, "missing"

    async def _ensure_logged_in(self, page: Page, settings: Any, profile: Any = None) -> bool:
        """Handle Foundit login with session persistence - tries restore first, then fresh login."""
        # Get student_id from profile
        if profile:
            self.profile = profile
        else:
            profile = getattr(self, "profile", None)
            
        student_id = getattr(profile, "student_id", None) or getattr(profile, "_id", None) or "default"
        
        # Initialize session manager
        session_mgr = SessionManager(student_id, "foundit")
        
        # STEP 1: Try to restore existing session first
        self.logger.log_info(f"Checking for existing session for {student_id}/foundit...")
        session_restored = await session_mgr.restore_session(page)
        
        if session_restored:
            # Verify session is valid by checking we're logged in
            try:
                # Foundit sometimes redirects to /seeker/profile or /seeker/dashboard if logged in
                await page.goto("https://www.foundit.in/rio/profile", timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                current_url = (page.url or "").lower()
                if "login" not in current_url and "otp" not in current_url and ("profile" in current_url or "dashboard" in current_url or "seeker" in current_url):
                    self.logger.log_ok(f"FoundIt session restored successfully for {student_id}")
                    self._logged_in = True
                    return True
                else:
                    self.logger.log_info("Restored session expired or redirected to login, will perform fresh login")
            except Exception as e:
                self.logger.log_info(f"Session verification failed ({e}), will perform fresh login")
        
        # STEP 2: No valid session - perform fresh login
        self.logger.log_info(f"No valid session found, performing fresh FoundIt login for {student_id}")
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                username, password, source = self._resolve_foundit_credentials(settings, profile)
                if not username or not password:
                    self.logger.log_err("FoundIt credentials missing.")
                    return False

                self.logger.log_info(f"FoundIt login attempt {attempt + 1}/{max_retries}")
                
                # Try main site first, then login page
                try:
                    await page.goto("https://www.foundit.in/", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                except:
                    pass
                
                # Navigate to login with retry
                for nav_attempt in range(2):
                    try:
                        await page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                        
                        if "chrome-error" in (page.url or ""):
                            self.logger.log_warn("Got blocked, retrying...")
                            continue
                        break
                    except Exception as nav_err:
                        self.logger.log_warn(f"Navigation attempt {nav_attempt + 1} failed: {nav_err}")
                        await asyncio.sleep(2)

                if "chrome-error" in (page.url or ""):
                    self.logger.log_warn("FoundIt blocked by Chrome error, retrying...")
                    await asyncio.sleep(5)
                    continue

                # Check if we were redirected to profile/dashboard (already logged in)
                current_url = (page.url or "").lower()
                if "login" not in current_url and "otp" not in current_url and ("profile" in current_url or "dashboard" in current_url or "seeker" in current_url):
                    self.logger.log_ok("Redirected away from login page to profile/dashboard - already logged in!")
                    self._logged_in = True
                    await session_mgr.save_session(page)
                    return True

                # Check for popups
                try:
                    close_btn = page.locator("div.close-btn, button.close, .modal-close, button:has-text('×')").first
                    if await close_btn.is_visible(timeout=3000):
                        await close_btn.click()
                except:
                    pass

                # Fill username
                user_field = page.locator("#userName")
                try:
                    await user_field.wait_for(state="visible", timeout=15000)
                except:
                    self.logger.log_warn("Login field not visible")
                    await asyncio.sleep(2)
                    continue

                await user_field.fill(username)
                await asyncio.sleep(1)

                # Toggle to password if needed
                try:
                    lp_toggle = page.locator("span:has-text('Login via Password'), a:has-text('Login via Password')").first
                    if await lp_toggle.is_visible(timeout=3000):
                        await lp_toggle.click()
                        await asyncio.sleep(1.5)
                except:
                    pass

                # Fill password
                pwd_field = page.locator("#password")
                await pwd_field.wait_for(state="visible", timeout=10000)
                await pwd_field.fill(password)
                
                # Click Login
                await page.locator("button:has-text('Login')").click()
                
                await page.wait_for_timeout(5000)

                current_url = (page.url or "").lower()
                if "login" in current_url or "otp" in current_url or "challenge" in current_url:
                    self.logger.log_warn("Still on login page, retrying...")
                    await asyncio.sleep(3)
                    continue
                
                if "chrome-error" in current_url:
                    self.logger.log_warn("Chrome error after login, retrying...")
                    await asyncio.sleep(5)
                    continue

                # STEP 3: Login successful - save session for future use
                self.logger.log_ok("FoundIt login successful. Saving session...")
                await session_mgr.save_session(page)
                
                self._logged_in = True
                self.logger.log_ok(f"FoundIt login successful for {student_id}")
                return True
                
            except Exception as e:
                self.logger.log_warn(f"Login attempt {attempt + 1} error: {e}")
                await asyncio.sleep(3)
        
        self.logger.log_err("FoundIt login failed after all retries")
        return False

    def _build_search_url(self, query: str, location: str, page_num: int = 1) -> str:
        """Construct the search URL for Foundit."""
        import urllib.parse
        loc = location.lower()
        # For the slug, use only the first role to make it look clean
        first_role = query.split(",")[0].strip()
        q_slug = first_role.lower().replace(" ", "-") + "-fresher"
        
        # URL encode the full query: commas become %2C, spaces become %20
        clean_query = query.lower().replace(", ", ",")
        encoded_query = urllib.parse.quote(clean_query)
        
        return f"{self.base_url}/search/{q_slug}-jobs-in-{loc}?start={page_num}&limit=20&query={encoded_query}&locations={loc}&experienceRanges=0~0&experience=0&queryDerived=true"

    async def _random_delay(self, min_sec: float, max_sec: float):
        """Random delay for anti-bot measures constrained by runtime settings."""
        settings = getattr(self, "settings", None)
        configured_min = float(getattr(settings, "min_delay_seconds", min_sec) if settings else min_sec)
        configured_max = float(getattr(settings, "max_delay_seconds", max_sec) if settings else max_sec)

        effective_min = max(float(min_sec), configured_min)
        effective_max = min(float(max_sec), configured_max)

        if effective_max < effective_min:
            effective_max = effective_min

        await asyncio.sleep(random.uniform(effective_min, effective_max))
    
    async def _generate_ai_resume(self, jd_text: str, student_id: str, profile: Any) -> Optional[str]:
        """Generate AI tailored resume using API"""
        import shutil
        import requests
        from pathlib import Path
        
        api_base = os.getenv("LOCAL_API_URL", "http://ai-engine:8000").rstrip("/")
        api_url = f"{api_base}/generate"
        
        try:
            # Get master resume
            master_resume_path = None
            if hasattr(profile, 'resume_path') and profile.resume_path:
                master_resume_path = profile.resume_path
            
            if not master_resume_path:
                master_resume_path = os.getenv("STUDENT_RESUME_PATH")
            
            # Extract text from master
            retrieved_chunks = ""
            if master_resume_path and os.path.exists(master_resume_path):
                from utils.pdf_reader import extract_text_from_pdf
                try:
                    master_text = extract_text_from_pdf(master_resume_path)
                    links = getattr(profile, 'extra', {})
                    linkedin = links.get('linkedin', '')
                    github = links.get('github', '')
                    header = f"NAME: {getattr(profile, 'name', 'Candidate')}\nEMAIL: {getattr(profile, 'email', '')}\nPHONE: {getattr(profile, 'phone', '')}\nLOCATION: {getattr(profile, 'location', '')}\nLINKEDIN: {linkedin}\nGITHUB: {github}\n"
                    retrieved_chunks = header + "\n\n" + master_text
                except Exception as e:
                    self.logger.log_warn(f"Could not extract master resume: {e}")
                    retrieved_chunks = str(profile)
            else:
                retrieved_chunks = str(profile)
            
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
