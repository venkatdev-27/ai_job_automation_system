import asyncio
import random
from dataclasses import dataclass
from typing import Any, Callable, Coroutine


FetchAttemptFn = Callable[[], Coroutine[Any, Any, tuple[list[dict[str, Any]], int, str]]]


@dataclass
class FetchResult:
    jobs: list[dict[str, Any]]
    decision: dict[str, Any]


class JobFetchStrategyController:
    blocked_status_codes = {403, 406, 429}

    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger

    async def execute(
        self,
        *,
        platform: str,
        query: str,
        previous_status: int = 0,
        attempt_type: str = "http",
        retry_count: int = 0,
        http_attempt: FetchAttemptFn | None = None,
        playwright_attempt: FetchAttemptFn | None = None,
        cache_attempt: FetchAttemptFn | None = None,
    ) -> FetchResult:
        platform_name = (platform or "").strip().lower()
        result = self._decision(
            platform=platform_name,
            query=query,
            method_used=attempt_type,
            status="skipped",
            jobs_found=0,
            next_action="stop",
            notes="No attempt executed.",
        )

        if retry_count > self.settings.max_fetch_retry_count:
            jobs, _, notes = await self._safe_call(cache_attempt)
            if jobs:
                return FetchResult(
                    jobs=jobs,
                    decision=self._decision(
                        platform=platform_name,
                        query=query,
                        method_used="cache",
                        status="success",
                        jobs_found=len(jobs),
                        next_action="continue",
                        notes=f"Retry limit reached; using cache. {notes}".strip(),
                    ),
                )
            return FetchResult(
                jobs=[],
                decision=self._decision(
                    platform=platform_name,
                    query=query,
                    method_used="skip",
                    status="skipped",
                    jobs_found=0,
                    next_action="stop",
                    notes="Retry limit exceeded and no cache available.",
                ),
            )

        strategy = str(getattr(self.settings, "fetch_strategy", "auto")).strip().lower()

        if strategy == "playwright" and playwright_attempt:
            self.logger.info("🔥 Strategy is 'playwright': Forcing Playwright attempt first.")
            await self._human_delay()
            jobs, status_code, notes = await self._safe_call(playwright_attempt)
            if jobs:
                result = self._decision(
                    platform=platform_name,
                    query=query,
                    method_used="playwright",
                    status="success",
                    jobs_found=len(jobs),
                    next_action="continue",
                    notes=notes or "Forced Playwright fetch succeeded.",
                )
                return FetchResult(jobs=jobs, decision=result)
            else:
                result = self._decision(
                    platform=platform_name,
                    query=query,
                    method_used="playwright",
                    status="skipped",
                    jobs_found=0,
                    next_action="fallback",
                    notes=f"Forced Playwright returned no jobs. {notes}",
                )

        if strategy != "playwright":
            prefer_http = self._can_try_http(platform_name, retry_count)
            if prefer_http and http_attempt:
                await self._human_delay()
                jobs, status_code, notes = await self._safe_call(http_attempt)
                if status_code == 200 and jobs:
                    result = self._decision(
                        platform=platform_name,
                        query=query,
                        method_used="http",
                        status="success",
                        jobs_found=len(jobs),
                        next_action="continue",
                        notes=notes or "HTTP fetch succeeded.",
                    )
                    return FetchResult(jobs=jobs, decision=result)

                blocked = status_code in self.blocked_status_codes
                result = self._decision(
                    platform=platform_name,
                    query=query,
                    method_used="http",
                    status="blocked" if blocked else "skipped",
                    jobs_found=0,
                    next_action="fallback",
                    notes=f"HTTP failed (status={status_code}). {notes}",
                )

        if strategy != "playwright" and playwright_attempt:
            await self._human_delay()
            jobs, status_code, notes = await self._safe_call(playwright_attempt)
            if jobs:
                result = self._decision(
                    platform=platform_name,
                    query=query,
                    method_used="playwright",
                    status="success",
                    jobs_found=len(jobs),
                    next_action="continue",
                    notes=notes or "Playwright fallback fetch succeeded.",
                )
                return FetchResult(jobs=jobs, decision=result)

            blocked = (status_code in self.blocked_status_codes) or ("captcha" in (notes or "").lower())
            result = self._decision(
                platform=platform_name,
                query=query,
                method_used="playwright",
                status="blocked" if blocked else "skipped",
                jobs_found=0,
                next_action="fallback",
                notes=f"Playwright fallback failed. {notes}",
            )

        jobs, _, notes = await self._safe_call(cache_attempt)
        if jobs:
            result = self._decision(
                platform=platform_name,
                query=query,
                method_used="cache",
                status="success",
                jobs_found=len(jobs),
                next_action="continue",
                notes=notes or "Using cached jobs.",
            )
            return FetchResult(jobs=jobs, decision=result)

        # Do not overwrite 'result' here if we already have an attempt recorded.
        if result.get("method_used") in {"skip", "stop", "unknown"}:
            result = self._decision(
                platform=platform_name,
                query=query,
                method_used="skip",
                status="skipped",
                jobs_found=0,
                next_action="stop",
                notes="No jobs found in HTTP/Playwright/cache fallbacks.",
            )
        return FetchResult(jobs=[], decision=result)

    def _can_try_http(self, platform: str, retry_count: int) -> bool:
        if retry_count != 0:
            return False

        strategy = str(getattr(self.settings, "fetch_strategy", "auto")).strip().lower()
        disabled_platforms = {
            str(item).strip().lower()
            for item in getattr(self.settings, "http_disabled_platforms", [])
            if str(item).strip()
        }

        if strategy == "playwright" and platform in disabled_platforms:
            return False

        if platform == "linkedin":
            return False
        return platform == "naukri"

    async def _human_delay(self) -> None:
        lower = min(self.settings.min_fetch_delay_seconds, self.settings.max_fetch_delay_seconds)
        upper = max(self.settings.min_fetch_delay_seconds, self.settings.max_fetch_delay_seconds)
        await asyncio.sleep(random.uniform(lower, upper))

    async def _safe_call(
        self, fn: FetchAttemptFn | None
    ) -> tuple[list[dict[str, Any]], int, str]:
        if not fn:
            return [], 0, ""
        try:
            # Execute result and check if it's a coroutine object
            result = fn()
            
            if asyncio.iscoroutine(result):
                jobs, status_code, notes = await result
            else:
                # If it's already a tuple (sync result)
                jobs, status_code, notes = result
                
            jobs = jobs if isinstance(jobs, list) else []
            return jobs, int(status_code or 0), str(notes or "")
        except Exception as exc:
            self.logger.warning("Fetch attempt failed: %s", exc)
            return [], 0, f"Exception: {exc}"

    def _decision(
        self,
        *,
        platform: str,
        query: str,
        method_used: str,
        status: str,
        jobs_found: int,
        next_action: str,
        notes: str,
    ) -> dict[str, Any]:
        return {
            "platform": platform,
            "query": query,
            "method_used": method_used,
            "status": status,
            "jobs_found": int(jobs_found),
            "next_action": next_action,
            "notes": notes,
        }
