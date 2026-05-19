"""
Notification Service - Job Automation System
============================================
Sends real-time notifications to admin dashboard via Socket.io.
"""

from __future__ import annotations
import os
import requests
from typing import Any, Optional
from datetime import datetime


class NotificationService:
    """
    Service to send notifications to the admin dashboard.
    Uses REST API to notify the server which then emits via Socket.io.
    """
    
    def __init__(self, api_url: Optional[str] = None):
        default_url = "http://node-api:5000" if os.getenv("IN_DOCKER", "").lower() == "true" else "http://localhost:5000"
        self.api_url = (api_url or os.getenv("API_URL", default_url)).rstrip("/")
    
    def notify_application(
        self,
        student_id: str,
        platform: str,
        job_title: str,
        company: str,
        status: str,
        resume_variant: Optional[str] = None,
        resume_url: Optional[str] = None,
        job_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Notify dashboard of application status.
        
        Args:
            student_id: Student ID
            platform: Platform (naukri, linkedin)
            job_title: Job title
            company: Company name
            status: 'applied' or 'failed'
            error: Error message if failed
            
        Returns:
            True if notification sent successfully
        """
        try:
            # Get student info
            from database import get_student
            student = get_student(student_id)
            
            normalized_status = "applied" if status == "applied" else "failed"
            student_name = student.name if student else student_id
            student_email = student.email if student else ""
            profile_resume_url = ""
            if student and getattr(student, "resume_urls", None) and resume_variant:
                profile_resume_url = getattr(student.resume_urls, resume_variant, "") or ""

            payload = {
                "studentId": student_id,
                "studentName": student_name,
                "candidateName": student_name,
                "candidateEmail": student_email,
                "jobTitle": job_title or "N/A",
                "company": company or "N/A",
                "platform": platform,
                "status": normalized_status,
                "rawStatus": status,
                "role": job_title or "N/A",
                "resumeVariant": resume_variant or "",
                "resumeUrl": resume_url or profile_resume_url,
                "jobUrl": job_url or "",
                "appliedAt": datetime.utcnow().isoformat(),
                "error": error,
            }
            
            # Send to API
            try:
                response = requests.post(
                    f"{self.api_url}/api/notify-application",
                    json=payload,
                    timeout=5,
                )
                if response.status_code == 200:
                    print(f"[NOTIFY] {normalized_status}: {job_title} at {company} ({student_name})")
                    return True
                else:
                    print(f"[NOTIFY ERROR] HTTP {response.status_code}: {response.text[:100]}")
                    return False
            except requests.exceptions.RequestException as e:
                print(f"[NOTIFY ERROR] Request failed: {e}")
                return False
            
        except Exception as e:
            print(f"Notification error: {e}")
            return False


def notify_admin_alert(
    title: str,
    message: str,
    severity: str = "warning",
    platform: str = None,
) -> bool:
    """
    Send admin alert (challenge detected, rate limit, etc.)
    """
    try:
        payload = {
            "type": "admin_alert",
            "title": title,
            "message": message,
            "severity": severity,
            "platform": platform,
            "timestamp": datetime.utcnow().isoformat(),
        }
        response = requests.post(
            f"{NotificationService().api_url}/api/notify-application",
            json=payload,
            timeout=5,
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Admin alert error: {e}")
        return False


notification_service = NotificationService()


# Convenience function
def notify_application(
    student_id: str,
    platform: str,
    job_title: str,
    company: str,
    status: str,
    resume_variant: Optional[str] = None,
    resume_url: Optional[str] = None,
    job_url: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """Send application notification to dashboard."""
    return notification_service.notify_application(
        student_id=student_id,
        platform=platform,
        job_title=job_title,
        company=company,
        status=status,
        resume_variant=resume_variant,
        resume_url=resume_url,
        job_url=job_url,
        error=error,
    )
