import logging
import re
from typing import Any, Dict
from ai_engine.config import ROLE_PROFILES, ROLE_BRAND_OVERRIDES, COMPANY_IGNORE_TERMS
from ai_engine.utils.text_processing import squash_spaces, split_source_lines, dedupe_preserve_order, normalize_text_for_match
from ai_engine.utils.regex_patterns import EMAIL_REGEX, PHONE_REGEX, PROFILE_URL_PATTERNS, SECTION_LABEL_HINTS

logger = logging.getLogger("ai_engine.extractor")

def extract_source_profile(text: str) -> Dict[str, Any]:
    lines = split_source_lines(text)
    email_match = EMAIL_REGEX.search(text)
    phone_match = PHONE_REGEX.search(text)

    urls = []
    for pattern in PROFILE_URL_PATTERNS:
        for match in pattern.finditer(text):
            urls.append(match.group(0).rstrip(".,;|"))
    urls = dedupe_preserve_order(urls)

    email = email_match.group(0) if email_match else ""
    phone = squash_spaces(phone_match.group(0)) if phone_match else ""
    name = ""

    for line in lines[:12]:
        lower = line.lower()
        if len(line) > 60 or any(m in lower for m in SECTION_LABEL_HINTS):
            continue
        if email and email.lower() in lower: continue
        if any(token in lower for token in ["linkedin", "github", "http", "www."]): continue

        words = re.findall(r"[A-Za-z][A-Za-z'.-]+", line)
        if 2 <= len(words) <= 5 and sum(1 for w in words if w[0].isupper()) >= max(2, len(words) - 1):
            name = line
            break

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "links": urls[:3],
        "contact": " | ".join(dedupe_preserve_order([phone, email] + urls[:3])),
    }

def extract_target_company(job_info: str) -> str:
    patterns = [
        r"(?:company|organization|employer|client)\s*[:\-]\s*([^\n|]{2,80})",
        r"\bjoin\s+([A-Z][A-Za-z0-9&.,' -]{2,60})\s+(?:as|to|for|where|who|team)\b",
        r"\bopportunity\s+at\s+([A-Z][A-Za-z0-9&.,' -]{2,60})\b",
    ]
    for p in patterns:
        match = re.search(p, job_info, re.IGNORECASE)
        if match:
            company = squash_spaces(match.group(1)).strip(" -|,.;:")
            if company.lower() not in COMPANY_IGNORE_TERMS:
                return company
    return ""

def detect_role_profile(job_info: str) -> Dict[str, Any]:
    text = squash_spaces(job_info).lower()
    for profile_id, profile in ROLE_PROFILES.items():
        if re.search(profile["regex"], text):
            return {**profile, "id": profile_id}

    return {
        "id": "general",
        "family": "general",
        "categories": ["Languages", "Frameworks", "Backend", "Databases", "Tools"],
    }
