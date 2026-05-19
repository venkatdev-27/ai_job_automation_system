import logging
import re
from typing import List, Dict, Any
from ai_engine.config import SUMMARY_WORD_MIN, SUMMARY_WORD_MAX, BULLET_WORD_MIN, BULLET_WORD_MAX
from ai_engine.utils.text_processing import count_words, normalize_text_for_match
from ai_engine.core.skill_engine import keyword_in_text

logger = logging.getLogger("ai_engine.validator")

def validate_resume_json(data: Dict[str, Any], candidate_data: str, role_brand: str, **kwargs) -> List[str]:
    errors = []
    
    # Summary Validation
    summary = data.get("summary", "").strip()
    c_words = count_words(summary)
    prefixes = [f"Aspiring {role_brand}", f"Entry-level {role_brand}", f"Professional {role_brand}"]
    
    if not any(summary.lower().startswith(p.lower()) for p in prefixes):
        errors.append(f"Summary must start with one of: {prefixes}")
    
    if not (SUMMARY_WORD_MIN <= c_words <= SUMMARY_WORD_MAX):
        errors.append(f"Summary word count {c_words} is outside {SUMMARY_WORD_MIN}-{SUMMARY_WORD_MAX}")

    # Section-specific validation
    for section in ["experience", "projects"]:
        for entry in data.get(section, []):
            for bullet in entry.get("bullets", []):
                b_words = count_words(bullet)
                if not (BULLET_WORD_MIN <= b_words <= BULLET_WORD_MAX):
                    errors.append(f"Bullet in {section} has {b_words} words (Limit: {BULLET_WORD_MIN}-{BULLET_WORD_MAX})")

    # Identity Preservation
    source_profile = kwargs.get("source_profile", {})
    if source_profile.get("email") and source_profile["email"].lower() not in str(data.get("contact", "")).lower():
        errors.append("Contact info must preserve source email.")
    
    if source_profile.get("name") and normalize_text_for_match(source_profile["name"]) not in normalize_text_for_match(data.get("full_name", "")):
        errors.append("Full name must match source data.")

    # Skill Grounding (Anti-Hallucination)
    all_skills = []
    for cat_name, skills in data.get("skills", {}).items():
        if isinstance(skills, list):
            all_skills.extend(skills)
            if not skills:
                errors.append(f"Skill category '{cat_name}' is empty.")
    
    source_context = f"{candidate_data}\n{kwargs.get('job_info', '')}"
    unverified = [s for s in all_skills if not keyword_in_text(s, source_context)]
    if unverified:
        errors.append(f"Unverified skills detected: {', '.join(unverified)}")

    return errors
