"""
Encryption Utility - Job Automation System
==========================================
Fernet encryption for credentials using cryptography library.
Per-student key derivation with legacy fallback support.
"""

from __future__ import annotations
import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class CredentialEncryptor:
    """Handles encryption/decryption of credentials with per-student key derivation."""

    _master_key: Optional[bytes] = None
    _legacy_instance: Optional[Fernet] = None

    @classmethod
    def _get_master_key(cls) -> bytes:
        """Get or derive master key from ENCRYPTION_KEY env var."""
        if cls._master_key is not None:
            return cls._master_key
        key_str = os.getenv("ENCRYPTION_KEY")
        if key_str:
            cls._master_key = key_str.encode()
        else:
            cls._master_key = os.urandom(32)
        return cls._master_key

    @classmethod
    def _derive_key(cls, password: bytes, salt: bytes) -> bytes:
        """Derive a Fernet key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    @classmethod
    def _get_legacy_instance(cls) -> Fernet:
        """Get the legacy shared-key Fernet instance."""
        if cls._legacy_instance is not None:
            return cls._legacy_instance
        master = cls._get_master_key()
        derived = cls._derive_key(master, salt=b"ai_bot_resumes_salt_v1")
        cls._legacy_instance = Fernet(derived)
        return cls._legacy_instance

    @classmethod
    def _get_student_instance(cls, student_id: str) -> Fernet:
        """Get a per-student Fernet instance."""
        master = cls._get_master_key()
        salt = f"student_{student_id}_v2".encode()
        derived = cls._derive_key(master, salt=salt)
        return Fernet(derived)

    @classmethod
    def encrypt(cls, plaintext: str, student_id: str = None) -> str:
        """Encrypt plaintext with per-student key if student_id provided."""
        if not plaintext:
            return plaintext
        fernet = cls._get_student_instance(student_id) if student_id else cls._get_legacy_instance()
        encrypted = fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    @classmethod
    def decrypt(cls, encrypted: str, student_id: str = None) -> str:
        """Decrypt with per-student key, fall back to legacy key."""
        if not encrypted:
            return encrypted
        if student_id:
            try:
                fernet = cls._get_student_instance(student_id)
                encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
                return fernet.decrypt(encrypted_bytes).decode()
            except Exception:
                return cls._decrypt_legacy(encrypted)
        return cls._decrypt_legacy(encrypted)

    @classmethod
    def _decrypt_legacy(cls, encrypted: str) -> str:
        """Decrypt using legacy shared key."""
        try:
            fernet = cls._get_legacy_instance()
            encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
            return fernet.decrypt(encrypted_bytes).decode()
        except Exception:
            return encrypted

    @classmethod
    def is_encrypted(cls, value: str) -> bool:
        """Check if a value appears to be encrypted."""
        if not value:
            return False
        try:
            base64.urlsafe_b64decode(value.encode())
            return True
        except Exception:
            return False


def encrypt_credentials(email: str, password: str, student_id: str = None) -> tuple[str, str]:
    """Encrypt email and password credentials."""
    return CredentialEncryptor.encrypt(email, student_id), CredentialEncryptor.encrypt(password, student_id)


def decrypt_credentials(encrypted_email: str, encrypted_password: str, student_id: str = None) -> tuple[str, str]:
    """Decrypt email and password credentials."""
    return (
        CredentialEncryptor.decrypt(encrypted_email, student_id),
        CredentialEncryptor.decrypt(encrypted_password, student_id)
    )


encryptor = CredentialEncryptor