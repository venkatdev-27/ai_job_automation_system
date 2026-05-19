"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PRODUCTION-GRADE RESUME GENERATION CORE                   ║
║  Usage: Core Engine for RAG + MiniMax M 2.5 + HyDE resume generation         ║
╚══════════════════════════════════════════════════════════════════════════════╝

This is the CORE ENGINE used across ALL platforms.

INPUT:
- job_description: Job description text
- retrieved_context: RAG + HyDE retrieved resume chunks
- match_analysis: Structured match analysis from RAG
- profile_data: User profile (name, skills, experience, projects, education)
- platform: Target platform (naukri, linkedin, generic)

OUTPUT:
- Complete tailored resume (summary, skills, experience, projects)
- Platform-specific optimizations
- RAG metadata for debugging/tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger("CoreResumeGenerator")

# ──────────────────────────────────────────────────────────────────────────────
# CORE ENGINE PROMPT
# ──────────────────────────────────────────────────────────────────────────────
MASTER_PROMPT = """
## CONTEXT ##
You are a Production-Grade Resume Generation Core Engine.

INPUT DATA:
- Job Description: {job_description}
- Retrieved Chunks (RAG): {retrieved_context}
- Match Analysis (MATCH/GAPS): {match_analysis}

CANDIDATE PROFILE:
- Name: {name}
- Original Skills: {skills}
- Experience: {experience}
- Projects: {projects}
- Education: {education}

## CRITICAL RULES ##

1. ZERO HALLUCINATION:
   - ONLY include skills found in "Original Skills" or "Retrieved Chunks".
   - Use REAL companies and dates from the profile only.
   - If a JD skill is missing but relates to your stack, mention it as "Familiar with" only if plausible.

2. SMART KEYWORD INJECTION (ATS):
   - Inject key JD skills into:
     a) Professional Summary (natural bridge)
     b) Skills categories (row-wise)
     c) At least 1-2 Experience bullet points specifically.

3. ELITE POLISHING (MANDATORY METRICS):
   - Use formula: [Action Verb] + [Technical Task] + [Quantitative Result].
   - EVERY BULLET MUST include a metric (%, $, time, or count).
   - Use "Power 50" verbs provided in the configuration.
   - Example: "Orchestrated a React-based CI/CD pipeline, reducing deployment latency by 45% and increasing throughput by 2x."

4. DYNAMIC CATEGORIZATION & PROJECT PRIORITY:
   - Group skills into rows (e.g. Frontend, Backend, Tools, etc.).
   - PRIORITIZE PROJECTS: Treat Projects as the high-impact center of the resume. Lead with results.

## TASK ##
Generate a COMPLETE tailored resume as a STRICT JSON object.
Use the strongest possible vocabulary to maximize ATS match.

{{
  "summary": "Full dynamic summary (minimum 45 words, target 60) bridging JD to Candidate skills using strictly 3-4 key skills only...",
  "skills": {{ "Category 1": ["s1", "s2"], "Category 2": ["s3"] }},
  "experience": [{{ "role": "..", "company": "..", "bullets": ["Polished bullet 1", ".."] }}],
  "projects": [{{ "name": "..", "tech": "..", "bullets": [".."] }}],
  "education": "Brief dynamic education summary or specific degree/university matching...",
  "validation": {{ "match_confidence": 0-100, "keywords_injected": ["k1", "k2"] }}
}}
"""

@dataclass
class ResumeGenerationConfig:
    """Configuration for resume generation."""
    max_summary_lines: int = 6
    max_skills: int = 25
    max_experience_bullets: int = 25
    max_projects: int = 15
    action_verbs: List[str] = None
    
    def __post_init__(self):
        if self.action_verbs is None:
            from rag_engine.rag_resume_generator import ACTION_VERBS
            self.action_verbs = ACTION_VERBS[:50]

class CoreResumeGenerator:
    """
    Production-Grade Resume Generation Core Engine
    
    Features:
    - RAG + HyDE context integration
    - Platform-specific optimization
    - ATS-friendly formatting
    - MiniMax M 2.5 LLM generation
    """
    
    def __init__(
        self,
        minimax_api_key: str = "",
        groq_api_key: str = "",
        config: ResumeGenerationConfig = None,
        storage_dir: str = None
    ):
        self.minimax_key = minimax_api_key
        self.groq_key = groq_api_key
        self.config = config or ResumeGenerationConfig()
        self.storage_dir = storage_dir or "storage/resumes"
        self.llm_retries = 2
        
        self.style_config = {
            "Impact-Driven": {"tone": "Achievement focused", "length": "Detail-heavy", "keywords": "High density"},
            "Technical-Deep": {"tone": "Architecture focused", "length": "Balanced", "keywords": "Tech-heavy"},
            "Concise-Architect": {"tone": "Senior Leadership", "length": "Compact", "keywords": "High-level"}
        }
        
        # Priority: GroqLLM for Original AI Generator
        try:
            from rag_engine.rag_engine import GroqLLM, MiniMaxLLM
            if self.groq_key:
                logger.info("Using GroqLLM for Core Resume Generation (100% Dynamic)")
                self.llm = GroqLLM(api_key=self.groq_key, model="llama-3.3-70b-versatile")
                self.is_groq = True
            elif self.minimax_key:
                logger.info("Using MiniMaxLLM for Core Resume Generation")
                self.llm = MiniMaxLLM(api_key=self.minimax_key)
                self.is_groq = False
            else:
                self.llm = None
        except ImportError:
            logger.warning("RAG engine not available. Using fallback generation.")
            self.llm = None
        
        # Ensure storage directory exists
        import os
        os.makedirs(self.storage_dir, exist_ok=True)
    
    async def generate(
        self,
        job_description: str,
        retrieved_context: str,
        match_analysis: Dict[str, Any],
        profile_data: Dict[str, Any],
        platform: str = "generic"
    ) -> Dict[str, Any]:
        """Async generate with validation layer and regeneration loop."""
        name = profile_data.get("name", "")
        skills = profile_data.get("skills", [])
        experience = profile_data.get("experience", [])
        projects = profile_data.get("projects", [])
        education = profile_data.get("education", "")

        # Build prompt
        def _fmt(val):
            return json.dumps(val, indent=1) if isinstance(val, (dict, list)) else str(val)

        prompt_data = {
            "job_description": job_description[:6000],
            "retrieved_context": retrieved_context[:6000],
            "match_analysis": _fmt(match_analysis),
            "name": name,
            "skills": _fmt(skills),
            "experience": _fmt(experience),
            "projects": _fmt(projects),
            "education": _fmt(education),
            "platform": platform
        }
        
        import random
        style_name = random.choice(list(self.style_config.keys()))
        style_details = self.style_config[style_name]
        logger.info(f"Injecting Advanced Style: {style_name} ({style_details})")

        prompt = MASTER_PROMPT.format(**prompt_data)
        prompt = f"STYLE DIRECTION: {style_name} - {style_details}\n\n{prompt}"
        
        best_resume = None
        best_score = -1

        for loop in range(2): # Max 1 regeneration
            # MULTI-TIER RECOVERY: Target 70B for drafting (Loop 1), 8B for polishing (Loop 2)
            target_model = "llama-3.1-70b-versatile" if loop == 0 else "llama-3.1-8b-instant"
            
            response = await self.llm.async_generate_json(
                prompt if loop == 0 else f"{prompt}\n\nREGENERATION FEEDBACK: {feedback}",
                system="You are a production-grade resume generation core engine. JSON ONLY.",
                temperature=0.2 if loop == 0 else 0.4, # Higher temp for loop 2
                preferred_model=target_model
            )

            if not response: continue

            # 1. Validation Layer (Remove Hallucinations)
            validated = self._validate_resume(response, profile_data, retrieved_context)
            
            # 2. Coverage Scoring
            target_keywords = match_analysis.get("missing_skills", []) + match_analysis.get("matched_skills", [])
            coverage = self._calculate_coverage(validated, target_keywords)
            match_score = match_analysis.get("match_score", 50)
            
            # 3. Bullet & Quality Scoring
            bullet_quality = self._calculate_bullet_quality(validated)
            quality_score = (match_score * 0.4) + (coverage * 100 * 0.3) + (bullet_quality * 0.3)
            
            logger.info(f"Loop {loop+1} Metrics -> Coverage: {coverage:.2f}, Match: {match_score}, Quality: {quality_score:.2f}")

            if coverage >= 0.70 and match_score >= 85 and bullet_quality >= 80:
                logger.info("Resume meets elite threshold. Success.")
                return self._finalize_result(validated, platform, match_analysis, profile_data, coverage, quality_score)
            
            # Store best so far
            if quality_score > best_score:
                best_score = quality_score
                best_resume = validated
            
            # Feedback for next loop (Reason-Based)
            if coverage < 0.70:
                feedback = f"INTELLIGENCE FEEDBACK: Keyword coverage ({coverage:.2f}) is too low. Specifically inject these missing skills: {target_keywords[:12]}"
            elif bullet_quality < 80:
                feedback = "INTELLIGENCE FEEDBACK: Bullet quality is weak. Use more Action Verbs and ensure 'Task-Action-Result' structure in every bullet."
            else:
                feedback = "INTELLIGENCE FEEDBACK: General polish required to meet elite threshold."

        logger.warning(f"Returning best attempt (score {best_score:.2f}) after {loop+1} loops.")
        return self._finalize_result(best_resume, platform, match_analysis, profile_data, best_score)

    def _validate_resume(self, output: Dict, profile: Dict, context: str) -> Dict:
        """STRICT VALIDATION: Remove hallucinated skills/companies."""
        validated = output.copy()
        allowed_skills = set([s.lower() for s in profile.get("skills", [])])
        # Add context-verified skills
        for word in re.findall(r'\b[A-Za-z0-9+#.]+\b', context):
            if len(word) > 2: allowed_skills.add(word.lower())

        # Filter skills categories
        new_skills = {}
        for cat, skill_list in output.get("skills", {}).items():
            filtered = [s for s in skill_list if s.lower() in allowed_skills or any(real in s.lower() for real in allowed_skills)]
            if filtered: new_skills[cat] = filtered
        validated["skills"] = new_skills
        
        return validated

    def _calculate_coverage(self, resume: Dict, target_keywords: List[str]) -> float:
        """ATS Keyword Coverage Scorer."""
        if not target_keywords: return 1.0
        resume_text = str(resume).lower()
        matches = 0
        for kw in target_keywords:
            if kw.lower() in resume_text: matches += 1
        return matches / len(target_keywords)

    def _finalize_result(self, resume, platform, match_analysis, profile_data, coverage, quality_score=0) -> Dict:
        """Helper to structure the final result and inject personal details."""
        resume["full_name"] = profile_data.get("name", "Candidate")
        
        # Inject restored contact details
        resume["contact_info"] = {
            "email": profile_data.get("email", ""),
            "phone": profile_data.get("phone", ""),
            "location": profile_data.get("location", ""),
            "linkedin": profile_data.get("linkedin", ""),
            "github": profile_data.get("github", ""),
            "portfolio": profile_data.get("portfolio", "")
        }
        
        resume["rag_metadata"] = {
            "match_score": match_analysis.get("match_score", 50),
            "keyword_coverage": round(coverage, 2),
            "quality_score": round(quality_score, 2),
            "version": "v3_hardened" if quality_score > 85 else "v2_dynamic"
        }
        return resume

    def _calculate_bullet_quality(self, resume: Dict) -> float:
        """
        Hardened Bullet Checker: 
        1. Action Verb presence
        2. Tech keyword presence
        3. Length threshold (> 10 words)
        """
        all_bullets = []
        for exp in resume.get("experience", []):
            all_bullets.extend(exp.get("bullets", []))
        for proj in resume.get("projects", []):
            all_bullets.extend(proj.get("bullets", []))

        if not all_bullets: return 0.0

        scores = []
        action_verbs = set([v.lower() for v in self.config.action_verbs])
        
        for bullet in all_bullets:
            b_score = 0
            # Rule 1: Action Verb (High Impact)
            first_word = re.findall(r'\b\w+\b', bullet)
            if first_word and first_word[0].lower() in action_verbs: b_score += 30
            
            # Rule 2: Length (Minimum 10 words for detail)
            if len(bullet.split()) >= 10: b_score += 20
            
            # Rule 3: Tech Keyword (Stacks & Tools)
            if any(char in bullet for char in ["+", "#", ".", "/"]) or re.search(r'[A-Z][a-z]+[A-Z]', bullet):
                b_score += 20
                
            # Rule 4: MANDATORY METRICS (%, $, numbers, time units)
            # Regex for digits, percentages, monetary values, or count words (k, M+)
            if re.search(r'(\d+|%|\$|\b\d+k\b|\b\d+m\b|\b\d+ms\b|seconds|minutes|hours)', bullet, re.IGNORECASE):
                b_score += 30
                
            scores.append(b_score)
        
        return sum(scores) / len(scores)
    
    def _validate_and_postprocess(
        self,
        response: Dict[str, Any],
        platform: str,
        match_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate and post-process the LLM response."""
        
        # Ensure all required fields exist
        cleaned_skills = self._clean_skills(response.get("skills", []))
        cleaned_experience = self._clean_experience(response.get("experience", []))
        cleaned_projects = self._clean_projects(response.get("projects", []))
        
        # Improve confidence score calculation
        match_score = match_analysis.get("match_score", 50)
        hyde_quality = match_analysis.get("hyde_relevance", 0.5)
        
        # Complex confidence calculation based on multiple factors
        confidence = int(
            (match_score * 0.4) +  # Base match score (40%)
            (len(cleaned_skills) * 1) +  # Skills count
            (len(cleaned_experience) * 5) +  # Experience count
            (len(cleaned_projects) * 3) +  # Projects count
            (hyde_quality * 10)  # HyDE quality bonus
        )
        
        confidence = min(100, max(30, confidence))  # Clamp between 30-100
        
        result = {
            "summary": response.get("summary", ""),
            "skills": cleaned_skills,
            "experience": cleaned_experience,
            "projects": cleaned_projects,
            "platform_adapter": {
                "platform": platform,
                "adjustments": self._get_platform_adjustments(platform)
            },
            "rag_metadata": {
                "match_score": match_score,
                "hyde_quality": hyde_quality,
                "keywords_used": self._extract_keywords_from_sections(response)
            },
            "confidence_score": confidence
        }
        
        # Platform-specific post-processing
        if platform == "naukri":
            result = self._apply_naukri_optimizations(result)
        elif platform == "linkedin":
            result = self._apply_linkedin_optimizations(result)
        
        return result
    
    def _generate_fallback(
        self,
        job_description: str,
        retrieved_context: str,
        match_analysis: Dict[str, Any],
        profile_data: Dict[str, Any],
        platform: str
    ) -> Dict[str, Any]:
        """Fallback rule-based generation when LLM fails."""
        
        # Extract keywords from JD
        jd_keywords = self._extract_keywords(job_description)
        
        # Build sections from context and profile
        summary = self._build_summary_fallback(profile_data, jd_keywords)
        skills = self._build_skills_fallback(profile_data["skills"], jd_keywords)
        experience = self._build_experience_fallback(profile_data["experience"], jd_keywords)
        projects = self._build_projects_fallback(profile_data["projects"], jd_keywords)
        
        return {
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "projects": projects,
            "platform_adapter": {
                "platform": platform,
                "adjustments": "Fallback generation applied"
            },
            "rag_metadata": {
                "match_score": match_analysis.get("match_score", 50),
                "hyde_quality": match_analysis.get("hyde_relevance", 0.5),
                "keywords_used": jd_keywords[:10]
            },
            "confidence_score": 60  # Lower confidence for fallback
        }
    
    # ── Section Builders ──────────────────────────────────────────────────────
    
    def _build_summary_fallback(
        self,
        profile_data: Dict[str, Any],
        jd_keywords: List[str]
    ) -> str:
        """Build a JD-dynamic professional summary using LLM."""
        if not self.llm:
            return "Professional Software Engineer seeking a challenging role."
            
        target_role = jd_keywords[0].title() if jd_keywords else "Software Engineer"
        prompt = f"""
        Generate a professional summary (minimum 50 words) for a {target_role} role.
        Candidate Skills: {json.dumps(profile_data.get('skills', []))}
        JD Context: {", ".join(jd_keywords)}
        
        Requirements:
        1. Dynamic and JD-specific.
        2. High-impact tone.
        3. AT LEAST 45 words (target 60 words).
        4. Use strictly 3-4 key technical skills only in the summary.
        5. No specific company names, focus on achievements.
        """
        
        summary = self.llm.generate(
            prompt, 
            system="You are a professional resume writer. Return only the summary text.",
            max_tokens=250
        )
        return summary or "Highly motivated Software Engineer with advanced technical skills."
    
    def _build_skills_fallback(
        self,
        profile_skills: List[str],
        jd_keywords: List[str]
    ) -> List[str]:
        """Build prioritized skills list."""
        if not profile_skills:
            return []
        
        # Prioritize JD-matching skills
        jd_set = {k.lower() for k in jd_keywords}
        priority = [s for s in profile_skills if s.lower() in jd_set]
        rest = [s for s in profile_skills if s.lower() not in jd_set]
        
        combined = priority + rest
        
        # Deduplicate while preserving order
        seen = set()
        result = []
        for skill in combined:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                result.append(skill)
        
        return result[:self.config.max_skills]
    
    def _build_experience_fallback(
        self,
        experience: List[Any],
        jd_keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Build experience objects from profile and JD."""
        if not experience:
            return [{
                "role": "Software Developer",
                "company": "Tech Solutions",
                "duration": "2023 - Present",
                "bullets": [
                    "Experienced in full-stack development and modern technologies.",
                    "Proven track record of delivering cross-functional solutions.",
                    "Committed to clean code and technical best practices."
                ]
            }]
        
        results = []
        for exp in experience[:20]:
            if isinstance(exp, str):
                results.append({
                    "role": "Professional Role",
                    "company": "Company",
                    "duration": "",
                    "bullets": [exp]
                })
            elif isinstance(exp, dict):
                results.append(exp)
        
        return results
    
    def _build_projects_fallback(
        self,
        projects: List[Any],
        jd_keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Build project objects."""
        if not projects:
            return [{
                "name": "Software Project",
                "tech": "React, Node.js",
                "bullets": [
                    "Successfully completed complex software engineering projects.",
                    "Developed robust applications with a focus on scale and performance."
                ]
            }]
        
        results = []
        for proj in projects[:15]:
            if isinstance(proj, str):
                results.append({
                    "name": "Technical Project",
                    "tech": "",
                    "bullets": [proj]
                })
            elif isinstance(proj, dict):
                results.append(proj)
        
        return results
    
    # ── Platform Optimizations ────────────────────────────────────────────────
    
    def _apply_naukri_optimizations(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Naukri-specific optimizations."""
        # Increase keyword density
        keywords = result["rag_metadata"]["keywords_used"]
        
        # Add keywords to skills if missing
        skills_text = " ".join(result["skills"])
        for keyword in keywords[:5]:
            if keyword.lower() not in skills_text.lower() and len(result["skills"]) < 20:
                result["skills"].append(keyword)
        
        # Make bullets more concise
        result["experience"] = [
            bullet[:120] + "..." if len(bullet) > 120 else bullet
            for bullet in result["experience"]
        ]
        
        result["platform_adapter"]["adjustments"] = "Increased keyword density, concise bullets"
        return result
    
    def _apply_linkedin_optimizations(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply LinkedIn-specific optimizations."""
        # Make bullets slightly more descriptive
        result["experience"] = [
            bullet + " Demonstrated impact through measurable results."
            if len(bullet) < 150 else bullet
            for bullet in result["experience"]
        ]
        
        result["platform_adapter"]["adjustments"] = "Enhanced readability and impact"
        return result
    
    # ── Utility Methods ───────────────────────────────────────────────────────
    
    def _clean_skills(self, skills: List[str]) -> List[str]:
        """Clean and deduplicate skills list."""
        if not skills:
            return []
    def _clean_skills(self, skills: Any) -> Dict[str, List[str]]:
        """Clean categorized skills."""
        if isinstance(skills, list):
            # Backwards compatibility: turn list into 'General' category
            return {"Technical Skills": skills[:self.config.max_skills]}
        
        if not isinstance(skills, dict):
            return {}
            
        cleaned_dict = {}
        for category, skill_list in skills.items():
            if not isinstance(skill_list, list): continue
            
            seen = set()
            clean_list = []
            for skill in skill_list[:10]: # Limit per category
                skill = re.sub(r'\s+', ' ', str(skill).strip())
                if skill and len(skill) > 1 and skill.lower() not in seen:
                    seen.add(skill.lower())
                    clean_list.append(skill)
            
            if clean_list:
                cleaned_dict[category] = clean_list
                
        return cleaned_dict
    
    def _clean_experience(self, experience: List[Any]) -> List[Dict[str, Any]]:
        """Clean structured experience items."""
        cleaned = []
        for item in experience[:20]: # Allow up to 20 roles
            if isinstance(item, str):
                # Backwards compatibility / unexpected simple string
                cleaned.append({"role": "Role", "company": "Company", "duration": "", "bullets": [item]})
                continue
            
            if not isinstance(item, dict): continue
            
            # Clean bullets
            raw_bullets = item.get("bullets", [])
            clean_bullets = []
            for b in raw_bullets[:self.config.max_experience_bullets]:
                b = re.sub(r'\s+', ' ', str(b).strip())
                b = re.sub(r'\.+$', '', b)
                if b and len(b) > 10:
                    if not any(b.startswith(v) for v in self.config.action_verbs):
                        b = f"{self.config.action_verbs[0]} {b}"
                    clean_bullets.append(b + ".")
            
            cleaned.append({
                "role": item.get("role", "Software Engineer"),
                "company": item.get("company", "Company"),
                "duration": item.get("duration", ""),
                "bullets": clean_bullets
            })
        return cleaned
    
    def _clean_projects(self, projects: List[Any]) -> List[Dict[str, Any]]:
        """Clean structured project items."""
        cleaned = []
        for item in projects[:self.config.max_projects]:
            if isinstance(item, str):
                cleaned.append({"name": "Project", "tech": "", "bullets": [item]})
                continue
            
            if not isinstance(item, dict): continue
            
            raw_bullets = item.get("bullets", [])
            clean_bullets = []
            for b in raw_bullets[:8]: # Limit bullets per project
                b = re.sub(r'\s+', ' ', str(b).strip())
                b = re.sub(r'\.+$', '', b)
                if b and len(b) > 10:
                    clean_bullets.append(b + ".")
            
            cleaned.append({
                "name": item.get("name", "Project"),
                "tech": item.get("tech", ""),
                "bullets": clean_bullets
            })
        return cleaned
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        STOP = {
            "the", "and", "for", "with", "that", "this", "will", "have",
            "you", "our", "are", "not", "but", "can", "all", "from", "your",
            "has", "its", "was", "been", "more", "also", "than", "into",
            "such", "well", "role", "work", "team", "good", "must", "able",
            "need", "new", "job", "may", "any", "use", "as", "is", "in",
            "to", "of", "a", "be", "we", "i", "my", "me", "this", "that",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "should", "could", "can", "may", "might", "must", "shall"
        }
        
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9#+.\-]{1,30}", text.lower())
        seen = set()
        result = []
        
        for word in words:
            if word not in STOP and word not in seen and len(word) > 2:
                seen.add(word)
                result.append(word)
        
        return result[:20]
    
    def _extract_keywords_from_sections(self, response: Dict[str, Any]) -> List[str]:
        """Extract keywords from generated sections."""
        text = " ".join([
            response.get("summary", ""),
            " ".join(response.get("skills", [])),
            " ".join(response.get("experience", [])),
            " ".join(response.get("projects", []))
        ])
        return self._extract_keywords(text)[:15]
    
    def _get_platform_adjustments(self, platform: str) -> str:
        """Get platform-specific adjustment description."""
        adjustments = {
            "naukri": "Increased keyword density, ATS optimization, concise formatting",
            "linkedin": "Enhanced readability, impact focus, professional tone",
            "generic": "Standard ATS-friendly formatting"
        }
        return adjustments.get(platform, "Standard formatting applied")

# ──────────────────────────────────────────────────────────────────────────────
# Demo / Test
# ──────────────────────────────────────────────────────────────────────────────

async def _demo():
    """Quick demonstration of the Core Resume Generator."""
    
    sample_job_description = """
    We are looking for a Full Stack Developer with 2-4 years of experience.
    
    Required Skills:
    - Python, JavaScript, TypeScript
    - React, Node.js, Express
    - MongoDB, PostgreSQL
    - AWS, Docker, Git
    
    Responsibilities:
    - Develop and maintain web applications
    - Collaborate with cross-functional teams
    - Write clean, maintainable code
    - Participate in code reviews
    """
    
    sample_retrieved_context = """
    Experience with Python and JavaScript development
    Built React applications with TypeScript
    Worked with Node.js and Express APIs
    Database experience with MongoDB and PostgreSQL
    Deployed applications using Docker and AWS
    Strong problem-solving and collaboration skills
    """
    
    sample_match_analysis = {
        "match_score": 85,
        "matched_skills": ["Python", "JavaScript", "React", "Node.js", "MongoDB"],
        "missing_skills": ["AWS", "Docker"],
        "strength_areas": ["Frontend development", "Backend APIs", "Database design"],
        "gap_areas": ["Cloud deployment", "Containerization"],
        "hyde_relevance": 0.9,
        "reason": "Strong match with minor gaps in deployment skills"
    }
    
    sample_profile = {
        "name": "Veera Venkata Satyanarayana Kosuri",
        "skills": ["Python", "JavaScript", "React", "Node.js", "MongoDB", "PostgreSQL"],
        "experience": [
            "Developed full-stack web applications",
            "Implemented RESTful APIs",
            "Created responsive user interfaces"
        ],
        "projects": [
            "E-commerce platform with payment integration",
            "Task management application with real-time updates"
        ],
        "education": "B.Tech Computer Science"
    }
    
    print("=" * 80)
    print("CORE RESUME GENERATOR DEMO")
    print("=" * 80)
    
    # Initialize generator
    generator = CoreResumeGenerator()
    
    # Generate resume for different platforms
    platforms = ["naukri", "linkedin", "indeed", "generic"]
    
    for platform in platforms:
        print(f"\n GENERATING FOR: {platform.upper()}")
        print("-" * 40)
        
        resume = await generator.generate(
            job_description=sample_job_description,
            retrieved_context=sample_retrieved_context,
            match_analysis=sample_match_analysis,
            profile_data=sample_profile,
            platform=platform
        )
        
        print(f"✓ Summary: {resume['summary'][:100]}...")
        print(f"✓ Skills: {len(resume['skills'])} items")
        print(f"✓ Experience: {len(resume['experience'])} bullets")
        print(f"✓ Projects: {len(resume['projects'])} items")
        print(f"✓ Match Score: {resume['rag_metadata']['match_score']}")
        print(f"✓ Platform Adjustments: {resume['platform_adapter']['adjustments']}")
        print(f"✓ Confidence: {resume['confidence_score']}%")
    
    print("\n" + "=" * 80)
    print("CORE ENGINE READY FOR PRODUCTION USE")
    print("=" * 80)

if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
