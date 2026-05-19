import logging
import asyncio
import os
from pathlib import Path
from ai_engine.config import RESUME_OUTPUT_DIR
from playwright.async_api import async_playwright

logger = logging.getLogger("ai_engine.pdf_generator")


class PDFService:
    _instance = None
    _playwright = None
    _browser = None
    _browser_lock = None
    _launch_count = 0
    _request_count = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_lock(self):
        if self._browser_lock is None:
            self._browser_lock = asyncio.Lock()
        return self._browser_lock

    async def _close_browser(self):
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:
                logger.warning(f"Failed to close PDF browser cleanly: {exc}")
            finally:
                self._browser = None

    async def aclose(self):
        await self._close_browser()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as exc:
                logger.warning(f"Failed to stop Playwright cleanly: {exc}")
            finally:
                self._playwright = None

    async def health_check(self) -> bool:
        try:
            browser = await self._get_browser()
            return bool(browser and browser.is_connected())
        except Exception as exc:
            logger.warning(f"PDF browser health check failed: {exc}")
            return False

    async def _get_browser(self, force_restart: bool = False):
        max_requests = max(1, int(os.getenv("PDF_MAX_REQUESTS_PER_BROWSER", "100")))
        needs_restart = (
            force_restart
            or self._browser is None
            or not self._browser.is_connected()
            or self._request_count >= max_requests
        )
        if not needs_restart:
            return self._browser

        async with self._get_lock():
            needs_restart = (
                force_restart
                or self._browser is None
                or not self._browser.is_connected()
                or self._request_count >= max_requests
            )
            if not needs_restart:
                return self._browser

            await self._close_browser()
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-setuid-sandbox",
                    ],
                )
                self._launch_count += 1
                self._request_count = 0
            except Exception:
                await self.aclose()
                logger.exception("Failed to launch PDF browser")
                raise
        return self._browser

    async def generate_pdf(self, html_content: str, output_path: Path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        last_error = None

        for attempt in range(2):
            page = None
            try:
                browser = await self._get_browser(force_restart=attempt > 0)
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle", timeout=30000)
                await page.pdf(
                    path=str(output_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"},
                )
                if not output_path.exists():
                    raise RuntimeError(f"PDF output missing: {output_path}")
                size = output_path.stat().st_size
                if size < 1000:
                    try:
                        output_path.unlink()
                    except OSError:
                        pass
                    raise RuntimeError(f"PDF output too small: {size} bytes")
                self._request_count += 1
                return
            except Exception as exc:
                last_error = exc
                logger.warning(f"PDF generation attempt {attempt + 1} failed: {exc}")
                await self._close_browser()
                if attempt == 0:
                    await asyncio.sleep(0.5)
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass

        raise RuntimeError(f"PDF generation failed after browser restart: {last_error}")


pdf_service = PDFService()

async def generate_pdf(html_content: str, output_filename: str) -> str:
    """
    Converts HTML string to PDF using the centralized PDFService.
    """
    output_path = RESUME_OUTPUT_DIR / output_filename
    
    try:
        print(f"    [PDF] Requesting PDF generation for {output_filename}...")
        await pdf_service.generate_pdf(html_content, output_path)
        print(f"    [PDF] OK: Generated {output_filename}")
        logger.info(f"PDF generated successfully at {output_path}")
        return str(output_path)
    except Exception as e:
        print(f"    [PDF] ERROR: {str(e)}")
        logger.error(f"PDF generation failed: {str(e)}")
        return ""

def generate_pdf_sync(html_content: str, output_filename: str) -> str:
    """
    Synchronous wrapper for generate_pdf.
    """
    async def _generate_once():
        try:
            return await generate_pdf(html_content, output_filename)
        finally:
            await pdf_service.aclose()

    return asyncio.run(_generate_once())
