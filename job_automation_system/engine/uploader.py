from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Optional, Union

from utils.humanize import random_delay
from utils.resume_downloader import download_resume_from_url

# Default directory for temporary resumes if not defined in resume_downloader
TEMP_RESUMES_DIR = Path("temp_resumes")

class ResumeUploader:
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    async def upload_resume(
        self, 
        page: Any, 
        resume_source: Union[str, Path],
        student_id: str = None,
        role: str = "master"
    ) -> bool:
        """
        Upload resume to job platform.
        """
        # Determine what type of input we have
        resume_path = None
        
        if isinstance(resume_source, (str, Path)):
            source_str = str(resume_source)
            
            # Case 1: Cloudinary URL
            if source_str.startswith('http'):
                if not student_id:
                    self.logger.warning("Student ID required for URL download")
                    return False
                
                # Download from Cloudinary
                self.logger.log_info(f"Downloading resume from Cloudinary URL...")
                path, success = download_resume_from_url(
                    source_str, 
                    student_id,
                    role
                )
                
                if success:
                    resume_path = Path(path)
                    self.logger.log_ok(f"Resume downloaded: {path}")
                else:
                    self.logger.warning("Failed to download resume from URL")
                    return False
            
            # Case 2: Local file path
            elif os.path.exists(source_str):
                resume_path = Path(source_str)
            
            # Case 3: Not a URL and doesn't exist
            else:
                self.logger.warning(f"Resume file not found: {source_str}")
                return False
        
        # Now upload the local file
        if not resume_path or not resume_path.exists():
            self.logger.warning("No valid resume path to upload")
            return False

        selectors = [
            "input[type='file']",
            ".jobs-document-upload__upload-button input[type='file']",
            "input[name*='resume' i]",
            "input[id*='resume' i]",
            "input[name*='cv' i]",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() == 0:
                    continue
                target = locator.first
                # v3 Force Reveal Strike: Ensure hidden inputs are receptive to file drops
                await target.evaluate(
                    "el => { el.style.display='block'; el.style.visibility='visible'; el.style.opacity='1'; el.removeAttribute('hidden'); }"
                )
                await target.set_input_files(str(resume_path))
                await random_delay(1000, 1500)
                self.logger.log_ok(f"NEW Resume uploaded via direct input: {selector}")
                return True
            except Exception:
                continue

        # Try file chooser flow by clicking common upload buttons
        button_selectors = [
            ".jobs-document-upload__upload-button",
            "label[for='jobs-document-upload-file-input']",
            "button:has-text('Upload resume')",
            "span:has-text('Upload resume')",
            "button[aria-label*='Upload resume']",
            "[data-testid='jobs-document-upload__upload-button']",
        ]
        for selector in button_selectors:
            try:
                button = page.locator(selector).first
                if await button.count() == 0:
                    continue
                
                self.logger.log_info(f"Attempting file chooser strike on: {selector}")
                async with page.expect_file_chooser(timeout=7000) as chooser_info:
                    await button.click(force=True)
                chooser = await chooser_info.value
                await chooser.set_files(str(resume_path))
                await random_delay(260, 620)
                self.logger.info("Resume uploaded via file chooser button: %s", selector)
                return True
            except Exception:
                continue

        self.logger.warning("No resume upload field detected on page.")
        return False


class FounditResumeUploader:
    """
    Foundit-specific resume uploader.
    """
    
    PROFILE_URL = "https://www.foundit.in/seeker/profile"
    FILE_INPUT_SELECTOR = "input[type='file'][name='resume']"
    REPLACE_BUTTON_SELECTOR = "button:has-text('Replace resume')"
    
    def __init__(self, logger: Any) -> None:
        self.logger = logger
        
    async def upload_resume(self, page: Any, resume_path: str) -> dict[str, Any]:
        """Upload resume to Foundit profile."""
        try:
            abs_path = os.path.abspath(resume_path)
            if not os.path.exists(abs_path):
                return {"status": "error", "message": f"File not found: {resume_path}"}
            
            # Navigate to profile
            await page.goto(self.PROFILE_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Try direct file input first
            file_input = page.locator(self.FILE_INPUT_SELECTOR)
            if await file_input.count() > 0:
                await file_input.set_input_files(abs_path)
                await asyncio.sleep(3)
                return {"status": "success", "message": "Uploaded via hidden input"}
            
            # Try clicking Replace resume button
            replace_btn = page.locator(self.REPLACE_BUTTON_SELECTOR)
            if await replace_btn.count() > 0:
                await replace_btn.click()
                await asyncio.sleep(1)
                file_input = page.locator(self.FILE_INPUT_SELECTOR)
                if await file_input.count() > 0:
                    await file_input.set_input_files(abs_path)
                    await asyncio.sleep(3)
                    return {"status": "success", "message": "Uploaded after button click"}
            
            return {"status": "error", "message": "No file input found"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
