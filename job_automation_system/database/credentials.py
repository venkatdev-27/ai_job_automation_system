"""
Credentials Module - Job Automation System
===========================================
Manages student credentials from MongoDB with encryption.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from database.student_repo import student_repository
from utils.crypto import CredentialEncryptor


if TYPE_CHECKING:
    from database.models import Student, PlatformCredentials


class RuntimeSettings:
    """Runtime settings with credentials injected from MongoDB."""
    
    def __init__(self, base_settings, student_credentials: Optional[dict] = None):
        self._base = base_settings
        self._creds = student_credentials or {}
        
        for key in dir(base_settings):
            if not key.startswith('_'):
                try:
                    value = getattr(base_settings, key)
                    setattr(self, key, value)
                except Exception:
                    pass
        
        # Expose resolved credential aliases as direct attributes.
        self.naukri_email = self.get("naukri_email", getattr(base_settings, "naukri_email", ""))
        self.naukri_username = self.get("naukri_username", getattr(base_settings, "naukri_username", ""))
        self.naukri_password = self.get("naukri_password", getattr(base_settings, "naukri_password", ""))
        self.linkedin_email = self.get("linkedin_email", getattr(base_settings, "linkedin_email", ""))
        self.linkedin_username = self.get("linkedin_username", getattr(base_settings, "linkedin_username", ""))
        self.linkedin_password = self.get("linkedin_password", getattr(base_settings, "linkedin_password", ""))
        self.foundit_email = self.get("foundit_email", getattr(base_settings, "foundit_email", ""))
        self.foundit_username = self.get("foundit_username", getattr(base_settings, "foundit_username", ""))
        self.foundit_password = self.get("foundit_password", getattr(base_settings, "foundit_password", ""))
    
    def get(self, key: str, default=None):
        """Get credential from student credentials or fall back to base."""
        cred_map = {
            'naukri_email': ('naukri', 'email_or_username'),
            'naukri_username': ('naukri', 'username_or_email'),
            'naukri_password': ('naukri', 'password'),
            'linkedin_username': ('linkedin', 'username_or_email'),
            'linkedin_email': ('linkedin', 'email_or_username'),
            'linkedin_password': ('linkedin', 'password'),
            'foundit_username': ('foundit', 'username_or_email'),
            'foundit_email': ('foundit', 'email_or_username'),
            'foundit_password': ('foundit', 'password'),
        }
        
        if key in cred_map:
            platform, field = cred_map[key]
            platform_creds = self._creds.get(platform, {})
            if field == "email_or_username":
                value = platform_creds.get("email") or platform_creds.get("username")
                if value:
                    return value
            elif field == "username_or_email":
                value = platform_creds.get("username") or platform_creds.get("email")
                if value:
                    return value
            elif field in platform_creds:
                return platform_creds[field]
        
        return getattr(self._base, key, default)


def build_dynamic_runtime_settings(base_settings, profile, student_id: str = None) -> RuntimeSettings:
    """
    Build runtime settings with per-student credentials from MongoDB.
    
    Args:
        base_settings: Base configuration settings
        profile: Student profile object
        student_id: Optional student ID (extracted from profile if not provided)
    
    Returns:
        RuntimeSettings with credentials injected
    """
    if not student_id and hasattr(profile, 'student_id'):
        student_id = profile.student_id
    
    credentials = None
    
    if student_id:
        student = student_repository.get_by_id(student_id)
        if student and student.credentials:
            credentials = _extract_encrypted_credentials(student, student_id)
    
    return RuntimeSettings(base_settings, credentials)


def _extract_encrypted_credentials(student: 'Student', student_id: str = None) -> dict:
    """Extract and decrypt credentials from student document."""
    result = {}
    
    if not student.credentials:
        return result
    
    creds = student.credentials
    
    for platform in ['naukri', 'linkedin', 'foundit']:
        platform_cred = getattr(creds, platform, None)
        if not platform_cred:
            continue

        raw_email = (getattr(platform_cred, "email", "") or "").strip()
        raw_username = (getattr(platform_cred, "username", "") or "").strip()
        raw_password = getattr(platform_cred, "password", None)

        if not raw_password:
            continue
        if not (raw_email or raw_username):
            continue

        def _maybe_decrypt(value: str, student_id: str) -> str:
            if not value:
                return value
            try:
                if CredentialEncryptor.is_encrypted(value):
                    return CredentialEncryptor.decrypt(value, student_id=student_id)
            except Exception:
                pass
            return value

        email = _maybe_decrypt(raw_email, student_id)
        username = _maybe_decrypt(raw_username, student_id)
        password = _maybe_decrypt(raw_password, student_id)

        if not email and username:
            email = username
        if not username and email:
            username = email

        result[platform] = {
            "email": email,
            "username": username,
            "password": password,
        }
    
    return result


def get_student_credentials(student_id: str) -> Optional[dict]:
    """Get decrypted credentials for a student."""
    student = student_repository.get_by_id(student_id)
    if not student or not student.credentials:
        return None
    return _extract_encrypted_credentials(student, student_id)


def set_student_credentials(
    student_id: str,
    naukri: Optional[tuple] = None,
    linkedin: Optional[tuple] = None,
    foundit: Optional[tuple] = None,
    encrypt: bool = True
) -> bool:
    """
    Set credentials for a student.
    
    Args:
        student_id: Student ID
        naukri: (email, password) tuple
        linkedin: (email, password) tuple
        foundit: (email, password) tuple
        encrypt: Whether to encrypt credentials
    
    Returns:
        True if successful
    """
    from database.models import StudentCredentials, PlatformCredentials
    from database.student_repo import student_repository
    
    student = student_repository.get_by_id(student_id)
    if not student:
        return False
    
    credentials = StudentCredentials()
    
    if naukri:
        email, password = naukri
        if encrypt:
            email = CredentialEncryptor.encrypt(email, student_id)
            password = CredentialEncryptor.encrypt(password, student_id)
        credentials.naukri = PlatformCredentials(email=email, password=password)
    
    if linkedin:
        email, password = linkedin
        if encrypt:
            email = CredentialEncryptor.encrypt(email, student_id)
            password = CredentialEncryptor.encrypt(password, student_id)
        credentials.linkedin = PlatformCredentials(email=email, password=password)
    
    if foundit:
        email, password = foundit
        if encrypt:
            email = CredentialEncryptor.encrypt(email, student_id)
            password = CredentialEncryptor.encrypt(password, student_id)
        credentials.foundit = PlatformCredentials(email=email, password=password)
    
    from database.models import StudentUpdate
    student_repository.update(student_id, StudentUpdate(credentials=credentials))
    return True


def rotate_credentials(student_id: str, platform: str, email: str, password: str) -> bool:
    """Rotate credentials for a specific platform."""
    mapping = {
        'naukri': ('naukri', None),
        'linkedin': ('linkedin', None),
        'foundit': ('foundit', None),
    }
    
    if platform not in mapping:
        return False
    
    return set_student_credentials(
        student_id,
        **{mapping[platform][0]: (email, password)}
    )
