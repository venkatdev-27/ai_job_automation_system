"""
Resume Selector Module
=====================
Smart resume selection based on JD skill matching.
- Best matching bucket found → Use pre-generated PDF
- No match found → Generate new tailored resume
- Saves tailored resumes to student folder for reuse
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

import sys
import json
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from role_manager.dynamic_role_generator import SKILL_TO_ROLE, COMPREHENSIVE_SKILLS
except ImportError:
    SKILL_TO_ROLE = {}
    COMPREHENSIVE_SKILLS = {}

from config import settings

# Base resumes directory
RESUMES_BASE_DIR = Path(settings.resumes_dir)


class ResumeSelector:
    """
    Smart resume selector that decides which resume to use based on JD skills.
    Uses 200+ roles from dynamic_role_generator for precision.
    """
    
    def __init__(self, student_id: str = "default", profile_skills: list = None):
        self.student_id = student_id
        self.student_resumes_dir = RESUMES_BASE_DIR / student_id
        self.student_resumes_dir.mkdir(parents=True, exist_ok=True)
        
        # Metrics tracking
        self._last_selection_reason = ""
        self._last_bucket_used = ""
        
        # Load custom roles from MongoDB
        self.custom_roles = {}
        self.profile_skills = profile_skills or []
        try:
            from utils.student_mongodb import get_student_by_id
            student = get_student_by_id(student_id)
            if student and "custom_roles" in student:
                self.custom_roles = student["custom_roles"]
            # Also load skills from profile if available
            if student and "skills" in student:
                self.profile_skills = student["skills"]
        except Exception as e:
            print(f"[WARN] Could not load custom roles for {student_id}: {e}")

    def get_bucket_for_role(self, role_title: str, match_skill: str = "", jd_skills: list = None, job_title: str = "") -> str:
        """
        Map JD to one of the 6 Discovered Roles or trigger New Role generation.
        """
        title_lower = role_title.lower()
        job_title_lower = job_title.lower()
        jd_skills_lower = [s.lower() for s in jd_skills] if jd_skills else []
        
        # 1. Initialize scores for Discovery Roles (or fallbacks)
        if self.custom_roles:
            if isinstance(self.custom_roles, dict):
                buckets = self.custom_roles
            elif isinstance(self.custom_roles, list):
                # Convert list to dict for compatibility
                buckets = {}
                for role in self.custom_roles:
                    if isinstance(role, dict):
                        title = role.get("title", "unknown")
                        key = title.lower().replace(" ", "_")
                        buckets[key] = role
            else:
                buckets = {}
        else:
            # Fallback to defaults to identify general category if discovery hasn't run yet
            buckets = {
                "frontend_developer": {"title": "Frontend Developer", "keywords": ["React", "JS", "HTML"]},
                "backend_developer": {"title": "Backend Developer", "keywords": ["Node", "Java", "Python"]},
                "fullstack_developer": {"title": "Full Stack Developer", "keywords": ["React", "Node"]},
                "java_developer": {"title": "Java Developer", "keywords": ["Java", "Spring"]},
                "python_developer": {"title": "Python Developer", "keywords": ["Python", "Django"]},
                "data_engineer": {"title": "Data Engineer", "keywords": ["SQL", "Spark"]},
            }
            
        bucket_scores = {k: 0 for k in buckets.keys()}
        
        # 2. Score based on role keywords
        for key, config in buckets.items():
            keywords = config.get("keywords", [])
            for skill in jd_skills_lower:
                if any(kw.lower() == skill for kw in keywords):
                    bucket_scores[key] += 2.0
                elif any(kw.lower() in skill for kw in keywords if len(kw) > 3):
                    bucket_scores[key] += 1.0
            
            # Score based on title match
            role_display_title = config.get("title", "").lower()
            if role_display_title and (role_display_title in job_title_lower or role_display_title in title_lower):
                bucket_scores[key] += 10.0
                
            # STRICT MATCH: If the requested role_title matches the bucket key or title exactly, guarantee it wins
            sanitized_title = title_lower.replace(" ", "_").replace(".", "").replace("-", "_")
            if sanitized_title in key or key in sanitized_title or title_lower == role_display_title:
                bucket_scores[key] += 1000.0
                
        # 3. Add bonus for profile-matching skills (prioritize role that matches profile's primary skills)
        # Get profile skills if available (passed via jd_skills with prefix)
        profile_skills = getattr(self, 'profile_skills', [])
        if profile_skills:
            for key, config in buckets.items():
                keywords = config.get("keywords", [])
                for ps in profile_skills:
                    if any(ps.lower() == kw.lower() for kw in keywords):
                        bucket_scores[key] += 5.0
                
        # 4. Add random tie-breaker to avoid always picking same bucket
        import random
        for k in bucket_scores:
            bucket_scores[k] += random.uniform(0, 0.9)
        
        # 5. Final Decision
        best_bucket = max(bucket_scores, key=bucket_scores.get)
        
        return best_bucket

    def extract_main_skill(self, jd_text: str) -> str:
        """
        Extract the main/primary skill from job description.
        """
        if not jd_text:
            return ""
        
        jd_lower = jd_text.lower()
        all_skills = sorted(SKILL_TO_ROLE.keys(), key=len, reverse=True)
        
        for skill in all_skills:
            if skill.lower() in jd_lower:
                return skill
        
        return ""
    
    def find_best_role_dynamic(self, jd_skills: list) -> Tuple[str, float, str]:
        """
        Find the best matching role among 200+ roles.
        Returns (role_title, match_score, match_skill)
        """
        best_title = "Software Engineer"
        best_skill = ""
        best_score = 0.0
        
        jd_lower = [s.lower() for s in jd_skills]
        all_skills = sorted(SKILL_TO_ROLE.keys(), key=len, reverse=True)
        
        for skill in all_skills:
            if skill.lower() in jd_lower:
                title = SKILL_TO_ROLE[skill]
                score = 90.0
                if score > best_score:
                    best_score = score
                    best_title = title
                    best_skill = skill
                    break
        
        return best_title, best_score, best_skill
    
    def get_pre_generated_resume_path(self, role_key: str, job_title: str = "") -> Optional[Path]:
        """
        Get path to pre-generated resume.
        Priority: Student folder > Default folder.
        Now includes Alias/Bucket matching for smarter reuse.
        """
        try:
            from role_manager.dynamic_role_generator import ROLE_VARIATIONS
        except ImportError:
            ROLE_VARIATIONS = {}

        # 1. First Priority: Check for Aliases/Buckets if job_title is provided
        alias_filenames = []
        if job_title:
            job_title_lower = job_title.lower()
            for root_role, aliases in ROLE_VARIATIONS.items():
                all_variants = [root_role.lower()] + [a.lower() for a in aliases]
                if any(v in job_title_lower for v in all_variants):
                    # If job title matches an alias/root, add those specific PDFs to priority list
                    alias_filenames.append(f"{root_role.lower()}.pdf")
                    alias_filenames.append(f"{root_role.lower().replace(' ', '_')}.pdf")
                    if "developer" not in root_role.lower():
                         alias_filenames.append(f"{root_role.lower()} developer.pdf")

        # 2. Second Priority: Fall back to specific role_key from bucket scoring
        bucket_filenames = [f"{role_key}.pdf"]
        sanitized_key = role_key.replace("_", " ")
        bucket_filenames.append(f"{role_key}_developer.pdf")
        bucket_filenames.append(f"{sanitized_key.title()} Developer.pdf")
        
        # 3. Combine with Priority: Aliases first, then bucket matches
        filenames = list(dict.fromkeys([f.lower() for f in (alias_filenames + bucket_filenames)]))
        
        # Search Location 1: Student Folder
        for filename in filenames:
            path = self.student_resumes_dir / filename
            if path.exists():
                return path
                
        # 4. Final attempt: Try common variations of the role key
        variations = [
            role_key,
            role_key.replace("_", " "),
            role_key.replace(" ", "_"),
            role_key.replace(".", "_"),
            role_key.replace("_", "."),
            f"{role_key}_developer",
            f"{role_key.replace('_', ' ')} developer",
            role_key.replace("_developer", ""),
            role_key.replace(" developer", ""),
        ]
        
        # Add variations without dots/dashes
        clean_key = re.sub(r'[^a-z0-9]', '', role_key.lower())
        
        for filename in list(dict.fromkeys(filenames + [f"{v}.pdf" for v in variations])):
            f_lower = filename.lower()
            # Check for exact match first
            path = self.student_resumes_dir / f_lower
            if path.exists():
                return path
            
            # Check if any file in directory matches the clean key
            for existing_file in self.student_resumes_dir.glob("*.pdf"):
                existing_clean = re.sub(r'[^a-z0-9]', '', existing_file.stem.lower())
                if clean_key == existing_clean or existing_clean == clean_key.replace('developer', ''):
                    return existing_file
                
                # NEW: Fuzzy match - if role_key is a part of the filename (e.g., 'backend_developer' matches 'java_backend_developer.pdf')
                if clean_key in existing_clean or existing_clean in clean_key:
                    return existing_file
                    
        # 5. Last ditch: If "backend" is in role_key, look for ANY file containing "backend"
        if "backend" in role_key.lower():
            for existing_file in self.student_resumes_dir.glob("*backend*.pdf"):
                return existing_file
        
        if "frontend" in role_key.lower():
            for existing_file in self.student_resumes_dir.glob("*frontend*.pdf"):
                return existing_file
                    
        return None
    
    def get_tailored_resume_path(self, skill_name: str) -> Optional[Path]:
        """
        Get path to existing tailored resume (e.g., 'java developer.pdf')
        """
        if not skill_name:
            return None
        
        # Format: "java developer.pdf" or "react developer.pdf"
        filename = f"{skill_name.lower()} developer.pdf"
        tailored_path = self.student_resumes_dir / filename
        
        if tailored_path.exists():
            return tailored_path
        
        # Try sanitized version
        sanitized = skill_name.lower().replace(" ", "_").replace(".", "_")
        filename_san = f"{sanitized}_developer.pdf"
        tailored_path_san = self.student_resumes_dir / filename_san
        if tailored_path_san.exists():
            return tailored_path_san
        
        return None
    
    def _get_resume_skills(self, path: Path) -> list[str]:
        """Get or extract skills from a PDF file with caching."""
        cache_path = self.student_resumes_dir / "resume_skills_cache.json"
        cache = {}
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    cache = json.load(f)
            except:
                cache = {}
        
        file_key = path.name
        mtime = path.stat().st_mtime
        
        if file_key in cache and cache[file_key].get("mtime") == mtime:
            return cache[file_key].get("skills", [])
        
        # Not in cache or changed - extract text and skills
        from utils.pdf_reader import extract_text_from_pdf
        text = extract_text_from_pdf(path)
        skills = extract_skills_from_jd(text)
        
        # Update cache
        cache[file_key] = {"mtime": mtime, "skills": skills}
        try:
            with open(cache_path, "w") as f:
                json.dump(cache, f)
        except:
            pass
            
        return skills

    def select_resume(
        self, 
        jd_text: str, 
        jd_skills: Optional[list] = None,
        profile_skills: Optional[list] = None,
        job_title: str = ""
    ) -> Tuple[str, Optional[Path], str]:
        """
        Main selection logic.
        Now checks actual content match if bucket/alias match fails.
        """
        from utils.logger import get_logger
        logger = get_logger(Path("logs/pipeline.log"))
        
        if not jd_skills:
            jd_skills = extract_skills_from_jd(jd_text)
            
        # 1. Detect Best Matching Bucket
        best_bucket = self.get_bucket_for_role("discovered", jd_skills=jd_skills, job_title=job_title or jd_text[:100])
        self._last_bucket_used = best_bucket
        
        # 2. Priority 1: Check for high-confidence alias/bucket match
        resume_path = self.get_pre_generated_resume_path(best_bucket, job_title=job_title)
        if resume_path:
            self._last_selection_reason = "BUCKET_MATCH"
            logger.info(f"[RESUME_SELECTOR] Bucket: {best_bucket} | Reason: BUCKET_MATCH | File: {resume_path.name}")
            return "PRE_GENERATED", resume_path, f"Bucket/Alias match: {resume_path.name}"
            
        # 3. Priority 2: CONTENT MATCH - Scan existing resumes for JD skill overlap
        logger.info(f"Scanning existing resumes for skill overlap with JD (Skills: {jd_skills})...")
        best_content_match = None
        max_overlap = 0
        
        for existing_file in self.student_resumes_dir.glob("*.pdf"):
            resume_skills = self._get_resume_skills(existing_file)
            overlap = len(set(jd_skills) & set(resume_skills))
            
            # If we match > 50% of JD skills or at least 3 skills, it's a good candidate
            if overlap > max_overlap:
                max_overlap = overlap
                best_content_match = existing_file
                
        # If we have a strong overlap (e.g. at least 4 skills or > 60% of JD skills)
        threshold = min(4, len(jd_skills) * 0.6) if jd_skills else 1
        if best_content_match and max_overlap >= threshold:
            self._last_selection_reason = "CONTENT_MATCH"
            logger.info(f"[RESUME_SELECTOR] Bucket: {best_bucket} | Reason: CONTENT_MATCH | Overlap: {max_overlap} skills")
            return "PRE_GENERATED", best_content_match, f"Content match ({max_overlap} skills): {best_content_match.name}"
        
        # 4. TRIGGER AI SYNTHESIS (No good existing match found)
        ai_enabled = getattr(settings, 'ai_engine_enabled', True)
        if ai_enabled:
            self._last_selection_reason = "AI_TAILOR_NEEDED"
            logger.info(f"[RESUME_SELECTOR] Bucket: {best_bucket} | Reason: AI_TAILOR_NEEDED | JD: {job_title or 'unknown'}")
            return "AI_TAILOR_NEEDED", None, f"Dynamic synthesis required for {job_title}"
        
        # AI disabled - fall back to best available pre-generated resume
        self._last_selection_reason = "AI_DISABLED_FALLBACK"
        logger.warning(f"[RESUME_SELECTOR] Bucket: {best_bucket} | Reason: AI_DISABLED_FALLBACK | JD: {job_title}")
        fallback_path = self.get_pre_generated_resume_path(best_bucket or "developer", job_title=job_title)
        if fallback_path:
            return "PRE_GENERATED", fallback_path, f"AI disabled - using {fallback_path.name}"
        
        # Last resort - use generic backend resume
        generic_path = self._get_generic_resume_path("backend")
        if generic_path and generic_path.exists():
            return "PRE_GENERATED", generic_path, "AI disabled - using generic backend"
        
        # No resume found - still try AI as last resort
        self._last_selection_reason = "NO_RESUME_FOUND"
        logger.error(f"[RESUME_SELECTOR] Bucket: {best_bucket} | Reason: NO_RESUME_FOUND | JD: {job_title}")
        return "AI_TAILOR_NEEDED", None, f"Fallback: synthesis required for {job_title}"
    
    def get_tailored_filename(self, skill_name: str) -> str:
        """
        Get filename for tailored resume.
        Format: 'java developer.pdf', 'react developer.pdf'
        """
        if not skill_name:
            return "tailored.pdf"
        return f"{skill_name} developer.pdf"
    
    def save_tailored_resume(self, source_pdf_path: str, skill_name: str) -> Path:
        """
        Save AI-generated tailored resume to student folder for reuse.
        """
        import shutil
        
        if not skill_name:
            skill_name = self.extract_main_skill("")
        
        filename = self.get_tailored_filename(skill_name)
        dest_path = self.student_resumes_dir / filename
        
        # Copy the generated PDF to student folder
        if os.path.exists(source_pdf_path):
            shutil.copy2(source_pdf_path, dest_path)
        
        return dest_path


def extract_skills_from_jd(jd_text: str) -> list[str]:
    """
    Simple skill extraction from JD text.
    Looks for common tech keywords.
    """
    if not jd_text:
        return []
    
    jd_lower = jd_text.lower()
    
    # Common tech skills to look for
    skills = []
    
    skill_keywords = [
        # Frontend
        "react", "reactjs", "angular", "angularjs", "vue", "vuejs", "svelte", "jquery", "redux", "mobx", 
        "next.js", "nextjs", "gatsby", "typescript", "javascript", "ts", "js", "html", "css", "scss", "sass", 
        "tailwind", "bootstrap", "material ui", "mui", "chakra ui", "webpack", "vite", "babel", "jest", "cypress",
        
        # Backend / Languages
        "node", "nodejs", "express", "nestjs", "fastify", "koa", "python", "django", "flask", "fastapi", 
        "java", "spring", "spring boot", "hibernate", "jpa", "jdbc", "maven", "gradle", "c#", "c++", "golang", "go",
        "rust", "php", "laravel", "ruby", "rails", "dotnet", ".net",
        
        # Database
        "mongodb", "mysql", "postgresql", "postgres", "sqlite", "oracle", "sql", "nosql", "redis", 
        "elasticsearch", "cassandra", "dynamodb", "mariadb", "snowflake", "redshift", "bigquery",
        
        # DevOps / Cloud
        "docker", "kubernetes", "k8s", "jenkins", "aws", "azure", "gcp", "google cloud", "terraform", "ansible",
        "ci/cd", "github actions", "gitlab ci", "nginx", "apache", "linux", "ubuntu", "bash", "shell",
        
        # Data / ML
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop", "airflow",
        "etl", "kafka", "machine learning", "ml", "data engineering", "tableau", "power bi",
        
        # General / Tools
        "git", "github", "gitlab", "bitbucket", "jira", "confluence", "slack", "trello", "agile", "scrum",
        "rest", "restful", "graphql", "grpc", "soap", "json", "xml", "jwt", "oauth", "auth0", "firebase",
        "stripe", "twilio", "postman", "swagger", "docker compose",
        
        # Stacks
        "mern", "mean", "full stack", "fullstack", "lamp", "jamstack"
    ]
    
    for skill in skill_keywords:
        if skill in jd_lower:
            skills.append(skill)
    
    return list(set(skills))


# Standalone function for direct usage
def get_resume_for_jd(
    jd_text: str, 
    student_id: str = "default",
    jd_skills: Optional[list] = None,
    profile_skills: Optional[list] = None
) -> Tuple[str, Optional[Path], str]:
    """
    Get appropriate resume for a job description.
    
    Returns: (resume_type, resume_path, source)
    """
    selector = ResumeSelector(student_id)
    return selector.select_resume(jd_text, jd_skills, profile_skills)