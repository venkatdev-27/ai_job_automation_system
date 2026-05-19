import logging
import json
import os
from typing import List, Dict
from ai_engine.config import COMMON_EQUIVALENTS, SKILL_LABEL_OVERRIDES, ENGINE_ROOT
from ai_engine.utils.text_processing import squash_spaces, normalize_text_for_match
from ai_engine.utils.regex_patterns import ATS_KEYWORD_REGEXES, SKILL_BUCKET_PATTERNS
from ai_engine.core.llm_client import groq_llm_call

logger = logging.getLogger("ai_engine.skill_engine")

# Persistent Cache for dynamic classifications
SKILL_CACHE_FILE = ENGINE_ROOT / "cache" / "skill_classifications.json"

class SkillEngine:
    def __init__(self):
        self._load_cache()

    def _load_cache(self):
        self.cache = {}
        if SKILL_CACHE_FILE.exists():
            try:
                with open(SKILL_CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load skill cache: {e}")

    def _save_cache(self):
        try:
            SKILL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SKILL_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skill cache: {e}")

    def normalize_skill_text(self, text):
        value = squash_spaces(text).lower()
        replacements = {
            "&": " and ", ".net": " dotnet ", "asp.net": " aspnet ", 
            "node.js": " nodejs ", "express.js": " expressjs ",
            "next.js": " nextjs ", "react.js": " reactjs ",
            "vue.js": " vuejs ", "c sharp": " c# ",
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        import re
        value = re.sub(r"[^a-z0-9#+./ -]+", " ", value)
        return squash_spaces(value)

    def keyword_in_text(self, keyword, text):
        source = str(text or "").lower()
        for label, regex in ATS_KEYWORD_REGEXES:
            if label.lower() == keyword.lower():
                if regex.search(source):
                    return True
        
        norm_kw = self.normalize_skill_text(keyword)
        norm_src = self.normalize_skill_text(source)
        return norm_kw and norm_kw in norm_src

    def detect_skill_bucket(self, skill):
        norm = self.normalize_skill_text(skill)
        if not norm: return ""
        for bucket, patterns in SKILL_BUCKET_PATTERNS.items():
            if any(p.search(norm) for p in patterns):
                return bucket
        return ""

    async def async_classify_skill_with_llm(self, skill: str, categories: List[str]) -> str:
        """
        v3 Optimization: Async Dynamic Fallback.
        """
        # Check cache first
        cache_key = f"{skill.lower()}|{'|'.join(sorted(categories)).lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        logger.info(f"Dynamic Async Classification: Identifying category for '{skill}'")
        
        system_prompt = "You are an ATS optimization expert. Categorize tech skills."
        prompt = f"Skill: {skill}\nCategories: {', '.join(categories)}\nReturn ONLY the category name:"
        
        from ai_engine.core.llm_client import async_groq_llm_call
        result = await async_groq_llm_call(prompt, system_prompt=system_prompt)
        category = squash_spaces(result) if result else categories[0]
        
        matched_category = None
        for c in categories:
            if c.lower() == category.lower() or c.lower() in category.lower():
                matched_category = c; break
        
        final_category = matched_category or categories[0]
        self.cache[cache_key] = final_category
        # Note: We skip disk save inside the loop; handled by orchestrator later
        return final_category

    def classify_skill_with_llm(self, skill: str, categories: List[str]) -> str:
        # Backward compatibility for sync calls
        import asyncio
        return asyncio.run(self.async_classify_skill_with_llm(skill, categories))

    async def async_choose_skill_category(self, skill, expected_categories, preferred=""):
        cats = list(expected_categories or [])
        if not cats: return "Skills"
        
        # 1. Fast Path: Static Bucket Matching
        bucket = self.detect_skill_bucket(skill)
        for c in cats:
            if bucket and bucket in self.normalize_skill_text(c):
                return c
        
        # 2. Dynamic Fallback: Async LLM
        return await self.async_classify_skill_with_llm(skill, cats)

    def choose_skill_category(self, skill, expected_categories, preferred=""):
        import asyncio
        return asyncio.run(self.async_choose_skill_category(skill, expected_categories, preferred))

# Global singleton
skill_engine = SkillEngine()

# Standalone convenience wrappers
def keyword_in_text(keyword: str, text: str) -> bool:
    return skill_engine.keyword_in_text(keyword, text)
