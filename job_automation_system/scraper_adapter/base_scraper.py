import asyncio
import random
import os
import sys
from pathlib import Path

# Ensure the job_automation_system root is in sys.path to avoid shadowing by top-level ai_engine
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional
from playwright.async_api import Page
from urllib.parse import urlencode

import httpx

from utils.dedupe import canonical_job_key
try:
    from job_automation_system.ai_engine.fetch_strategy_controller import JobFetchStrategyController
except ImportError:
    try:
        from ai_engine.fetch_strategy_controller import JobFetchStrategyController  # type: ignore
    except ImportError:
        JobFetchStrategyController = None
from config.settings import settings
from utils.helpers import read_json
from utils.job_utils import (
    is_fresher_friendly,
    location_score,
    normalize_job_payload,
    normalize_url,
)


class BaseScraper(ABC):
    source = "base"
    base_url = ""

    def __init__(self, max_results: int = 20, timeout_seconds: int = 25, logger: Any = None) -> None:
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds
        self.logger = logger
        self.fetch_decisions: list[dict[str, Any]] = []
        self.seen_urls_lock = asyncio.Lock()
        self._status_codes: list[int] = []
        self._last_request_at = 0.0
        self._http_client: httpx.AsyncClient | None = None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    @abstractmethod
    async def search_jobs(self, profile: Any, settings: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def build_job(
        self,
        title: str,
        company: str,
        location: str,
        url: str,
        description: str,
        *,
        required_skills: list[str] | None = None,
        employment_type: str = "",
        experience_text: str = "",
        experience_min: int = 0,
        experience_max: int = 99,
        apply_link: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        payload = {
            "source": self.source,
            "title": title,
            "company": company,
            "location": location,
            "url": normalize_url(url, self.base_url or None),
            "apply_link": normalize_url(apply_link or url, self.base_url or None),
            "description": description,
            "required_skills": required_skills or [],
            "employment_type": employment_type,
            "experience_text": experience_text,
            "experience_min": experience_min,
            "experience_max": experience_max,
            "posted_at": now,
            "metadata": metadata or {},
        }
        return normalize_job_payload(payload)

    def _track_status(self, status_code: int) -> None:
        if status_code:
            self._status_codes.append(int(status_code))

    def _last_status(self) -> int:
        if not self._status_codes:
            return 0
        for code in self._status_codes:
            if code in {403, 406, 429}:
                return code
        if 200 in self._status_codes:
            return 200
        return self._status_codes[-1]

    async def _throttle(self) -> None:
        min_delay = 0.5
        max_delay = 1.5
        if hasattr(self, "settings_ref") and self.settings_ref is not None:
            min_delay = float(getattr(self.settings_ref, "min_fetch_delay_seconds", 2.0))
            max_delay = float(getattr(self.settings_ref, "max_fetch_delay_seconds", 5.0))
        lower = min(min_delay, max_delay)
        upper = max(min_delay, max_delay)

        import time
        now = time.time()
        elapsed = now - self._last_request_at
        target = random.uniform(lower, upper)
        if elapsed < target:
            await asyncio.sleep(target - elapsed)
        self._last_request_at = time.time()

    async def _http_get_with_status(self, url: str, params: dict[str, Any] | None = None) -> tuple[str, int]:
        await self._throttle()
        try:
            client = await self._get_http_client()
            response = await client.get(url, params=params)
            self._track_status(response.status_code)
            response.raise_for_status()
            return response.text, response.status_code
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            self._track_status(code)
            if self.logger:
                self.logger.warning("%s GET failed: %s | HTTP %s", self.source, url, code)
            return "", code
        except Exception as exc:
            if self.logger:
                self.logger.warning("%s GET failed: %s | %s", self.source, url, exc)
            return "", 0

    async def _http_get(self, url: str, params: dict[str, Any] | None = None) -> str:
        text, _ = await self._http_get_with_status(url, params=params)
        return text

    async def _http_get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self._throttle()
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)

        try:
            client = await self._get_http_client(headers=headers)
            response = await client.get(url, params=params)
            self._track_status(response.status_code)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            self._track_status(code)
            if self.logger:
                self.logger.warning("%s GET JSON failed: %s | HTTP %s", self.source, url, code)
            return {}
        except Exception as exc:
            if self.logger:
                self.logger.warning("%s GET JSON failed: %s | %s", self.source, url, exc)
            return {}

    async def _get_http_client(self, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                headers=headers or self.headers,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        elif headers and dict(self._http_client.headers) != headers:
            await self._http_client.aclose()
            self._http_client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        return self._http_client

    async def _playwright_get(self, url: str, params: dict[str, Any] | None = None) -> tuple[str, int, str]:
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"

        print(f"🔥 PLAYWRIGHT CALLED: {url}")
        
        from scraper_adapter.playwright_manager import playwright_manager
        
        try:
            settings = getattr(self, "settings_ref", None)
            page = await playwright_manager.get_page(settings)
                      # Auto-login helper
            await self._platform_login_if_needed(page, url)
            
            # STEP 3: FAST navigation
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            # Reduced throttle/scroll timing
            await page.mouse.wheel(0, 5000)
            await page.wait_for_timeout(200)
            
            html = await page.content()
            body_text = await page.inner_text("body")
            text = body_text.lower()
            
            # Return page to pool instead of closing
            await playwright_manager.return_page(page)
            
            if "captcha" in text and ("verify" in text or "robot" in text):
                return "", 429, "captcha_detected"
            
            return html, 200, "playwright_ok"
        except Exception as exc:
            # Try to return the page even if it failed
            try:
                await playwright_manager.return_page(page)
            except:
                pass
            return "", 0, f"playwright_error: {exc}"

    async def simulate_human_behavior(self, page: Page):
        """v3 Stealth Strike: Mimic real human kinetic activity."""
        import random
        try:
            # 1. Randomized Mouse Movements
            for _ in range(3):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y, steps=10)
                await asyncio.sleep(random.uniform(0.5, 1.2))

            # 2. Kinetic Scrolling Pulse
            scroll_dist = random.randint(200, 500)
            await page.mouse.wheel(0, scroll_dist)
            await asyncio.sleep(1)
            await page.mouse.wheel(0, -200) # Slight snap-back
            
            await asyncio.sleep(random.uniform(1, 2))
        except Exception:
            pass
            
    async def _playwright_page_exec(self, url: str, callback: Callable[[Page], Coroutine[Any, Any, Any]], navigate: bool = True) -> Any:
        """
        New optimized execution method that reuses pages and allows direct locator usage.
        """
        from scraper_adapter.playwright_manager import playwright_manager
        settings = getattr(self, "settings_ref", None)
        page = await playwright_manager.get_page(settings)
        try:
            # MANDATORY V2 AUTH GATEKEEPER
            auth_success = await self.ensure_authenticated(page)
            if not auth_success:
                self.logger.log_err(f"CRITICAL: {self.source} authentication failed. Aborting execution.")
                return None
            
            if navigate and url:
                if page.url != url:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    # v3 Stabilized Stealth: 5s Bio-Wait + Jitter (Safe alternative to networkidle)
                    self.logger.log_info("Waiting 5.0s for high-fidelity stabilization...")
                    await asyncio.sleep(5) 
                    await self.simulate_human_behavior(page)
                    
                    # Evidence Verification Sweep
                    content_peek = await page.content()
                    if "Something went wrong" in content_peek:
                        self.logger.log_err("Oops! Redirect Detected. Anti-bot triggered.")
                else:
                    self.logger.log_info(f"Already on target URL: {url}. Skipping navigation.")
            
            return await callback(page)
        finally:
            await playwright_manager.return_page(page)

    async def ensure_authenticated(self, page: Page) -> bool:
        """
        MANDATORY GATEKEEPER: Verifies identity or performs strict login.
        """
        if not hasattr(self, "settings_ref") or self.settings_ref is None:
            return False

        source = str(getattr(self, "source", "")).lower()
        email = ""
        password = ""
        login_url = ""
        check_url = ""
        email_selectors = []
        password_selectors = []
        submit_selectors = []

        if source == "linkedin":
            email = str(getattr(self.settings_ref, "linkedin_email", "")).strip()
            password = str(getattr(self.settings_ref, "linkedin_password", "")).strip()
            login_url = "https://www.linkedin.com/login"
            check_url = "https://www.linkedin.com/feed/"
            email_selectors = ["#username", "input#username", "input[name='session_key']", "input[type='email']"]
            password_selectors = ["#password", "input#password", "input[name='session_password']", "input[type='password']"]
            submit_selectors = ["button[type='submit']", ".btn__primary--large", "button:has-text('Sign in')"]
        elif source == "naukri":
            email = str(getattr(self.settings_ref, "naukri_email", "")).strip()
            password = str(getattr(self.settings_ref, "naukri_password", "")).strip()
            login_url = "https://www.naukri.com/nlogin/login"
            check_url = "https://www.naukri.com/mnjuser/homepage"
            # STRICT ID USE ONLY: Prevent accidental typing into search bars
            email_selectors = ["#usernameField"]
            password_selectors = ["#passwordField"]
            submit_selectors = ["button[type='submit']"]

        if not email or not password:
            self.logger.log_warn(f"MISSING CREDENTIALS for {source}. Skipping automated login.")
            return False

        # 1. Check if already logged in (Strict Check)
        logged_in_indicators = [
            "#global-nav", ".nI-gNb-header__user-avatar", ".nav-main", 
            "#nav-bar", ".nav-container", ".global-nav", "a[href*='/homepage']",
            "a[href*='/feed']"
        ]

        if check_url:
            try:
                # FIRST: Lightweight check on current URL (Avoids reloads)
                for indicator in logged_in_indicators:
                    if await page.locator(indicator).count() > 0:
                        self.logger.log_ok(f"[OK] VERIFIED: {source} session is already active on current page.")
                        return True
                
                # SECOND: If not detected, try the dedicated check_url
                current_url = page.url.lower()
                if check_url not in current_url:
                    await page.goto(check_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                
                is_logged_in = False
                for indicator in logged_in_indicators:
                    if await page.locator(indicator).count() > 0:
                        is_logged_in = True
                        break
                
                if is_logged_in:
                    self.logger.log_ok(f"[OK] VERIFIED: {source} session is active on {source}.")
                    return True
            except Exception as e:
                self.logger.log_warn(f"Session check failed for {source}: {e}")

        # 2. Perform Brute-Force Login
        self.logger.log_info(f"Performing PROMPT AUTOMATED LOGIN for {source}...")
        try:
            # ANTI-SEARCH GUARD: If we are on the home page, do not attempt automated login
            if "naukri.com" in page.url.lower() and "login" not in page.url.lower() and "homepage" not in page.url.lower():
                self.logger.log_warn("Forced Redirect to Home Page detected. Aborting automated login pulse to prevent search drift.")
                return False

            await page.goto(login_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
            
            # Find and fill Email
            for sel in email_selectors:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    self.logger.log_info(f"Typing email into '{sel}'...")
                    await el.fill(email)
                    break
            
            # Find and fill Password
            for sel in password_selectors:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    self.logger.log_info(f"Typing password into '{sel}'...")
                    await el.fill(password)
                    break
            
            await asyncio.sleep(random.uniform(0.5, 1.2))
            
            # Click Submit
            for sel in submit_selectors:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    self.logger.log_info(f"Clicking final Sign-in button: '{sel}'")
                    await el.click()
                    break
            
            # 3. Handle Security Walls / Verification
            await asyncio.sleep(5)
            if "checkpoint" in page.url or "captcha" in page.url or "challenge" in page.url:
                self.logger.log_warn("--- SECURITY CHECKPOINT DETECTED ---")
                self.logger.log_warn("Please solve the CHALLENGE manually in the browser window.")
                # Wait up to 5 minutes for manual resolution
                for i in range(300):
                    if check_url in page.url or "feed" in page.url or "homepage" in page.url:
                        self.logger.log_ok("AUTHENTICATION SUCCESSFUL: Checkpoint resolved.")
                        return True
                    await asyncio.sleep(1)
                return False

            await page.wait_for_url("**/feed**" if source=="linkedin" else "**/homepage**", timeout=20000)
            self.logger.log_ok(f"AUTHENTICATION SUCCESSFUL for {source}.")
            return True
        except Exception as e:
            self.logger.log_err(f"Automated login failed for {source}: {e}")
            return False
    async def _take_auth_screenshot(self, page: Page, name: str) -> str:
        """Captures a diagnostic screenshot for authentication failures."""
        try:
            folder = Path(settings.base_dir) / "storage" / "auth_debug"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{name}_{int(asyncio.get_event_loop().time())}.png"
            await page.screenshot(path=str(path))
            return str(path)
        except Exception:
            return "failed_to_capture"

    def _soup(self, html: str) -> Any:
        try:
            from bs4 import BeautifulSoup

            return BeautifulSoup(html or "", "html.parser")
        except Exception:
            return None

    def _get_queries(self, profile: Any, settings: Any) -> list[str]:
        raw = profile.candidate_titles or settings.include_keywords
        return [query for query in raw[: settings.max_queries_per_platform] if str(query).strip()]

    def _get_locations(self, profile: Any, settings: Any) -> list[str]:
        raw = settings.preferred_locations or [profile.location]
        return [location for location in raw[: settings.max_locations_per_query] if str(location).strip()]

    async def _cache_attempt(self, query: str, settings: Any) -> tuple[list[dict[str, Any]], int, str]:
        cached = read_json(settings.jobs_catalog_file, default=[])
        applied = read_json(settings.applied_jobs_file, default=[])
        applied_keys = {str(item) for item in applied if isinstance(item, str)}
        if not isinstance(cached, list):
            return [], 0, "cache_unavailable"

        query_tokens = [token for token in str(query).lower().split() if token]
        filtered: list[dict[str, Any]] = []

        for item in cached:
            if not isinstance(item, dict):
                continue
            if str(item.get("source", "")).lower() != self.source:
                continue
            try:
                if canonical_job_key(item) in applied_keys:
                    continue
            except Exception:
                pass
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("company", "")),
                    str(item.get("description", "")),
                ]
            ).lower()
            if query_tokens and not any(token in haystack for token in query_tokens):
                continue
            filtered.append(item)
            if len(filtered) >= self.max_results:
                break

        if filtered:
            return filtered, 200, "cache_hit"
        return [], 204, "cache_miss"

    async def _run_fetch_strategy(
        self,
        *,
        platform: str,
        query: str,
        settings: Any,
        retry_count: int,
        http_attempt: Optional[Callable[[], Coroutine[Any, Any, tuple[list[dict[str, Any]], int, str]]]] = None,
        playwright_attempt: Optional[Callable[[], Coroutine[Any, Any, tuple[list[dict[str, Any]], int, str]]]] = None,
    ) -> list[dict[str, Any]]:
        from typing import Optional
        controller = JobFetchStrategyController(settings, self.logger)
        
        # Wrapped for controller logic
        async def cache_wrapped():
            return await self._cache_attempt(query, settings)
            
        result = await controller.execute(
            platform=platform,
            query=query,
            previous_status=self._last_status(),
            attempt_type="http",
            retry_count=retry_count,
            http_attempt=http_attempt,
            playwright_attempt=playwright_attempt,
            cache_attempt=cache_wrapped,
        )
        self.fetch_decisions.append(result.decision)
        if self.logger:
            self.logger.info("Fetch strategy: %s", result.decision)
        return result.jobs

    def finalize_jobs(self, jobs: list[dict[str, Any]], profile: Any, settings: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        preferred_types = [item.lower() for item in settings.preferred_job_types]

        for raw in jobs:
            job = normalize_job_payload(raw)
            if not job.get("title") or not job.get("url"):
                continue

            joined_text = " ".join(
                [
                    str(job.get("title", "")),
                    str(job.get("description", "")),
                    str(job.get("experience_text", "")),
                ]
            )
            if settings.strict_fresher_only and not is_fresher_friendly(
                joined_text, max_experience=settings.max_experience_years
            ):
                continue

            if preferred_types and job.get("employment_type", "unknown").lower() not in preferred_types:
                if job.get("employment_type", "unknown").lower() != "unknown":
                    continue

            if settings.preferred_locations:
                if location_score(str(job.get("location", "")), settings.preferred_locations) <= 0:
                    location_text = str(job.get("location", "")).lower()
                    if "remote" not in location_text:
                        continue

            output.append(job)
            if len(output) >= self.max_results:
                break

        return output
