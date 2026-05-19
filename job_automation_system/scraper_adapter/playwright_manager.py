import asyncio
import os
import random
import gc
import psutil
from typing import Any, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import settings

class PlaywrightManager:
    """
    Step 10 Optimization: Reuse Browser & Context.
    Implements a singleton manager to avoid the high cost of re-launching Playwright.
    Now supports per-student Chrome profiles for session isolation.
    Includes: Worker recycling, CPU-aware scheduling, resource blocking.
    """
    _instance: Optional['PlaywrightManager'] = None
    _p: Any = None
    _browser: Optional[Browser] = None
    _contexts: dict[str, BrowserContext] = {}  # Per-student contexts
    _page_pool: list[Page] = []
    _current_student_id: Optional[str] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PlaywrightManager, cls).__new__(cls)
            cls._instance._recycle_counter = 0  # Turbo Armor: Track pages for recycling
            cls._instance._loop_id = None
            cls._instance._student_count = 0  # Track students processed
            cls._instance._last_platform = None  # Track platform switches
        return cls._instance

    def _is_docker(self) -> bool:
        return os.environ.get("IN_DOCKER", "").lower() == "true" or Path("/app").exists()

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value).strip("_") or "default"

    # ============================================================
    # 5. Worker Recycling - Restart after 30-50 students
    # ============================================================
    def _check_worker_recycle(self) -> bool:
        """Check if worker needs recycling (prevents memory leaks)."""
        recycle_threshold = int(os.environ.get("WORKER_RECYCLE_AFTER", "40"))
        if self._student_count >= recycle_threshold:
            return True
        return False

    def _should_recycle(self, student_id: str = None) -> bool:
        """Check if worker needs recycling and mark student as processed."""
        if student_id:
            self._student_count += 1
        return self._check_worker_recycle()

    # ============================================================
    # 6. CPU-Aware Scheduler - Wait if CPU > 80%
    # ============================================================
    async def _wait_for_cpu(self):
        """Wait if CPU > 80% to prevent overheating spikes."""
        try:
            cpu_threshold = float(os.environ.get("CPU_THRESHOLD", "80"))
            max_wait = int(os.environ.get("CPU_MAX_WAIT", "60"))
            
            for wait_sec in range(max_wait):
                cpu_percent = psutil.cpu_percent(interval=1)
                if cpu_percent < cpu_threshold:
                    return True
            return False
        except Exception:
            return True  # If psutil fails, continue

    # ============================================================
    # 7. Stagger Browser Starts - Every 10-20 seconds
    # ============================================================
    async def _stagger_browser_start(self):
        """Stagger browser launches to prevent spikes."""
        stagger_ms = int(os.environ.get("STAGGER_BROWSER_MS", "15000"))
        # Add random jitter (±20%)
        stagger_with_jitter = stagger_ms + random.randint(-3000, 3000)
        await asyncio.sleep(stagger_with_jitter / 1000)

    # ============================================================
    # 8. Cleanup Between Platforms
    # ============================================================
    async def cleanup_for_platform(self, platform: str):
        """Cleanup before switching platforms."""
        # Force garbage collection
        gc.collect()
        
        # If switching platforms, full cleanup
        if self._last_platform and self._last_platform != platform:
            # Close all contexts
            for ctx_key in list(self._contexts.keys()):
                try:
                    ctx = self._contexts.pop(ctx_key, None)
                    if ctx:
                        await ctx.close()
                except Exception:
                    pass
            
            # Clear page pool
            for page in self._page_pool:
                try:
                    if not page.is_closed():
                        await page.close()
                except Exception:
                    pass
            self._page_pool = []
        
        self._last_platform = platform

    async def full_cleanup(self):
        """Full cleanup - kill Chrome leftovers, gc, close workers."""
        import subprocess
        
        # Kill Chrome leftovers (zombie processes)
        try:
            subprocess.run(
                ["pkill", "-9", "-f", "chrome"],
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["pkill", "-9", "-f", "chromium"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
        
        # Close all contexts
        for ctx_key in list(self._contexts.keys()):
            try:
                ctx = self._contexts.pop(ctx_key, None)
                if ctx:
                    await ctx.close()
            except Exception:
                pass
        
        # Clear page pool
        for page in self._page_pool:
            try:
                if not page.is_closed():
                    await page.close()
            except Exception:
                pass
        self._page_pool = []
        
        # Force garbage collection
        gc.collect()

        # Mark for recycling
        self._student_count = 0

    # ============================================================
    # CPU-Aware: Call before starting browsers
    # ============================================================
    async def prepare_for_platform(self, platform: str):
        """CPU-aware + cleanup before starting a platform."""
        # Cleanup if switching platforms
        await self.cleanup_for_platform(platform)
        
        # Wait for CPU to cool down
        if platform == "linkedin":  # CPU-intensive
            await self._wait_for_cpu()
        
        return True

    def _base_profile_dir(self, settings: Any) -> Path:
        """Return a Linux-safe profile base inside Docker, even if .env has Windows paths."""
        raw_dir = (
            os.environ.get("CHROME_PROFILE_DIR")
            or getattr(settings, "chrome_profile_dir", None)
            or "/app/chrome_profile"
        )
        raw_text = str(raw_dir).strip()
        is_windows_path = len(raw_text) >= 2 and raw_text[1] == ":"
        if self._is_docker() and is_windows_path:
            raw_text = "/app/chrome_profile"
        return Path(raw_text).resolve()

    def _profile_namespace(self) -> str:
        """Separate profiles per queue/container so Firefox profile locks don't collide."""
        return self._safe_name(
            os.environ.get("PROFILE_NAMESPACE")
            or os.environ.get("CELERY_QUEUE")
            or os.environ.get("HOSTNAME")
            or "worker"
        )

    def _reset_if_loop_changed(self) -> None:
        """Avoid reusing Playwright futures created by a previous asyncio.run loop."""
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            return
        if self._loop_id is None:
            self._loop_id = loop_id
            return
        if self._loop_id != loop_id:
            self._page_pool = []
            self._contexts = {}
            self._browser = None
            self._p = None
            self._loop_id = loop_id

    def _get_student_profile_dir(self, settings: Any, student_id: str) -> Path:
        """Get Chrome profile directory for a specific student."""
        base_dir = self._base_profile_dir(settings)
        base_dir = base_dir.parent / "chromium_profile"
        
        if not base_dir.exists():
            base_dir.mkdir(parents=True, exist_ok=True)
            
        student_dir = base_dir / self._profile_namespace() / self._safe_name(student_id)
        student_dir.mkdir(parents=True, exist_ok=True)
        return student_dir

    async def get_context(self, settings: Any, student_id: str = None) -> BrowserContext:
        """
        Retrieves or initializes the singular, optimized persistent browser context.
        Uses a real Chrome profile on the D: drive to maintain sessions.
        """
        self._reset_if_loop_changed()
        context_key = student_id or "_default"
        existing_context = self._contexts.get(context_key)
        if existing_context and self._p:
            try:
                # Check if context is still valid
                await existing_context.cookies()
                return existing_context
            except Exception as e:
                # SELF-HEALING: Detect closed pipe or disconnected browser
                if any(err in str(e).lower() for err in ["closed", "pipe", "disconnected", "connection"]):
                    from utils.logger import get_logger
                    log_file = getattr(settings, "run_log_file", "pipeline.log")
                    tmp_log = get_logger(log_file)
                    tmp_log.log_warn(f"[RECOVERY] Browser pipe disconnected for {student_id}. Resetting...")
                    if student_id:
                        await self.close_student_context(student_id)  # Force clean reset
                    else:
                        await self.close_context()
                self._contexts.pop(context_key, None)

        if not self._p:
            await self._force_kill_chrome()
            self._p = await async_playwright().start()

        if student_id:
            user_data_dir = self._get_student_profile_dir(settings, student_id)
        else:
            base_dir = self._base_profile_dir(settings)
            user_data_dir = base_dir.parent / "chromium_profile"
            user_data_dir = user_data_dir / self._profile_namespace() / "_default"

        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up stale Chrome lock files to prevent "SingletonLock" errors
        try:
            for lock_file in user_data_dir.glob("Singleton*"):
                lock_file.unlink()
            for socket_file in user_data_dir.glob("*.sock"):
                socket_file.unlink()
        except Exception:
            pass

        # Force headless mode for Docker - use settings as single source of truth
        headless = getattr(settings, "playwright_headless", True)
        if self._is_docker():
            headless = True # Enforce headless in docker regardless of other settings

        proxy = None
        if getattr(settings, "proxy_server", None):
            proxy = {"server": settings.proxy_server}
        # Revert to stable Desktop UA
        selected_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        
        for attempt in range(3):
            try:
                browser_type = "chromium"  # Always use chromium
                browser_launcher = self._p.chromium
                
                context = await browser_launcher.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=headless,
                    proxy=proxy,
                    user_agent=selected_ua,
                    viewport={"width": 1280, "height": 720},
                    locale="en-US",
                    timezone_id="UTC",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": "https://www.naukri.com/",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                    },
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--disable-default-apps",
                        "--disable-sync",
                        "--disable-translate",
                        "--metrics-recording-only",
                        "--no-first-run",
                    ],
                )

                
                self._contexts[context_key] = context
                self._browser = context.browser
                self._current_student_id = student_id
                
                break
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))

        return self._contexts[context_key]

    async def get_page(self, settings: Any, student_id: str = None) -> Page:
        """
        Retrieves a page from the pool or creates a new one.
        Uses per-student context for isolation.
        """
        context = await self.get_context(settings, student_id)
        
        try:
            await context.cookies() 
        except Exception as e:
            if any(err in str(e).lower() for err in ["closed", "pipe", "disconnected", "connection"]):
                await self.close_student_context(student_id)
                context = await self.get_context(settings, student_id)
            else: raise
        
        self._page_pool = [p for p in self._page_pool if not p.is_closed()]
        
        if self._page_pool:
            return self._page_pool.pop()

        page = await context.new_page()
        page.set_default_timeout(20000)
        page.set_default_navigation_timeout(30000)
        
        await self._apply_stealth(page)
        return page

    async def _apply_stealth(self, page: Page):
        """Applies anti-detection scripts and stealth to a page."""
        # Enhanced anti-automation spoofing - bypass bot detection
        await page.add_init_script("""() => {
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
                writable: true
            });
            
            // Spoof platform - MUST NOT BE NULL
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });

            // Spoof vendor
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
                configurable: true
            });

            // Spoof plugins to look like real Chrome
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            });

            
            // Spoof languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            
            // Spoof hardware concurrency
            if (navigator.hardwareConcurrency !== undefined) {
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8,
                    configurable: true
                });
            }
            
            // Spoof device memory
            if (navigator.deviceMemory !== undefined) {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                    configurable: true
                });
            }
            
            // Spoof chrome runtime
            if (window.chrome) {
                Object.defineProperty(window.chrome, 'runtime', {
                    get: () => ({ installed: true, version: '120.0.6099.71' }),
                    configurable: true
                });
            }
            
            // Clear all automation detection variables
            window.cdc_adoQpoasnfaofpintcsj = undefined;
            window.$cdc_asdjflasutopfhisd = undefined;
            window.$chrome_asyncScriptInfo = undefined;
            window.__webdriver_script = undefined;
            window.webdriver = undefined;
            window.__webdriver = undefined;
            window.cdc_adoQpoasnfa = undefined;
            window.$cdc_asdflg = undefined;
            
            // Chrome object
            window.navigator.chrome = window.navigator.chrome || {
                app: { installed: true },
                runtime: { id: 'gcmjkmfnpdpclmfimdmclfapobgjff', version: '120.0.6099.71' }
            };
            
            // Permissions
            if (navigator.permissions !== undefined) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(params) {
                    if (params.name === 'notifications') {
                        return Promise.resolve({ state: 'prompt' });
                    }
                    return originalQuery.call(this, params);
                };
            }
            
            // Fake clipboard
            if (navigator.clipboard !== undefined) {
                Object.defineProperty(navigator, 'clipboard', {
                    get: () => ({ 
                        readText: () => Promise.resolve(''),
                        writeText: () => Promise.resolve()
                    }),
                    configurable: true
                });
            }
            
            // Connection info
            if (navigator.connection !== undefined) {
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({ 
                        effectiveType: '4g',
                        downlink: 10,
                        rtt: 50,
                        saveData: false
                    }),
                    configurable: true
                });
            }
            
            // Media devices
            if (navigator.mediaDevices !== undefined) {
                Object.defineProperty(navigator.mediaDevices, 'enumerateDevices', {
                    get: () => () => Promise.resolve([
                        { deviceId: 'default', kind: 'audioinput', label: 'Microphone' },
                        { deviceId: 'default', kind: 'videoinput', label: 'Camera' }
                    ]),
                    configurable: true
                });
            }
            
// Generator
            try {
                const magicArray = Array.from({ length: 100 }, (_, i) => i);
                window.Symbol && window.Symbol.for && (window.Symbol.for('csp_ nonce') || true);
            } catch(e) {}
            
            // Performance API
            if (window.performance && window.performance.timing) {
                Object.defineProperty(performance.timing, 'navigationStart', { get: () => 1 });
            }
        }""")
        
        # Apply high-fidelity stealth using dedicated library
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            pass

        
        # RAM Optimization: Block heavy resources + tracking (saves ~40% memory)
        # Disable with BLOCK_RESOURCES=false for debugging
        block_resources = os.environ.get("BLOCK_RESOURCES", "false").lower() == "true"

        if block_resources:
            # Block: images, media(videos), fonts, stylesheets (CSS)
            blocked_types = {"image", "media", "font", "stylesheet", "websocket"}
            
            # Block tracking domains
            tracking_domains = [
                "*google-analytics.com",
                "*googletagmanager.com",
                "*facebook.net",
                "*hotjar.com",
                "*analytics.com",
                "*doubleclick.net",
                "*criteo.com",
                "*newrelic.com",
                "*mixpanel.com",
                "*segment.io",
                "*bing.com/bat.js",
                "*linkedin.com/px/",
            ]
            
            async def block_heavy_resources(route):
                resource_type = route.request.resource_type
                url = route.request.url

                # Naukri login can fail if CSS/media are blocked.
                # Allow full asset loading for Naukri domains.
                if "naukri.com" in (url or "").lower():
                    await route.continue_()
                    return
                
                # Block by type
                if resource_type in blocked_types:
                    await route.abort()
                    return
                
                # Block tracking scripts
                for domain in tracking_domains:
                    if domain.replace("*", "") in url:
                        await route.abort()
                        return
                
                await route.continue_()
            
            await page.route("**/*", block_heavy_resources)
        
        return page
    
    async def return_page(self, page: Page):
        """Return a page by closing only the page and keeping the context warm."""
        if not page:
            return
        try:
            if not page.is_closed():
                await page.close()
        except Exception:
            pass

    async def save_state(self, settings: Any, student_id: str = None):
        """Persists the session state for a student."""
        context_key = student_id or "_default"
        context = self._contexts.get(context_key)
        
        if context:
            try:
                storage_path = getattr(settings, "session_state_file", None)
                if storage_path:
                    if student_id:
                        storage_path = storage_path.replace(".json", f"_{student_id}.json")
                    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(storage_path))
            except Exception:
                pass

    async def close_context(self, student_id: str = None):
        """Closes the context while keeping the browser alive."""
        context_key = student_id or "_default"
        context = self._contexts.pop(context_key, None)
        
        if context:
            try:
                await context.close()
            except Exception:
                pass

    async def close_student_context(self, student_id: str):
        """Close and cleanup a specific student's context."""
        if not student_id:
            return
        
        context = self._contexts.pop(student_id, None)
        if context:
            try:
                await context.close()
            except Exception:
                pass
        
        default_ctx = self._contexts.get("_default")
        if default_ctx and self._current_student_id == student_id:
            self._current_student_id = None

    async def shutdown(self):
        """Total cleanup of Playwright resources."""
        for page in self._page_pool:
            try:
                await page.close()
            except Exception:
                pass
        self._page_pool = []

        for context in self._contexts.values():
            try:
                await context.close()
            except Exception:
                pass
        self._contexts = {}

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._p:
            try:
                await self._p.stop()
            except Exception:
                pass
            self._p = None

    async def _force_kill_chrome(self):
        """Forcibly clears orphaned Chrome processes to release profile locks."""
        import subprocess
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
            await asyncio.sleep(2)
        except:
            pass

    async def recycle_engine(self, settings: Any, student_id: str = None):
        """Flushes the browser system to prevent pipe exhaustion."""
        from utils.logger import get_logger
        log_file = getattr(settings, "run_log_file", "pipeline.log")
        tmp_log = get_logger(log_file)
        
        tmp_log.log_info(f"[INFRA-ARMOR] Recycling browser for student {student_id}...")
        
        self._page_pool = []
        
        await self.save_state(settings, student_id)
        await self.close_student_context(student_id)
        
        try:
            if self._p:
                await self._p.stop()
        except:
            pass
        self._p = None
        self._browser = None
        
        await asyncio.sleep(2)
        
        try:
            import subprocess
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
        except:
            pass
        
        await asyncio.sleep(1)
        
        try:
            self._p = await async_playwright().start()
        except Exception as e:
            tmp_log.log_warn(f"[RECOVERY] Failed to start playwright: {e}")
            raise
        
        self._contexts = {}
        
        context = await self.get_context(settings, student_id)
        tmp_log.log_info(f"[INFRA-ARMOR] Browser recycled successfully")
        return context

    def get_current_student(self) -> Optional[str]:
        """Get the currently active student ID."""
        return self._current_student_id
    
    def has_student_context(self, student_id: str) -> bool:
        """Check if a student has an active context."""
        return student_id in self._contexts

    # ── CDP (Chrome DevTools Protocol) support ──────────────────────────
    # Connect to an already-running Chrome launched with:
    #   chrome.exe --remote-debugging-port=9222
    # This uses the real Chrome profile so LinkedIn sees a genuine browser.

    async def get_page_via_cdp(self, settings: Any = None, cdp_url: str = None) -> Page:
        """
        Connect to an existing Chrome via CDP and return a Page.
        
        Priority order for CDP URL:
        1. http://chrome-cdp:9222 (Docker browserless container - PRIMARY)
        2. http://host.docker.internal:9222 (fallback for host Chrome)
        3. http://localhost:9222 (local fallback)
        
        No manual Chrome needed when using browserless Docker container!
        """
        # Auto-detect CDP URL if not provided
        if not cdp_url:
            cdp_url = os.environ.get("CDP_URL")
            
        # Runtime Patch: If url points to 9222, fix it to 3000
        if cdp_url and ":9222" in cdp_url and "chrome-cdp" in cdp_url:
            cdp_url = cdp_url.replace(":9222", ":3000")
        
        if not cdp_url:
            # Priority order for CDP connections
            cdp_options = [
                "http://chrome-cdp:3000",      # Docker browserless container (PRIMARY)
                "http://host.docker.internal:9222",  # Host Chrome fallback
                "http://localhost:9222",       # Local fallback
            ]
            
            # Try each option until one works
            for option in cdp_options:
                try:
                    import socket
                    host = option.replace("http://", "").split(":")[0]
                    port = int(option.replace("http://", "").split(":")[1])
                    socket.setdefaulttimeout(3)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((host, port))
                    sock.close()
                    cdp_url = option
                    print(f"  [CDP] Connected to: {option}")
                    break
                except Exception:
                    continue
            
            # Fallback to primary if none connect
            if not cdp_url:
                cdp_url = "http://chrome-cdp:3000"
        self._reset_if_loop_changed()
        
        if not self._p:
            self._p = await async_playwright().start()

        try:
            browser = await self._p.chromium.connect_over_cdp(cdp_url)
            self._browser = browser

            # Enhanced stealth headers to bypass bot detection
            ctx = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "Referer": "https://www.google.com/",
                    # Enhanced sec-ch-ua headers (more complete)
                    "sec-ch-ua": '"Not_A Brand";v="24", "Chromium";v="120", "Google Chrome";v="120", "Microsoft Edge";v="120", "Opera";v="106"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-ch-ua-platform-version": '"10.0.19041.1"',
                    "sec-ch-ua-arch": '"x86"',
                    "sec-ch-ua-bitness": '"64"',
                    "sec-ch-ua-full-version": '"120.0.6099.71"',
                    "sec-ch-ua-full-version-list": '"Not_A Brand";v="24.0.0.0","Chromium";v="120.0.6099.71","Google Chrome";v="120.0.6099.71","Microsoft Edge";v="120.0.6099.71","Opera";v="106.0.0.0"',
                    "sec-ch-ua-model": '""',
                    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                    "Origin-Agent-Cluster": "?0",
                    "Pragma": "akamai-x-cache-on, akamai-x-cache-remote-on",
                    "X-Akamak-Origin": "origin",
                },
            )
            page = await ctx.new_page()
            page.set_default_timeout(20000)
            page.set_default_navigation_timeout(30000)
            await self._apply_stealth(page)
            return page

        except Exception as e:
            raise ConnectionError(
                f"CDP connection failed ({cdp_url}): {e}. "
                "Start Chrome with: chrome.exe --remote-debugging-port=9222"
            )

    async def get_page_with_cdp_fallback(
        self, settings: Any, student_id: str = None, cdp_url: str = None
    ) -> tuple[Page, str]:
        """
        Try CDP first (browserless Docker container), fall back to managed Playwright browser.
        Returns (page, method) where method is 'cdp' or 'playwright'.
        
        Priority: Docker browserless Chrome > Host Chrome > Playwright
        """
        use_cdp = os.environ.get("USE_CDP", "true").lower() == "true"
        
# Attempt 1: CDP (browserless Docker container)
        if use_cdp:
            try:
                page = await self.get_page_via_cdp(settings, cdp_url)
                content = await page.content()
                content_len = len(content)
                
                # If content is too short, CDP was blocked - need Selenium fallback
                if content_len < 10000:
                    print(f"  [CDP] Blocked by platform (content={content_len} bytes), trying regular Playwright...")
                    await page.close()
                    raise ConnectionError(f"CDP blocked: only {content_len} bytes")
                
                print(f"  [CDP] Using browserless Chrome container (content={content_len} bytes)")
                return page, "cdp"
            except Exception as e:
                print(f"  [CDP] Failed, falling back to regular Playwright: {e}")
        
        # Attempt 2: Regular Playwright (fallback)
        page = await self.get_page(settings, student_id)
        print(f"  [Playwright] Using regular browser fallback")
        return page, "playwright"


playwright_manager = PlaywrightManager()
