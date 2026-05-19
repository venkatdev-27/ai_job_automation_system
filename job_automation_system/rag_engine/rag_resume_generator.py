"""
RAG-Based Role Resume Generator
=============================
Creates 5-6 role-specific resumes using Master Profile (MongoDB) + AI Tailoring.
Stage 1: Multi-Role Base (Pre-generated from MongoDB data)
Stage 2: Job-Specific Polishing (On-the-fly per application)
"""

import asyncio
import json
import os
import re
import httpx
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from utils.path_contract import resolve_ai_engine_pdf_path

IN_DOCKER = os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()

RESUMES_DIR = Path(os.getenv("RESUMES_DIR", "/app/ai_engine/resumes" if IN_DOCKER else "D:/ai-bot-resumes/ai_engine/resumes"))
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

# Initial empty config - will be populated via discover_top_roles
ROLE_CONFIGS = {}

# 300+ ATS-Optimized Action Verbs for Resume Enhancement
ACTION_VERBS = [
    # Leadership & Strategic (40+)
    "Spearheaded", "Orchestrated", "Chaired", "Mobilized", "Pioneered", "Championed", "Directed", "Executed",
    "Led", "Governed", "Influenced", "Mentored", "Coached", "Trained", "Developed", "Established", "Founded",
    "Initiated", "Launched", "Transformed", "Reorganized", "Restructured", "Revitalized", "Modernized",
    "Pioneered", "Innovated", "Generated", "Secured", "Acquired", "Negotiated", "Facilitated", "Partnered",
    "Collaborated", "Aligned", "Integrated", "Consolidated", "Synthesized", "Strategized", "Roadmapped",
    "Visualized", "Conceptualized", "Conceptualized", "Devised", "Formulated", "Designed",
    # Technical Excellence (60+)
    "Architected", "Engineered", "Developed", "Built", "Created", "Constructed", "Implemented", "Deployed",
    "Integrated", "Configured", "Customized", "Optimized", "Enhanced", "Refactored", "Restructured", "Rewrote",
    "Debugged", "Diagnosed", "Resolved", "Troubleshot", "Maintained", "Supported", "Administered", "Managed",
    "Monitored", "Automated", "Scripted", "Programmed", "Compiled", "Tested", "Validated", "Verified",
    "Certified", "Audited", "Reviewed", "Assessed", "Analyzed", "Evaluated", "Investigated", "Examined",
    "Explored", "Discovered", "Identified", "Pinpointed", "Detected", "Uncovered", "Mapped", "Correlated",
    "Benchmarked", "Measured", "Profiled", "Instrumented", "Instrumented", "Virtualized", "Containerized",
    "Containerized", "Orchestrated", "Provisioned", "Scaled", "Elasticized", "Balanced", "Load Balanced",
    "Distributed", "Decentralized", "Centralized", "Standardized", "Normalized", "Modularized", "Abstracted",
    # Efficiency & Performance (40+)
    "Streamlined", "Simplified", "Accelerated", "Expedited", "Quickened", "Fast-Tracked", "Boosted", "Elevated",
    "Amplified", "Augmented", "Enhanced", "Improved", "Upgraded", "Enhanced", "Refined", "Polished", "Perfected",
    "Maximized", "Minimized", "Reduced", "Decreased", "Cut", "Trimmed", "Slashed", "Eliminated", "Removed",
    "Saved", "Conserved", "Preserved", "Rationalized", "Consolidated", "Merged", "Unified", "Standardized",
    "Synchronized", "Orchestrated", "Coordinated", "Sequenced", "Prioritized", "Weighted", "Balanced", "Optimized",
    # Data & Analytics (35+)
    "Quantified", "Calculated", "Computed", "Processed", "Extracted", "Transformed", "Loaded", "Cleaned",
    "Visualized", "Illustrated", "Represented", "Modeled", "Simulated", "Predicted", "Forecasted", "Projected",
    "Estimated", "Determined", "Derived", "Concluded", "Inferred", "Extrapolated", "Interpolated", "Aggregated",
    "Segmented", "Categorized", "Classified", "Indexed", "Catalogued", "Organized", "Structured", "Formatted",
    "Packaged", "Delivered", "Distributed", "Reported", "Documented",
    # Product & Design (35+)
    "Designed", "Conceptualized", "Envisioned", "Visualized", "Prototyped", "Mocked", "Wireframed", "Sketched",
    "Planned", "Planned", "Scheduled", "Mapped", "Outlined", "Drafted", "Authored", "Composed", "Wrote",
    "Edited", "Revised", "Updated", "Refreshed", "Redesigned", "Reimagined", "Reengineered", "Rebuilt",
    "Repositioned", "Renovated", "Reconstructed", "Refurbished", "Revamped", "Overhauled", "Replaced", "Superseded",
    # Communication & Collaboration (35+)
    "Presented", "Demonstrated", "Illustrated", "Explained", "Clarified", "Simplified", "Conveyed", "Conveyed",
    "Communicated", "Negotiated", "Persuaded", "Influenced", "Convinced", "Advocated", "Promoted", "Marketed",
    "Sold", "Brokered", "Settled", "Agreed", "Arranged", "Organized", "Convened", "Conducted", "Chaired",
    "Facilitated", "Moderated", "Mediated", "Arbitrated", "Reconciled", "Collaborated", "Cooperated", "Participated",
    "Engaged", "Connected", "Linked", "Networked", "Partnered", "Allied",
    # Problem Solving (30+)
    "Solved", "Resolved", "Fixed", "Rectified", "Corrected", "Reversed", "Remediated", "Addressed", "Tackled",
    "Confronted", "Mitigated", "Alleviated", "Minimized", "Prevented", "Averted", "Avoided", "Circumvented",
    "Bypassed", "Overcame", "Conquered", "Cracked", "Deciphered", "Decoded", "Disentangled", "Unraveled",
    "Untangled", "Simplified", "Streamlined", "Rationalized", "Troubleshot", "Debugged", "Diagnosed", "Treated",
    "Healed", "Restored", "Renewed", "Revived", "Rejuvenated",
    # Achievement & Results (40+)
    "Achieved", "Accomplished", "Completed", "Delivered", "Executed", "Finished", "Finalized", "Concluded",
    "Reached", "Met", "Exceeded", "Surpassed", "Outperformed", "Outstripped", "Outpaced", "Beat", "Defeated",
    "Won", "Earned", "Gained", "Secured", "Obtained", "Acquired", "Procured", "Attained", "Realized", "Materialized",
    "Generated", "Produced", "Created", "Established", "Instituted", "Pioneered", "Spearheaded", "Led", "Guided",
    "Directly contributed", "Impacted", "Affected", "Influenced", "Shaped", "Molded", "Forged", "Crafted",
    "Engineered", "Orchestrated", "Choreographed", "Conducted",
    # Quality & Compliance (25+)
    "Ensured", "Guaranteed", "Assured", "Secured", "Safeguarded", "Protected", "Shielded", "Defended",
    "Verified", "Validated", "Confirmed", "Certified", "Qualified", "Accredited", "Audited", "Inspected",
    "Reviewed", "Evaluated", "Assessed", "Tested", "Screened", "Checked", "Monitored", "Controlled", "Governed",
    "Regulated", "Compliant", "Adhered", "Conformed", "Observated",
    # Learning & Growth (20+)
    "Researched", "Studied", "Investigated", "Explored", "Examined", "Surveyed", "Queried", "Queried",
    "Gathered", "Collected", "Compiled", "Compiled", "Synthesized", "Inferred", "Deduced", "Concluded",
    "Adapted", "Adjusted", "Modified", "Customized", "Tailored", "Personalized", "Calibrated", "Fine-tuned",
    "Optimized", "Refined", "Mastered", "Specialized", "Deepened",
    # Customer & Stakeholder (25+)
    "Serviced", "Assisted", "Aided", "Helped", "Supported", "Backed", "Sponsored", "Funded", "Financed",
    "Invested", "Betted", "Ventured", "Partnered", "Allied", "Aligned", "Engaged", "Interfaced", "Liaised",
    "Corresponded", "Corresponded", "Responded", "Replied", "Answered", "Addressed", "Attended", "Accommodated",
    "Catered", "Satisfied", "Pleased", "Delighted", "Impressed", "Wowed",
    # Time & Resource Management (20+)
    "Prioritized", "Sequenced", "Scheduled", "Timed", "Paced", "Planned", "Projected", "Estimated", "Allocated",
    "Assigned", "Delegated", "Distributed", "Dispensed", "Budgeted", "Economized", "Saved", "Conserved",
    "Reused", "Recycled", "Reclaimed", "Recovered", "Retrieved", "Restored", "Replenished", "Supplemented",
    # Innovation & Creativity (20+)
    "Invented", "Originated", "Initiated", "Introduced", "Presented", "Proposed", "Suggested", "Recommended",
    "Advised", "Counseled", "Consulted", "Brainstormed", "Ideated", "Conceptualized", "Visualized", "Designed",
    "Crafted", "Forged", "Shaped", "Molded", "Transformed", "Revolutionized", "Disrupted", "Changed", "Altered",
    # Additional Power Verbs (30+)
    "Empowered", "Enabled", "Facilitated", "Leveraged", "Utilized", "Exploited", "Harnessed", "Captured",
    "Harvested", "Extracted", "Won", "Awarded", "Honored", "Recognized", "Acknowledged", "Celebrated",
    "Published", "Authored", "Documented", "Recorded", "Logged", "Filed", "Catalogued", "Indexed", "Cross-referenced",
    "Correlated", "Linked", "Connected", "Integrated", "Seamlessly integrated", "Unified", "Converged",
    "Diversified", "Expanded", "Grew", "Increased", "Scaled"
]


def _get_dynamic_verbs(count: int = 3) -> str:
    """Get random unique verbs for bullet polishing."""
    import random
    verbs = random.sample(ACTION_VERBS, min(count, len(ACTION_VERBS)))
    return ", ".join(verbs)


def _dedupe_skills(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in skills:
        token = str(item or "").strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


def _extract_skills_from_mongo(data: dict) -> list[str]:
    """
    Normalize candidate skills across schema variants.
    Priority:
    1) top-level skills
    2) resumeData.skills / technical_skills / tools / frameworks / languages
    3) categorized_skills flattened
    4) custom_roles keywords flattened
    """
    skills: list[str] = []

    top = data.get("skills")
    if isinstance(top, list):
        skills.extend(top)

    resume_data = data.get("resumeData", {})
    if isinstance(resume_data, dict):
        for key in ("skills", "technical_skills", "tools", "frameworks", "languages"):
            values = resume_data.get(key)
            if isinstance(values, list):
                skills.extend(values)

    categorized = data.get("categorized_skills", {})
    if isinstance(categorized, dict):
        for values in categorized.values():
            if isinstance(values, list):
                skills.extend(values)

    custom_roles = data.get("custom_roles")
    if isinstance(custom_roles, dict):
        for role_cfg in custom_roles.values():
            if isinstance(role_cfg, dict):
                role_keywords = role_cfg.get("keywords")
                if isinstance(role_keywords, list):
                    skills.extend(role_keywords)
    elif isinstance(custom_roles, list):
        for role_cfg in custom_roles:
            if isinstance(role_cfg, dict):
                role_keywords = role_cfg.get("keywords")
                if isinstance(role_keywords, list):
                    skills.extend(role_keywords)

    return _dedupe_skills([str(s) for s in skills])


@dataclass
class CandidateProfile:
    """Complete candidate profile from Master Data"""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    primary_role: str = ""
    education: str = ""
    skills: list[str] = field(default_factory=list)
    categorized_skills: dict[str, list[str]] = field(default_factory=dict)
    experience: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    master_template: dict = field(default_factory=dict)  # NEW: Template from master resume
    full_text: str = ""

    @classmethod
    def from_mongo(cls, data: dict) -> 'CandidateProfile':
        """Hydrate from MongoDB document"""
        links = data.get("links", {})
        skills = _extract_skills_from_mongo(data)
        
        return cls(
            full_name=data.get("full_name") or data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            location=data.get("location", ""),
            linkedin=links.get("linkedin") if isinstance(links, dict) else data.get("linkedin", ""),
            github=links.get("github") if isinstance(links, dict) else data.get("github", ""),
            portfolio=links.get("portfolio") if isinstance(links, dict) else data.get("portfolio", ""),
            primary_role=data.get("primary_role", ""),
            education=data.get("education", ""),
            skills=skills,
            categorized_skills=data.get("categorized_skills", {}),
            experience=data.get("experience", []),
            projects=data.get("projects", []),
            master_template=data.get("master_template", {}),
            full_text=data.get("full_text", ""),
        )


@dataclass 
class RoleResume:
    """Complete resume for a specific role"""
    role_key: str
    role_title: str
    file_path: str
    summary: str
    skills: dict
    experience: list[dict]
    projects: list[dict]
    contact_info: dict
    education: str
    created_at: float = 0
    
    def to_dict(self) -> dict:
        return {
            "role_key": self.role_key,
            "role_title": self.role_title,
            "file_path": self.file_path,
            "summary": self.summary,
            "skills": self.skills,
            "experience": self.experience,
            "projects": self.projects,
            "contact_info": self.contact_info,
            "education": self.education,
            "created_at": self.created_at,
        }


# ── Shared LLM singleton ────────────────────────────────────────────────────
_shared_llm = None

def _get_llm():
    """Return a single shared LLM instance (no repeated RAGEngine init)."""
    global _shared_llm
    if _shared_llm is None:
        from .rag_engine import RAGEngine
        _engine = RAGEngine()
        _shared_llm = _engine.llm
    return _shared_llm


class RAGResumeGenerator:
    """
    Generates role resumes using Master Profile (MongoDB) + AI Tailoring.
    Stage 1: Multi-Role Base (Pre-generated)
    Stage 2: Job-Specific Polishing (On-the-fly)
    """
    
    def __init__(self, logger: Any = None, student_id: str = "default"):
        self.logger = logger
        self.student_id = student_id
        self.rag_engine = None
        self.profile: Optional[CandidateProfile] = None
        self.custom_roles: dict = {}
        self.generated_resumes: dict[str, RoleResume] = {}
        self.full_text: str = ""  # Store raw text to prevent data loss
        self._initialized = False
        
        # Student-specific resume directory
        self.resumes_dir = RESUMES_DIR / student_id
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
        
        # Parallel generation settings
        self._max_concurrent = max(1, int(os.getenv("RESUME_BATCH_SIZE", 3)))
        self._pdf_semaphore = asyncio.Semaphore(self._max_concurrent)
        self._shared_browser = None
        self._playwright = None
        
    def hydrate_from_db(self, student_doc: dict):
        """Pre-populate profile from existing MongoDB data"""
        self.profile = CandidateProfile.from_mongo(student_doc)
        
        # Load discovered roles if they exist
        self.custom_roles = student_doc.get("custom_roles", {})
        if self.custom_roles:
            print(f"  [HYDRATE] Loaded {len(self.custom_roles)} Discovered Roles")
        
        self.full_text = student_doc.get("full_text", "")
        if self.full_text:
            print(f"  [HYDRATE] Loaded raw resume text ({len(self.full_text)} chars)")
            
        print(f"  [HYDRATE] Loaded {self.profile.full_name} from MongoDB (Skills: {len(self.profile.skills)})")
        
        # NEW: Automatically check for existing resumes in student folder
        self._sync_generated_resumes_from_disk()

    def _sync_generated_resumes_from_disk(self):
        """Check the student's resume directory and populate generated_resumes cache."""
        if not self.custom_roles:
            return
            
        found_count = 0
        if isinstance(self.custom_roles, dict):
            roles_iter = self.custom_roles.items()
        elif isinstance(self.custom_roles, list):
            # Convert list of dicts with 'role_key' to items-like iterator
            roles_iter = []
            for item in self.custom_roles:
                if isinstance(item, dict):
                    rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                    roles_iter.append((rk, item))
        else:
            return

        for key, cfg in roles_iter:
            title = cfg.get("title", "")
            if not title: continue
            
            # Variant 1: Based on role_key (e.g., aws_cloud.pdf)
            safe_key = key.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
            # Variant 2: Based on role_title (e.g., aws_cloud_engineer.pdf)
            safe_title = title.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
            
            paths_to_check = [
                self.resumes_dir / f"{safe_key}.pdf",
                self.resumes_dir / f"{safe_title}.pdf"
            ]
            
            for target_path in paths_to_check:
                if target_path.exists() and target_path.stat().st_size > 1000:
                    if key not in self.generated_resumes:
                        self.generated_resumes[key] = RoleResume(
                            role_key=key,
                            role_title=title,
                            file_path=str(target_path),
                            summary=cfg.get("summary", ""),
                            skills={},
                            experience=[],
                            projects=[],
                            contact_info={},
                            education=""
                        )
                        found_count += 1
                        break # Found one variant, move to next role
        
        if found_count > 0:
            print(f"  [SYNC] Found {found_count} existing resumes in {self.resumes_dir}")

    async def discover_top_roles(self) -> dict:
        """Analyze Master Profile to discover the top 6 professional roles."""
        if not self.profile:
            await self._init_rag()
            
        print("\n  [DISCOVERY] Calling LLM to identify best roles from Master Resume...")
        llm = _get_llm()
        
        prompt = f"""
        STRICT RULES:
        - Roles MUST follow the naming convention of 'Primary Skill Developer' (e.g., 'Java Developer', 'Python Developer', 'React Developer', 'Node.js Developer').
        - Do NOT use project names (e.g., 'Hospital Management System') as role titles.
        - Do NOT use generic titles like 'Backend Developer' if a more specific tech-based title like 'Node.js Developer' is possible.
        - Each of the 6 roles MUST focus on a distinct primary technology from the skills list to ensure variety.
        
        Candidate Technical Skills: {", ".join(self.profile.skills)}
        Full Resume Text (Reference only for context):
        {self.full_text[:5000]}
        
        Return valid JSON where keys are the lowercase role keys and values contain the title and keywords:
        {{
            "java_backend": {{ "title": "Java Backend Developer", "keywords": ["Java", "Spring Boot"...] }},
            "react_frontend": {{ "title": "React Frontend Developer", "keywords": ["React", "Redux"...] }},
            ... (6 roles total)
        }}
        """
        
        result = await llm.async_generate_json(
            prompt, 
            system="You are a senior career consultant. Identify 6 accurate technical roles based on candidate's background. Return ONLY JSON.",
            temperature=0.2
        )
        
        if result:
            self.custom_roles = result
            print(f"  [DISCOVERY] Success! Found 6 roles: {', '.join(self.custom_roles.keys())}")
            
            # Save to MongoDB
            from utils.student_mongodb import get_mongo_connection
            client = get_mongo_connection()
            if client:
                db = client["ai_bot_resumes"]
                db["students"].update_one(
                    {"student_id": self.student_id},
                    {"$set": {
                        "custom_roles": self.custom_roles,
                        "full_text": self.full_text
                    }}
                )
            
            return self.custom_roles
        return {}

    async def _init_rag(self, file_path: str = "", force_reindex: bool = False, force_extract: bool = False):
        """Initialize RAG engine and extract profile from resume file.
        
        Args:
            file_path: Path to resume file
            force_reindex: Force re-indexing even if already done
            force_extract: If True, force re-extraction from AI even if profile exists in DB
        """
        if self._initialized and not force_reindex and not force_extract:
            return
            
        try:
            # Try to download resume from Cloudinary if not provided locally
            if not file_path or not os.path.exists(file_path):
                from utils.student_mongodb import get_student_resume_url
                resume_url = get_student_resume_url(self.student_id)
                if resume_url:
                    from utils.resume_downloader import download_if_needed
                    try:
                        print(f"  [DOWNLOAD] Downloading resume from URL: {resume_url}")
                        downloaded_path = download_if_needed(resume_url, self.student_id)
                        if downloaded_path and os.path.exists(downloaded_path):
                            file_path = downloaded_path
                    except Exception as e:
                        print(f"  [ERROR] Failed to download resume: {e}")

            from utils.pdf_reader import extract_text_from_pdf
            
            # 1. Extract text from resume file (always do this)
            text_content = ""
            if file_path and os.path.exists(file_path):
                # Smart Format Detection: check file signature, not extension
                with open(file_path, "rb") as f:
                    header = f.read(10)
                
                if header.startswith(b"%PDF"):
                    print("  [FORMAT] Detected PDF signature")
                    text_content = extract_text_from_pdf(file_path)
                elif header.startswith(b"PK"):
                    print("  [FORMAT] Detected DOCX signature")
                    import mammoth
                    with open(file_path, "rb") as f:
                        text_content = mammoth.extract_raw_text(f).value
                else:
                    print("  [FORMAT] Detected plain text")
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
            
            self.full_text = text_content
            print(f"  [TEXT] Extracted {len(self.full_text)} chars from resume")
            
            # 2. Resolve Profile
            # Try to get profile from MongoDB first if not already loaded
            if not self.profile:
                from utils.student_mongodb import get_student_by_id
                student_doc = get_student_by_id(self.student_id)
                if student_doc:
                    self.profile = CandidateProfile.from_mongo(student_doc)
                    if not self.full_text and 'full_text' in student_doc:
                        self.full_text = student_doc['full_text']
                        print(f"  [DB] Loaded full_text from MongoDB ({len(self.full_text)} chars)")
            
            # Check if we need to force re-extract due to missing critical fields or force_extract
            needs_extraction = False
            if force_extract:
                needs_extraction = True
            elif not self.profile:
                needs_extraction = True
            else:
                # Check for missing critical data
                missing_fields = []
                if not self.profile.skills:
                    missing_fields.append("skills")
                if not self.profile.education:
                    missing_fields.append("education")
                if not self.profile.experience and not self.profile.projects:
                    missing_fields.append("experience/projects")
                if not self.full_text:
                    missing_fields.append("full_text")
                
                if missing_fields:
                    print(f"  [CHECK] Profile is missing critical fields: {', '.join(missing_fields)}. Triggering re-extraction...")
                    needs_extraction = True

            if needs_extraction and text_content:
                print(f"  [SIMPLE] Extracting profile from {len(text_content)} chars...")
                self.profile = await self._parse_profile_from_context(text_content)
                
                # Sync the newly extracted profile back to MongoDB
                if self.profile and self.profile.skills:
                    from utils.student_mongodb import update_student_profile
                    from dataclasses import asdict
                    profile_dict = asdict(self.profile)
                    
                    # Also get master template if it exists in db
                    from utils.student_mongodb import get_student_by_id
                    student_doc = get_student_by_id(self.student_id)
                    if student_doc and 'master_template' in student_doc:
                        profile_dict['master_template'] = student_doc['master_template']
                        
                    update_student_profile(self.student_id, profile_dict)
                    print("  [DB] Updated student profile in MongoDB with extracted data")
            
            self._initialized = True
        except Exception as e:
            print(f"  [ERROR] RAG init error: {e}")
            import traceback
            traceback.print_exc()
            if not self.profile:
                self.profile = CandidateProfile()
            self._initialized = True
    
    async def _parse_profile_from_context(self, context: str) -> CandidateProfile:
        """Deep Parse complete profile from RAG context."""
        try:
            llm = _get_llm()

            prompt = f"""
            Extract a complete professional profile from this resume.

            CRITICAL REQUIREMENTS:
            1. You MUST extract ALL experience entries - look for job titles, company names, durations
            2. You MUST extract ALL projects - look for project names, tech stacks, descriptions
            3. Do NOT return empty arrays if data exists in the resume
            4. Look for sections like: INTERNSHIPS, PROJECTS, WORK EXPERIENCE, EMPLOYMENT

            REQUIRED JSON keys (all must be populated):
            - full_name
            - email
            - phone
            - location
            - linkedin
            - github
            - portfolio
            - primary_role
            - education
            - skills (flat array of all technical skills)
            - categorized_skills (grouped by category)
            - experience: ARRAY of {{"title": job title, "company": company, "duration": dates, "bullets": [list of bullet points]}}
            - projects: ARRAY of {{"name": project name, "tech": tech stack, "bullets": [list of bullet points]}}

            Resume Text:
            {context[:15000]}
            """
            
            result = await llm.async_generate_json(
                prompt, 
                system="You are a meticulous resume parser. Extract EVERY detail. Return ONLY JSON.", 
                temperature=0.1
            )
            
            if result:
                profile = CandidateProfile(
                    full_name=result.get("full_name", ""),
                    email=result.get("email", ""),
                    phone=result.get("phone", ""),
                    location=result.get("location", ""),
                    linkedin=result.get("linkedin", ""),
                    github=result.get("github", ""),
                    portfolio=result.get("portfolio", ""),
                    primary_role=result.get("primary_role", ""),
                    education=result.get("education", ""),
                    skills=result.get("skills", []),
                    categorized_skills=result.get("categorized_skills", {}),
                    experience=result.get("experience", []),
                    projects=result.get("projects", []),
                    full_text=context,
                )
                print(f"  [PROFILE] Extracted: {profile.full_name} | Skills: {len(profile.skills)}")
                return profile
        except Exception as e:
            print(f"  [ERROR] Profile parse error: {e}")
        return CandidateProfile()
    
    async def _generate_summary(self, role_title: str, jd_skills: list[str] = None, jd_context: str = "") -> str:
        """Generate high-impact tailored summary (MINIMUM 45 words with strong verbs)."""
        try:
            llm = _get_llm()
            candidate_skills = self.profile.skills if self.profile else []
            valid_skills = [s for s in (jd_skills or []) if any(cs.lower() == s.lower() for cs in candidate_skills)]
            valid_skills = valid_skills[:5] if valid_skills else candidate_skills[:5]
            skills_str = ', '.join(valid_skills)
            
            # 1. Check if fresher (no professional experience or experience has only internships)
            is_fresher = True
            if self.profile and self.profile.experience:
                has_job = False
                for exp in self.profile.experience:
                    title = exp.get("title", "").lower()
                    company = exp.get("company", "").lower()
                    bullets = " ".join(exp.get("bullets", [])).lower()
                    if "intern" not in title and "intern" not in company and "intern" not in bullets:
                        has_job = True
                        break
                if has_job:
                    is_fresher = False

            # 2. Build detailed description of experience/internships/projects
            exp_text = ""
            if self.profile and self.profile.experience:
                for exp in self.profile.experience[:3]:
                    title = exp.get("title", "")
                    company = exp.get("company", "")
                    bullets = exp.get("bullets", [])
                    # Classify if internship
                    is_intern = any(w in title.lower() or w in company.lower() or any(w in b.lower() for b in bullets) for w in ["intern", "trainee"])
                    role_type = "Internship" if is_intern else "Professional Role"
                    bullets_summary = "; ".join(bullets[:2]) if bullets else "hands-on implementation"
                    exp_text += f"- {role_type}: {title} at {company} (Key achievements: {bullets_summary}). "
            
            # If candidate is a fresher or has no experience, also append academic/personal projects
            if (is_fresher or not exp_text) and self.profile and self.profile.projects:
                for proj in self.profile.projects[:2]:
                    title = proj.get("title", "Project")
                    bullets = proj.get("bullets", [])
                    bullets_summary = "; ".join(bullets[:2]) if bullets else "hands-on application development"
                    exp_text += f"- Academic/Personal Project: {title} (Key achievements: {bullets_summary}). "
            
            # Get random sample of verbs for dynamic variety
            import random
            sample_verbs = random.sample(ACTION_VERBS[:50], min(10, 50))
            verbs_str = ", ".join(sample_verbs)

            if is_fresher:
                fresher_guidelines = (
                    "- The candidate is a FRESHER / ENTRY-LEVEL developer.\n"
                    "- Focus on academic projects, internships, hands-on coding, and foundational engineering.\n"
                    "- Highlight enthusiasm for clean code, learning agility, and contributing to development cycles.\n"
                    "- DO NOT use any management, executive, or seasoned phrasing."
                )
            else:
                fresher_guidelines = (
                    "- Focus on professional software engineering achievements, system design, and production delivery.\n"
                    "- Highlight professional impact, business value, and application lifecycle ownership."
                )

            prompt = (
                f"Locate the candidate's original 'Professional Summary', 'Summary', or 'Objective' in the Background text below.\n"
                f"Rewrite and tailor that original summary specifically for a {role_title} role. If no original summary exists, write a new one based on the Background.\n"
                f"STRICT RULES:\n"
                f"- Return ONLY the final rewritten summary paragraph. No preambles, no labels, no original text.\n"
                f"- MUST be exactly 45 words long.\n"
                f"- Use STRONG, ATS-optimized action verbs from this list: {verbs_str}\n"
                f"- Include skills: {skills_str}\n"
                f"- Explicitly mention candidate's 'internship' or 'experience'.\n"
                f"- Explicitly highlight 'enthusiasm for clean code' and 'learning agility'.\n"
                f"- NO 'years', 'experienced', 'seasoned', or tenure references.\n"
                f"- NO generic phrases like 'Dedicated professional'.\n"
                f"{fresher_guidelines}\n"
                f"- Focus on technical impact, achievements, and quantifiable results.\n"
                f"Background: {self.full_text[:3000]}\n"
            )
            summary = await llm.async_generate(prompt, system="Write a dynamic, high-impact summary of exactly 45 words. Focus on technical achievements and satisfy every rule.", temperature=0.3)
            
            summary = summary.strip()
            words = summary.split()
            
            # If the summary is not close to 45 words, adjust it dynamically
            if len(words) < 42 or len(words) > 48:
                print(f"  [SUMMARY] Summary length ({len(words)} words) is not close to 45 words. Adjusting dynamically...")
                adjust_prompt = (
                    f"Rewrite this professional summary to be exactly 45 words long.\n"
                    f"You MUST satisfy every one of these rules:\n"
                    f"1. Exactly 45 words long.\n"
                    f"2. Explicitly mention the internship/experience.\n"
                    f"3. Include skills: {skills_str}.\n"
                    f"4. Explicitly highlight enthusiasm for clean code and learning agility.\n"
                    f"Do not use generic filler text.\n\n"
                    f"Current summary: {summary}"
                )
                adjusted = await llm.async_generate(adjust_prompt, system="Rewrite the summary to be exactly 45 words long satisfying all criteria.", temperature=0.3)
                if adjusted:
                    adjusted_words = adjusted.strip().split()
                    if 40 <= len(adjusted_words) <= 50:
                        summary = adjusted.strip()
            
            return summary
        except Exception as e:
            print(f"  [WARN] Summary generation failed: {e}")
            skills_part = f" specializing in {skills_str}" if skills_str else ""
            fallback = (
                f"Highly motivated and result-oriented {role_title}{skills_part}. "
                f"Possesses a strong foundation in modern software engineering principles and hands-on experience "
                f"developing robust, efficient applications. Committed to collaborating with cross-functional "
                f"teams to build and deploy high-quality solutions while continuously expanding technical expertise."
            )
            return fallback

    async def _polish_bullets_async(self, original_bullets: list[str], role_title: str, jd_context: str) -> list[str]:
        """Polish bullets — ONLY rephrase words/verbs, NEVER change actual data from master resume."""
        if not original_bullets:
            return original_bullets
        
        try:
            llm = _get_llm()
            
            # Take exactly 3 bullets
            bullets_to_polish = original_bullets[:3] if len(original_bullets) >= 3 else original_bullets
            bullets_text = "\n".join([f"- {b}" for b in bullets_to_polish])
            
            # Get unique verbs for each bullet - ensure no duplicates
            import random
            unique_verbs = random.sample(ACTION_VERBS, min(3, len(ACTION_VERBS)))
            verbs_str = ", ".join(unique_verbs)
            
            # Get more verbs for the LLM to choose from (exclude the 3 already selected)
            remaining_verbs = [v for v in ACTION_VERBS if v not in unique_verbs]
            all_verbs = ", ".join(random.sample(remaining_verbs, min(27, len(remaining_verbs))))
            
            prompt = (
                f"Rephrase these resume bullet points with stronger ATS-optimized action verbs.\n\n"
                f"CRITICAL: Keep ALL original technical skills, tools, and data exactly the same.\n"
                f"RULES - MANDATORY:\n"
                f"1. Keep ALL original technical skills, tools, company names unchanged.\n"
                f"2. Each bullet MUST start with a UNIQUE verb - NO VERB REPEATS across any bullet.\n"
                f"3. Use these specific verbs as starting points (one each): {verbs_str}\n"
                f"4. If you need more verbs, use ONLY from: {all_verbs}\n"
                f"5. Each bullet MUST be exactly 12 words for ATS optimization.\n"
                f"6. Add quantifiable metrics where plausible based ONLY on existing facts.\n"
                f"7. Return each bullet starting with '- ' and ending with period.\n"
                f"8. VERIFY: Before returning, ensure no verb is repeated as the first word.\n\n"
                f"Original bullets:\n{bullets_text}\n\n"
                f"Example:\n"
                f"Original: Developed REST APIs.\n"
                f"Polished: Architected RESTful APIs using Python Flask and Docker, reducing latency by 40%.\n"
            )
            result = await llm.async_generate(
                prompt,
                system="You are a resume editor Expert. Transform bullet points with unique action verbs and measurable impact. NEVER add new skills - only enhance existing ones.",
                temperature=0.2,
                max_tokens=800
            )
            
            # Parse bullets
            polished = [line.strip("- ").strip() for line in result.split("\n") if line.strip().startswith("-")]
            
            # Ensure exactly 3 bullets
            if len(polished) >= 3:
                polished = polished[:3]
            else:
                while len(polished) < 3:
                    polished.append(bullets_to_polish[len(polished)])
            
            # ENFORCE UNIQUE VERBS: Check first word of each bullet and ensure no repeats
            used_verbs = set()
            unique_polished = []
            for bullet in polished:
                first_word = bullet.split()[0] if bullet.split() else ""
                # If verb already used or not in our verb list, replace with unique verb
                if first_word in used_verbs or first_word not in ACTION_VERBS:
                    # Get a fresh verb not used yet
                    available_verbs = [v for v in ACTION_VERBS if v not in used_verbs]
                    if available_verbs:
                        replacement_verb = random.choice(available_verbs)
                        used_verbs.add(replacement_verb)
                        # Replace first word
                        words = bullet.split()
                        if words:
                            words[0] = replacement_verb
                            unique_polished.append(" ".join(words))
                        else:
                            unique_polished.append(bullet)
                    else:
                        unique_polished.append(bullet)
                else:
                    used_verbs.add(first_word)
                    unique_polished.append(bullet)
            polished = unique_polished
            
            # FORCE exactly 12 words per bullet
            validated_bullets = []
            for i, bullet in enumerate(polished):
                words = bullet.strip().rstrip('.').split()
                
                # Get original bullet words as fallback
                orig_words = original_bullets[i].split() if i < len(original_bullets) else original_bullets[0].split()
                
                # Use polished if exactly 12 words, otherwise use original
                if len(words) == 12:
                    final_words = words
                elif len(words) > 12:
                    final_words = words[:12]
                else:
                    final_words = orig_words[:12]
                
                # Finalize with period
                final = " ".join(final_words)
                if not final.endswith('.'):
                    final = final + "."
                
                validated_bullets.append(final)
            
            return validated_bullets
        except Exception as e:
            print(f"  [WARN] Bullet polish failed: {e}")
            return original_bullets[:3] if len(original_bullets) >= 3 else original_bullets
    
    async def _generate_role_resume(self, role_key: str, role_title: str) -> RoleResume:
        """Generate a tailored resume for a core role and save PDF."""
        if not self.profile:
            await self._init_rag()
            
        # Get keywords from custom_roles if available, else use skills
        # Support both list and dict formats for custom_roles
        role_info = {}
        if isinstance(self.custom_roles, dict):
            role_info = self.custom_roles.get(role_key, {})
        elif isinstance(self.custom_roles, list):
            for item in self.custom_roles:
                if isinstance(item, dict) and (item.get("role_key") == role_key or item.get("title") == role_title):
                    role_info = item
                    break
        
        keywords = role_info.get("keywords", self.profile.skills if self.profile else []) if isinstance(role_info, dict) else (self.profile.skills if self.profile else [])
        
        print(f"\n  --- Generating: {role_title} ---")
        
        # 1. AI Tailored Summary
        print(f"    [1] Generating summary...")
        summary = await self._generate_summary(role_title, keywords)
        
        # 2. AI Polished Experience & Projects
        print(f"    [2] Polishing experience bullets...")
        jd_mock = f"Role: {role_title}. Keywords: {', '.join(keywords)}"
        
        tailored_exp = []
        for exp in self.profile.experience:
            polished = await self._polish_bullets_async(exp.get("bullets", []), role_title, jd_mock)
            tailored_exp.append({**exp, "bullets": polished})
            
        print(f"    [3] Polishing project bullets...")
        tailored_proj = []
        for proj in self.profile.projects:
            polished = await self._polish_bullets_async(proj.get("bullets", []), role_title, jd_mock)
            tailored_proj.append({**proj, "bullets": polished})

        # 3. Prepare target path - use role-based filename only
        safe_role = role_title.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
        file_name = f"{safe_role}.pdf"
        target_path = self.resumes_dir / file_name
        
        # 4. Trigger AI Engine for PDF generation
        print(f"    [4] API: Requested PDF generation for {role_title}...")
        try:
            import httpx
            import shutil
            
            # Construct "Synthetic Master Context" from the MongoDB profile
            context_str = f"Name: {self.profile.full_name}\nRole: {role_title}\n"
            context_str += f"Email: {self.profile.email}\nPhone: {self.profile.phone}\n"
            context_str += f"LinkedIn: {self.profile.linkedin}\nGitHub: {self.profile.github}\n"
            context_str += f"Location: {self.profile.location}\n"
            context_str += f"Education: {self.profile.education}\n"
            context_str += f"Professional Summary: {summary}\n"
            context_str += f"Skills: {', '.join(self.profile.skills)}\n"
            context_str += "Experience:\n" + json.dumps(tailored_exp, indent=2) + "\n"
            context_str += "Projects:\n" + json.dumps(tailored_proj, indent=2)
            
            # Get master_template from profile
            master_template = getattr(self.profile, 'master_template', None) or {}
            
            api_payload = {
                "retrievedChunks": context_str,
                "jobDescription": f"Job Title: {role_title}\nFocus Skills: {', '.join(keywords)}",
                "disableCache": False,
                "refreshCache": True,
                "student_id": self.student_id,
                "master_template": master_template,
                "summary": summary
            }
            
            api_url = os.environ.get("LOCAL_API_URL", "http://ai-engine:8000")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_url}/generate",
                    json=api_payload,
                    timeout=httpx.Timeout(300.0)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated_path = resolve_ai_engine_pdf_path(result)
                    generated_content = str(generated_path) if generated_path else result.get("resumeText")
                    
                    if generated_content and generated_content.startswith("<"):
                        with open(target_path, 'w', encoding='utf-8') as f:
                            f.write(generated_content)
                        print(f"    [OK] Saved HTML to: {target_path}")
                    elif generated_content and os.path.exists(generated_content):
                        import time
                        time.sleep(2)
                        if os.path.abspath(generated_content) != os.path.abspath(target_path):
                            shutil.copy2(generated_content, target_path)
                            print(f"    [OK] Saved PDF (copied from {generated_content})")
                        else:
                            print(f"    [OK] Saved PDF (already at target: {target_path})")
                    else:
                        print(f"    [WARN] No content generated")
                else:
                    print(f"    [ERROR] PDF API failed ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"    [ERROR] PDF generation error: {e}")

        # 5. Return Metadata
        return RoleResume(
            role_key=role_key,
            role_title=role_title,
            file_path=str(target_path),
            summary=summary,
            skills=self.profile.categorized_skills if self.profile.categorized_skills else {"Skills": self.profile.skills},
            experience=tailored_exp,
            projects=tailored_proj,
            contact_info={
                "email": self.profile.email,
                "phone": self.profile.phone,
                "linkedin": self.profile.linkedin,
                "github": self.profile.github
            },
            education=self.profile.education,
            created_at=asyncio.get_event_loop().time()
        )
    
    async def generate_initial_resumes(self) -> dict[str, RoleResume]:
        """Discover and pre-generate the top 6 core resumes - PARALLELIZED."""
        if not self.profile:
            await self._init_rag()
            
        # Discover roles if self.custom_roles is empty
        if not self.custom_roles:
            await self.discover_top_roles()
        
        # Prepare tasks for parallel generation
        async def generate_role_safe(key: str, cfg: dict) -> tuple[str, RoleResume]:
            async with self._pdf_semaphore:
                safe_role = key.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
                target_path = self.resumes_dir / f"{safe_role}.pdf"
                
                print(f"  [GENERATING] {key} (FORCED)...")
                result = await self._generate_role_resume(key, cfg["title"])
                return key, result
        
        # Prepare tasks for parallel generation
        if isinstance(self.custom_roles, dict):
            roles_items = self.custom_roles.items()
        elif isinstance(self.custom_roles, list):
            roles_items = []
            for item in self.custom_roles:
                if isinstance(item, dict):
                    rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                    roles_items.append((rk, item))
                else:
                    # Skip non-dict items in the list
                    continue
        else:
            return {}

        tasks = []
        for k, c in roles_items:
            # Skip if already exists in generated_resumes (synced from disk)
            if k in self.generated_resumes:
                continue
            tasks.append(generate_role_safe(k, c))
            
        if not tasks:
            return self.generated_resumes

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for item in results:
            if isinstance(item, Exception):
                print(f"  [ERROR] {item}")
            elif item:
                key, resume = item
                self.generated_resumes[key] = resume
        
        return self.generated_resumes
    
    async def get_resume_for_role(self, role_key: str, role_title: str = "") -> RoleResume:
        """Fetch pre-generated base resume or dynamically generate if missing."""
        if not self.generated_resumes:
            await self.generate_initial_resumes()
            
        if role_key in self.generated_resumes:
            return self.generated_resumes[role_key]
            
        target_title = role_title or role_key.replace("_", " ").title()
        print(f"  [DYNAMIC] Role '{role_key}' not pre-generated. Generating completely new tailored resume from master data for '{target_title}'...")
        new_resume = await self._generate_role_resume(role_key, target_title)
        self.generated_resumes[role_key] = new_resume
        return new_resume
    
    async def get_tailed_resume(self, job_description: str, company: str = "") -> tuple[RoleResume, dict]:
        """Deep AI-Tailoring lifecycle: Role Title -> Summary -> Bullets"""
        if not self.profile:
            await self._init_rag()
        
        # A. Identity Extraction
        llm = _get_llm()
        role_title = await llm.async_generate(f"Extract job title from JD: {job_description[:300]}", system="Title only.", max_tokens=30)
        role_title = role_title.strip() or "Software Engineer"
        role_key = self._extract_role_from_jd(job_description)
        
        base_resume = await self.get_resume_for_role(role_key, role_title)
        jd_skills = self._extract_skills_from_jd(job_description)
        
        # B. Tailored Generation
        new_summary = await self._generate_summary(role_title, jd_skills, job_description)
        
        tailored_exp = []
        for exp in base_resume.experience:
            polished = await self._polish_bullets_async(exp.get("bullets", []), role_title, job_description)
            tailored_exp.append({**exp, "bullets": polished})
            
        tailored = RoleResume(
            role_key=role_key,
            role_title=role_title,
            file_path=base_resume.file_path,
            summary=new_summary,
            skills=base_resume.skills,
            experience=tailored_exp,
            projects=base_resume.projects,
            contact_info=base_resume.contact_info,
            education=base_resume.education,
            created_at=asyncio.get_event_loop().time()
        )
        
        return tailored, {"role_title": role_title, "company": company, "match_score": 0.9}

    def _extract_role_from_jd(self, jd: str) -> str:
        jd_lower = jd.lower()
        # Use custom roles if available
        roles_to_score = self.custom_roles if self.custom_roles else ROLE_CONFIGS
        if not roles_to_score:
            return "dynamic_role" 
            
        scores = {}
        if isinstance(roles_to_score, dict):
            for k, v in roles_to_score.items():
                keywords = v.get("keywords", [])
                scores[k] = sum(1 for kw in keywords if kw.lower() in jd_lower)
        elif isinstance(roles_to_score, list):
            for item in roles_to_score:
                if isinstance(item, dict):
                    rk = item.get("role_key") or item.get("title", "unknown").lower().replace(" ", "_")
                    keywords = item.get("keywords", [])
                    scores[rk] = sum(1 for kw in keywords if kw.lower() in jd_lower)
        
        if not scores:
            return "dynamic_role"
            
        best_role = max(scores, key=scores.get)
        return best_role if scores[best_role] > 0 else "dynamic_role"

    def _extract_skills_from_jd(self, jd: str) -> list[str]:
        tech_skills = ["React", "Python", "Java", "Docker", "AWS", "SQL", "TypeScript"]
        return [s for s in tech_skills if s.lower() in jd.lower()]


_generator = None
def get_rag_resume_generator(logger=None, student_id="default"):
    global _generator
    if not _generator or _generator.student_id != student_id:
        _generator = RAGResumeGenerator(logger, student_id)
        
        # Auto-hydrate if student exists in MongoDB
        try:
            from utils.student_mongodb import get_student_by_id
            student_doc = get_student_by_id(student_id)
            if student_doc:
                _generator.hydrate_from_db(student_doc)
        except Exception as e:
            if logger:
                logger.log_warn(f"Failed to auto-hydrate generator: {e}")
            else:
                print(f"  [WARN] Failed to auto-hydrate generator: {e}")
                
    return _generator

async def demo():
    gen = get_rag_resume_generator()
    res = await gen.get_tailed_resume("Cloud Engineer", "AWS")
    print(res[0].summary)

if __name__ == "__main__":
    asyncio.run(demo())
