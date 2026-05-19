import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import asyncio
import aiohttp


logger = logging.getLogger(__name__)


class VerificationType(Enum):
    CAPTCHA = "captcha"
    EMAIL_CODE = "email_code"
    PHONE_VERIFY = "phone_verify"
    SUSPENDED = "suspended"
    RATE_LIMITED = "rate_limited"
    UNKNOWN = "unknown"


class VerificationHandler:
    """Handles verification challenges during automation."""
    
    def __init__(self):
        self._notification_sent = set()
    
    async def detect_verification(self, page) -> VerificationType:
        """Detect what type of verification is present."""
        try:
            page_text = (await page.inner_text("body")).lower() if page else ""
            page_url = page.url if page else ""
            
            if "checkpoint" in page_url or "challengesv2" in page_url:
                return VerificationType.CAPTCHA
            
            verification_patterns = {
                "captcha": ["captcha", "verify you're human", "i'm not a robot"],
                "email_code": ["enter the code", "email verification", "check your email"],
                "phone_verify": ["phone number", "sms verification", "text message"],
                "suspended": ["account has been suspended", "locked", "restrict"],
                "rate_limited": ["too many attempts", "try again later", "限"],
            }
            
            for vtype, patterns in verification_patterns.items():
                for pattern in patterns:
                    if pattern in page_text:
                        return VerificationType(vtype)
            
            return VerificationType.UNKNOWN
        except Exception:
            return VerificationType.UNKNOWN
    
    async def handle_verification(
        self,
        page,
        student_id: str,
        platform: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Handle verification challenge with pause and notification."""
        vtype = await self.detect_verification(page)
        
        try:
            page_url = page.url if page else "unknown"
        except Exception:
            page_url = "unknown"
        
        result = {
            "detected": True,
            "type": vtype.value,
            "page_url": page_url,
            "student_id": student_id,
            "platform": platform,
            "timestamp": datetime.utcnow().isoformat(),
            "action_taken": None,
        }
        
        if vtype == VerificationType.CAPTCHA:
            result["action_taken"] = "retry_fresh_profile"
            result["message"] = "CAPTCHA detected - will retry with fresh profile"
        
        elif vtype == VerificationType.EMAIL_CODE:
            result["action_taken"] = "notify_admin"
            result["message"] = "Email code required - notify admin"
        
        elif vtype == VerificationType.PHONE_VERIFY:
            result["action_taken"] = "notify_admin"
            result["message"] = "Phone verification required - notify admin"
        
        elif vtype == VerificationType.SUSPENDED:
            result["action_taken"] = "pause_student"
            result["message"] = "Account suspended - pause student"
        
        elif vtype == VerificationType.RATE_LIMITED:
            result["action_taken"] = "cooldown"
            result["message"] = "Rate limited - cooldown period"
        
        else:
            result["action_taken"] = "retry"
            result["message"] = "Unknown verification - retry"
        
        await self.notify_student(student_id, vtype, page_url, platform)
        await self.log_verification_event(result)
        
        return result
    
    async def notify_student(
        self,
        student_id: str,
        vtype: VerificationType,
        page_url: str,
        platform: str
    ):
        """Notify student/admin about verification requirement."""
        notif_key = f"{student_id}:{vtype.value}:{int(datetime.utcnow().timestamp() / 3600)}"
        
        if notif_key in self._notification_sent:
            return
        
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            return
        
        message = f"⚠️ Verification Required\nStudent: {student_id}\nPlatform: {platform}\nType: {vtype.value}\nURL: {page_url}\n\nPlease resolve to continue automation."
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    webhook_url,
                    json={"text": message},
                    timeout=aiohttp.ClientTimeout(total=10)
                )
                self._notification_sent.add(notif_key)
        except Exception as e:
            logger.warning(f"Notification failed: {e}")
    
    async def log_verification_event(self, event_data: Dict[str, Any]):
        """Log verification event to file (MongoDB integration point)."""
        try:
            log_file = os.environ.get("VERIFICATION_LOG_FILE", "/app/logs/verification.log")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.warning(f"Failed to log verification event: {e}")
    
    async def wait_for_verification_resolve(
        self,
        page,
        student_id: str,
        timeout: int = 300
    ) -> bool:
        """Wait for manual verification to be resolved."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            vtype = await self.detect_verification(page)
            
            if vtype == VerificationType.UNKNOWN:
                await asyncio.sleep(5)
                vtype = await self.detect_verification(page)
                if vtype == VerificationType.UNKNOWN:
                    return True
            
            await asyncio.sleep(10)
        
        return False


verification_handler = VerificationHandler()