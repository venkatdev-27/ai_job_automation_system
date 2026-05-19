import os
import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright

logger = logging.getLogger("pipeline.pdf_service")

class PDFService:
    _instance = None
    _playwright = None
    _browser = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PDFService, cls).__new__(cls)
        return cls._instance

    async def _get_browser(self):
        if self._browser is None:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            logger.info("PDFService: Browser launched.")
        return self._browser

    async def generate_pdf(self, html_content: str, output_path: Path):
        """
        Converts HTML to PDF with font injection, timeout handling, and validation.
        """
        output_path = Path(output_path)
        
        # 1. Font Control: Inject Times New Roman
        font_style = """
        <style>
            body { 
                font-family: "Times New Roman", Times, serif !important; 
            }
        </style>
        """
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{font_style}</body>")
        else:
            html_content += font_style

        browser = await self._get_browser()
        page = await browser.new_page()
        
        try:
            # 2. Timeout Handling
            await page.set_content(html_content, wait_until="networkidle", timeout=30000)
            
            # 3. Generate PDF
            await page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "0.5in", "right": "0.5in", "bottom": "0.5in", "left": "0.5in"}
            )
            
            # 4. Validation
            if not output_path.exists():
                raise Exception(f"PDF generation failed: Output file {output_path} missing.")
            
            size = output_path.stat().st_size
            if size < 1000:
                # Cleanup invalid file
                try: output_path.unlink()
                except: pass
                raise Exception(f"PDF generation failed: File size {size} bytes is too small (< 1000).")
            
            logger.info(f"PDFService: Successfully generated {output_path} ({size} bytes)")
        except Exception as e:
            logger.error(f"PDFService: Error generating PDF: {e}")
            raise
        finally:
            await page.close()

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("PDFService: Browser closed.")

# Singleton instance for easy import
pdf_service = PDFService()
