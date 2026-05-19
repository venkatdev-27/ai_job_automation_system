"""
Session Manager - Job Automation System
=======================================
Manages session persistence across platforms (LinkedIn, Naukri, Foundit).
Provides session restore, save, and validation functionality.

Usage:
    session_manager = SessionManager(student_id, platform)
    is_valid = await session_manager.restore_session(page)
    await session_manager.save_session(page)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger("session_manager")


class SessionManager:
    """Manages session persistence for student profiles across platforms."""
    
    # Profile base directory - configurable via environment
    # In Docker, use /app/chrome_profile
    PROFILE_BASE_DIR = Path(os.getenv(
        "CHROME_PROFILE_DIR", 
        "/app/chrome_profile" if os.getenv("IN_DOCKER") else "D:/ai-bot-resumes/job_automation_system/chrome_profile"
    ))
    
    # Platform name mapping
    PLATFORM_MAP = {
        "linkedin": "linkedin",
        "naukri": "naukri", 
        "foundit": "foundit",
        "foundit.in": "foundit",
    }
    
    def __init__(self, student_id: str, platform: str):
        """
        Initialize session manager for a student and platform.
        
        Args:
            student_id: Unique student identifier (e.g., 'student_2b4359c4')
            platform: Platform name ('linkedin', 'naukri', 'foundit')
        """
        self.student_id = student_id
        self.platform = self.PLATFORM_MAP.get(platform.lower(), platform.lower())
        self.profile_path = self.PROFILE_BASE_DIR / student_id / self.platform
        self.cookies_file = self.profile_path / "cookies.json"
        self.session_file = self.profile_path / "session.json"
        
        # Create profile directory if not exists
        self.profile_path.mkdir(parents=True, exist_ok=True)
    
    async def restore_session(self, page) -> bool:
        """
        Try to restore existing session from profile.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if session restored successfully, False otherwise
        """
        try:
            # Check if profile exists
            if not self.profile_path.exists():
                logger.info(f"[SESSION] No profile directory for {self.student_id}/{self.platform}")
                return False
            
            # Try to load cookies
            if self.cookies_file.exists():
                try:
                    with open(self.cookies_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                    
                    if cookies and len(cookies) > 0:
                        # Add cookies to page context
                        await page.context.add_cookies(cookies)
                        logger.info(f"[SESSION] Loaded {len(cookies)} cookies for {self.student_id}/{self.platform}")
                        
                        # Restore localStorage if available
                        local_storage_file = self.profile_path / "local_storage.json"
                        if local_storage_file.exists():
                            try:
                                with open(local_storage_file, 'r') as f:
                                    local_storage = json.load(f)
                                if local_storage:
                                    await page.evaluate(f"""(items) => {{
                                        for (let key in items) {{
                                            try {{ localStorage.setItem(key, items[key]); }}
                                            catch(e) {{}}
                                        }}
                                    }}""", local_storage)
                                    logger.info(f"[SESSION] Restored {len(local_storage)} localStorage items")
                            except Exception as e:
                                logger.warn(f"[SESSION] Failed to restore localStorage: {e}")
                        
                        # Try to verify session is still valid
                        if await self._verify_session(page):
                            logger.info(f"[SESSION] Session restored successfully for {self.student_id}/{self.platform}")
                            return True
                        else:
                            logger.info(f"[SESSION] Cookies loaded but session expired for {self.student_id}/{self.platform}")
                            # Continue to try login
                except Exception as e:
                    logger.warn(f"[SESSION] Failed to load cookies: {e}")
            
            # Try to load session storage
            if self.session_file.exists():
                logger.info(f"[SESSION] Found session file but cookies failed - will re-login")
            
            return False
            
        except Exception as e:
            logger.warn(f"[SESSION] Session restore failed: {e}")
            return False
    
    async def save_session(self, page) -> bool:
        """
        Save session after successful login.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if session saved successfully
        """
        try:
            # Ensure profile directory exists
            self.profile_path.mkdir(parents=True, exist_ok=True)
            
            # Save cookies
            cookies = await page.context.cookies()
            if cookies:
                with open(self.cookies_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, indent=2)
                logger.info(f"[SESSION] Saved {len(cookies)} cookies for {self.student_id}/{self.platform}")
            
            # Save localStorage for better session restoration
            try:
                local_storage = await page.evaluate("""() => {
                    let items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        let key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }""")
                if local_storage:
                    local_storage_file = self.profile_path / "local_storage.json"
                    with open(local_storage_file, 'w', encoding='utf-8') as f:
                        json.dump(local_storage, f, indent=2)
                    logger.info(f"[SESSION] Saved {len(local_storage)} localStorage items")
            except Exception as e:
                logger.warn(f"[SESSION] Failed to save localStorage: {e}")
            
            # Save session metadata with timestamp
            import time
            session_data = {
                "student_id": self.student_id,
                "platform": self.platform,
                "saved_at": time.time(),
                "cookie_count": len(cookies) if cookies else 0,
            }
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"[SESSION] Session saved successfully for {self.student_id}/{self.platform}")
            return True
            
        except Exception as e:
            logger.error(f"[SESSION] Failed to save session: {e}")
            return False
    
    async def _verify_session(self, page) -> bool:
        """
        Verify if session is still valid by checking platform-specific elements.
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if session appears valid
        """
        try:
            if self.platform == "linkedin":
                # Try accessing LinkedIn home - if redirects to login, session invalid
                await page.goto("https://www.linkedin.com/feed", timeout=10000, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                current_url = page.url.lower()
                # If still on feed or home, session is valid
                if "login" not in current_url and "feed" in current_url:
                    return True
                # Try another check - check for logged-in elements
                await page.goto("https://www.linkedin.com", timeout=10000)
                if "login" not in page.url.lower():
                    return True
                    
            elif self.platform == "naukri":
                # Try accessing Naukri homepage
                await page.goto("https://www.naukri.com/mnjuser/homepage", timeout=10000, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                if "nlogin" not in page.url.lower():
                    return True
                    
            elif self.platform == "foundit":
                # Try accessing Foundit homepage
                await page.goto("https://www.foundit.in/", timeout=10000, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                if "login" not in page.url.lower():
                    return True
            
            return False
            
        except Exception as e:
            logger.warn(f"[SESSION] Session verification failed: {e}")
            return False
    
    async def validate_session(self, page) -> bool:
        """
        Check if existing session is still valid (without restoring).
        
        Args:
            page: Playwright Page object
            
        Returns:
            bool: True if session exists and is valid
        """
        if not self.cookies_file.exists():
            return False
        
        # Check session age - don't use sessions older than 7 days
        try:
            import time
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                saved_at = session_data.get('saved_at', 0)
                age_hours = (time.time() - saved_at) / 3600
                if age_hours > 168:  # 7 days
                    logger.info(f"[SESSION] Session too old ({age_hours:.1f}h), need fresh login")
                    return False
                logger.info(f"[SESSION] Session age: {age_hours:.1f}h")
        except Exception as e:
            logger.warn(f"[SESSION] Could not check session age: {e}")
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            if not cookies:
                return False
            
            # Add cookies and verify
            await page.context.add_cookies(cookies)
            return await self._verify_session(page)
            
        except Exception as e:
            logger.warn(f"[SESSION] Session validation failed: {e}")
            return False
    
    async def clear_session(self) -> bool:
        """
        Clear saved session for this student/platform.
        
        Returns:
            bool: True if session cleared successfully
        """
        try:
            if self.cookies_file.exists():
                self.cookies_file.unlink()
            if self.session_file.exists():
                self.session_file.unlink()
            # Also clear localStorage
            local_storage_file = self.profile_path / "local_storage.json"
            if local_storage_file.exists():
                local_storage_file.unlink()
            logger.info(f"[SESSION] Session cleared for {self.student_id}/{self.platform}")
            return True
        except Exception as e:
            logger.error(f"[SESSION] Failed to clear session: {e}")
            return False
    
    def get_profile_path(self) -> Path:
        """Get the profile directory path for this student/platform."""
        return self.profile_path


async def restore_and_login(
    page, 
    student_id: str, 
    platform: str, 
    login_func,
    *login_args,
    **login_kwargs
) -> bool:
    """
    Convenience function: Try restore session first, if fails then login, then save.
    
    Args:
        page: Playwright Page object
        student_id: Student identifier
        platform: Platform name
        login_func: Async function to perform login
        *login_args, **login_kwargs: Arguments to pass to login_func
        
    Returns:
        bool: True if login successful (via restore or fresh login)
    """
    session_mgr = SessionManager(student_id, platform)
    
    # Step 1: Try restore existing session
    session_restored = await session_mgr.restore_session(page)
    if session_restored:
        logger.info(f"[SESSION] Using existing session for {student_id}/{platform}")
        return True
    
    # Step 2: No valid session - perform fresh login
    logger.info(f"[SESSION] No valid session, performing fresh login for {student_id}/{platform}")
    login_success = await login_func(page, *login_args, **login_kwargs)
    
    # Step 3: Save session after successful login
    if login_success:
        await session_mgr.save_session(page)
    
    return login_success