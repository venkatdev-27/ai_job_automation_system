import logging
import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

IN_DOCKER = os.environ.get("IN_DOCKER", "").lower() == "true" or Path("/app/ai_engine").exists()
BASE_DIR = Path("/app") if IN_DOCKER else Path("d:/ai-bot-resumes")
CONTAINER_PROJECT_ROOT = os.getenv("CONTAINER_PROJECT_ROOT", "/app").replace("\\", "/").rstrip("/")
HOST_PROJECT_ROOT = os.getenv("HOST_PROJECT_ROOT", "D:/ai-bot-resumes").replace("\\", "/").rstrip("/")

from ai_engine.config import (
    SUMMARY_WORD_MIN, SUMMARY_WORD_MAX,
    LEGACY_FONT_FAMILY, LEGACY_BODY_FONT_SIZE_PT,
    LEGACY_NAME_FONT_SIZE_PT, LEGACY_SECTION_FONT_SIZE_PT,
    LEGACY_MARGIN_IN, LEGACY_LINE_HEIGHT, RESUME_OUTPUT_DIR
)
from ai_engine.utils.logging_setup import logger
from ai_engine.utils.text_processing import (
    clean_text, count_words, remove_empty_html_elements,
    strip_markdown_code_fences
)
from ai_engine.core.llm_client import groq_llm_call_with_fallback, parse_llm_json_response
from ai_engine.core.extractor import extract_source_profile, extract_target_company, detect_role_profile
from ai_engine.core.skill_engine import skill_engine
from ai_engine.core.validator import validate_resume_json
from ai_engine.core.pdf_generator import generate_pdf_sync
from ai_engine.core.rag_service import RAGService


def _resume_path_contract(pdf_path: str) -> Dict[str, str]:
    """Return host/container path variants without breaking legacy pdfPath clients."""
    normalized = str(pdf_path).replace("\\", "/")
    container_path = normalized if normalized.startswith(f"{CONTAINER_PROJECT_ROOT}/") else None
    host_path = normalized if re.match(r"^[A-Za-z]:/", normalized) else None

    if container_path and not host_path:
        host_path = f"{HOST_PROJECT_ROOT}{container_path[len(CONTAINER_PROJECT_ROOT):]}"
    elif host_path and not container_path:
        host_root_lower = HOST_PROJECT_ROOT.lower()
        if host_path.lower().startswith(f"{host_root_lower}/"):
            container_path = f"{CONTAINER_PROJECT_ROOT}{host_path[len(HOST_PROJECT_ROOT):]}"

    return {
        "pdfPath": container_path if IN_DOCKER and container_path else host_path or normalized,
        "containerPath": container_path or normalized,
        "hostPath": host_path or normalized,
    }


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

class ResumeOrchestrator:
    def __init__(self, settings: Any = None):
        self.settings = settings

    async def generate_resume_pipeline(self, retrieved_chunks: str, job_description: str, 
                                       student_id: str = None, master_template: Dict[str, Any] = None,
                                       summary: str = None) -> Dict[str, Any]:
        logger.info("Starting Dynamic Resume Generation Pipeline")
        
        # Store master template for use in template generation
        self.master_template = master_template
        self.student_id = student_id
        
        # Initialize RAG Service
        rag_service = RAGService.get_instance()
        # Prioritize raw master text for indexing if available
        index_text = master_template.get("text") if isinstance(master_template, dict) else None
        if not index_text:
            index_text = retrieved_chunks
            
        if student_id and index_text:
            rag_service.index_resume(index_text, student_id)
        
        # Enhance candidate data with RAG if possible
        if student_id and job_description:
            logger.info("Enriching context with RAG retrieval...")
            rag_context = await rag_service.retrieve_context(job_description, student_id)
            if rag_context:
                candidate_data = f"{retrieved_chunks}\n\n[RAG ENHANCED CONTEXT]\n{rag_context}"
            else:
                candidate_data = clean_text(retrieved_chunks)
        else:
            candidate_data = clean_text(retrieved_chunks)
        
        # v3 MASTER LOCKDOWN: Fetch original categories FIRST to avoid JD-suggested injections
        print("  [PHASE 0] Extracting Master Categories...")
        master_categories = await self._extract_master_categories_async(candidate_data)
        
        # 1. ANALYZE JOB DYNAMICALLY (Only if master categories are missing)
        import asyncio
        if not master_categories:
            logger.info("No master categories found. Triggering dynamic JD discovery strike.")
            role_task = self._analyze_job_dynamically(job_description)
        else:
            # Create a dummy task that returns the default role profile with master categories
            from ai_engine.core.extractor import detect_role_profile
            async def get_base():
                profile = detect_role_profile(job_description) # Keep the family/title detection
                profile["categories"] = master_categories
                return profile
            role_task = get_base()

        # Parallel setup
        print("  [PHASE 1] Extracting Profile & Keywords (Parallel)...")
        role_profile, source_profile, target_company, source_keywords, jd_keywords = await asyncio.gather(
            role_task, 
            asyncio.to_thread(extract_source_profile, candidate_data),
            asyncio.to_thread(extract_target_company, job_description),
            asyncio.to_thread(self._extract_dynamic_keywords, candidate_data),
            asyncio.to_thread(self._extract_dynamic_keywords, job_description)
        )
        
        # Override with master categories to be 100% sure
        final_categories = master_categories if master_categories else role_profile.get("categories", [])
        logger.info(f"Final Combined Strategy Categories: {final_categories}")

        # PHASE 1: Data Extraction & Polishing
        print("  [PHASE 2] Running Advanced Extraction & Sanitization...")
        extraction_results = await self._run_phase1(
            candidate_data, job_description, role_profile, source_profile, 
            target_company, source_keywords, jd_keywords
        )
        
        # Override LLM generated summary with explicit pre-generated summary if provided
        if summary:
            extraction_results["summary"] = summary
        
        # Map skills to categories dynamically using the SkillEngine (Parallel Harmonization)
        extraction_results["skills"] = await self._harmonize_skills_async(
            extraction_results.get("skills", {}),
            final_categories
        )
        # Save Skill Cache once at the end
        skill_engine._save_cache()
        
        # PHASE 2: HTML Generation
        print("  [PHASE 3] Generating Structured HTML...")
        resume_html = await self._run_phase2(extraction_results, role_profile, job_description)
        
        # PHASE 3: PDF Generation
        print("  [PHASE 4] Launching Browser for PDF Generation...")
        from ai_engine.core.pdf_generator import generate_pdf
        import uuid
        from ai_engine.config import get_student_resume_path
        # Clean role title for filename (e.g. "Java Backend Developer" -> "java_backend_developer.pdf")
        role_title = extraction_results.get("role_title", "Resume")
        safe_role_title = re.sub(r"\W+", "_", role_title).lower()
        pdf_filename = f"{safe_role_title}.pdf"

        if student_id:
            pdf_path_output = get_student_resume_path(student_id, pdf_filename)
        else:
            pdf_path_output = RESUME_OUTPUT_DIR / pdf_filename

        pdf_path = await generate_pdf(resume_html, str(pdf_path_output))
        try:
            with open(pdf_path_output.with_suffix(".html"), "w", encoding="utf-8") as f:
                f.write(resume_html)
        except Exception as html_err:
            logger.warning(f"Could not write debug HTML file: {html_err}")

        path_contract = _resume_path_contract(pdf_path)

        return {
            "success": True,
            "resumeText": resume_html,
            **path_contract,
            "fullName": extraction_results.get("full_name"),
            "roleFamily": role_profile.get("family"),
            "targetCompany": target_company,
            "score": 85,
            "createdAt": datetime.utcnow().isoformat()
        }

    async def _extract_master_categories_async(self, candidate_data: str) -> List[str]:
        """
        Uses LLM to surgically extract the actual category headers found in the candidate's master resume.
        """
        system_prompt = "You are an ATS parser. Extract all technical category headers (e.g., 'Programming Languages', 'Web Technologies') found in the provided resume text."
        prompt = f"Resume Content:\n{candidate_data}\n\nList all technical category headers exactly as they appear (one per line):"
        
        from ai_engine.core.llm_client import groq_llm_call_with_fallback_async
        res, _, _ = await groq_llm_call_with_fallback_async(prompt, system_prompt=system_prompt)
        if res:
            # v3 Sanitizer: Strip numbers (1.), bullets (*, -), and common prefixes
            import re
            lines = [line.strip() for line in res.split("\n") if line.strip()]
            clean_categories = []
            for line in lines:
                clean = re.sub(r"^\d+[\.\)]\s*", "", line) # Strip '1.' or '1)'
                clean = re.sub(r"^[\*\-\•]\s*", "", clean) # Strip bullets
                clean = clean.strip().rstrip(":")
                if clean and len(clean) < 40:
                    clean_categories.append(clean)
            return clean_categories
        return []

    async def _analyze_job_dynamically(self, job_description: str) -> Dict[str, Any]:
        """
        Uses LLM to discover the best ATS categories for the specific JD.
        """
        logger.info("Analyzing job dynamically to discover categories...")
        base_profile = detect_role_profile(job_description)
        
        system_prompt = "You are an ATS optimization expert. Analyze the job description and suggest 5-6 professional category headings for a technical resume skills section (e.g., 'Core Backend', 'Cloud Infrastructure', 'Specialized AI Tools')."
        prompt = f"Job Description:\n{job_description}\n\nSuggested Categories (comma separated):"
        
        from ai_engine.core.llm_client import groq_llm_call_with_fallback_async
        res, _, _ = await groq_llm_call_with_fallback_async(prompt, system_prompt=system_prompt)
        if res and isinstance(res, str):
            dynamic_categories = [c.strip() for c in res.split(",") if c.strip()]
            if len(dynamic_categories) >= 3:
                logger.info(f"Discovered dynamic categories: {dynamic_categories}")
                base_profile["categories"] = dynamic_categories
        
        return base_profile

    def _extract_dynamic_keywords(self, text: str) -> List[str]:
        # Simple extraction for now, can be improved with LLM
        # This just pulls words from the text to be categorized later
        words = re.findall(r"\b[A-Z][a-zA-Z0-9+#.]{2,}\b", text)
        return list(set(words))

    async def _harmonize_skills_async(self, raw_skills: Dict[str, List[str]], target_categories: List[str]) -> Dict[str, List[str]]:
        """v3 Optimization: Parallel Skill Categorization."""
        harmonized = {cat: [] for cat in target_categories}
        all_detected_skills = []
        
        if isinstance(raw_skills, dict):
            for skills in raw_skills.values():
                all_detected_skills.extend(skills)
        elif isinstance(raw_skills, list):
            all_detected_skills = raw_skills
            
        unique_skills = list(set(all_detected_skills))
        
        # Dispatch bounded parallel tasks so large skill sets do not burst LLM calls.
        import asyncio
        max_concurrency = max(1, int(os.getenv("LLM_SKILL_MAX_CONCURRENCY", os.getenv("LLM_MAX_CONCURRENCY", "4"))))
        semaphore = asyncio.Semaphore(max_concurrency)

        async def choose_category(skill: str) -> str:
            async with semaphore:
                return await skill_engine.async_choose_skill_category(skill, target_categories)

        tasks = [choose_category(s) for s in unique_skills]
        results = await asyncio.gather(*tasks)
        
        for skill, category in zip(unique_skills, results):
            harmonized[category].append(skill)
            
        return {k: v for k, v in harmonized.items() if v}

    def _harmonize_skills(self, raw_skills: Dict[str, List[str]], target_categories: List[str]) -> Dict[str, List[str]]:
        import asyncio
        return asyncio.run(self._harmonize_skills_async(raw_skills, target_categories))

    async def _run_phase1(self, candidate_data, job_info, role_profile, source_profile, target_company, source_skills, jd_skills):
        logger.info("Running Phase 1: Data Extraction & Polishing")
        
        role_brand = role_profile.get("id", "Software Developer").replace("_", " ").title()
        category_lines = "\n".join([f"- {label}" for label in role_profile.get("categories", [])])
        
        extractor_system = f"""STRICT RULES (ATS OPTIMIZATION & 100% FACTUAL MIRRORING):
1. DATA MIRROR: Transfer 100% of technical facts, tools, and project details ONLY from the CANDIDATE DATA.
2. IMPROVE BUT MIRROR: Rephrase the project/experience bullet points to be more high-impact and result-oriented (Action Verb + Task + Result).
3. ZERO HALLUCINATION: You are strictly forbidden from adding new skills, tools, or projects. Improve the FLOW, but keep the FACTS 100% identical to the source.
4. TOTAL DATA RETENTION: Include every project and every work experience entry found in the data. Do not omit any.
5. BULLET PARITY: Maintain the original count of bullets. If a project has 5 bullets, return 5 improved bullets.
6. NO JD INJECTION: DO NOT include tech stacks from the JOB DESCRIPTION that are not present in the CANDIDATE DATA. If a skill is in the JD but not the candidate data, IGNORE it.
7. SUMMARY PRESERVATION: If 'Professional Summary:' is present in the CANDIDATE DATA, you MUST extract and output that exact text verbatim in the 'summary' key of your JSON. Do NOT summarize or change it.
8. DATA INTEGRITY: Use ONLY information found in the CANDIDATE DATA or RAG ENHANCED CONTEXT. 
9. ABSOLUTE JSON: Return only valid JSON. No preamble. No comments."""

        prompt = f"""
EXTRACT JSON from the following:
CANDIDATE DATA: {candidate_data}
JOB DESCRIPTION: {job_info}
ROLE CATEGORIES: {category_lines}
TARGET COMPANY: {target_company}

REQUIREMENT: Capture every single project and experience entry from the CANDIDATE DATA verbatim. Return empty lists [] only if the data is genuinely missing.

OUTPUT JSON SCHEMA:
{{
  "full_name": "...",
  "role_title": "...",
  "location": "City, Country",
  "contact": "Email | Phone",
  "links": ["LinkedIn URL", "GitHub URL", ...],
  "summary": "...",
  "education": [{{ "degree": "...", "institution": "...", "date": "..." }}],
  "skills": ["ALL tools from candidate data", ...],
  "experience": [{{ "title": "...", "company": "...", "date": "...", "bullets": ["...", ...] }}],
  "projects": [{{ "title": "...", "tech_stack": "...", "bullets": ["...", ...] }}]
}}
"""
        from ai_engine.core.llm_client import groq_llm_call_with_fallback_async
        res, _, _ = await groq_llm_call_with_fallback_async(prompt, system_prompt=extractor_system)
        if not res:
            raise Exception("Phase 1 LLM call failed")
            
        print(f"DEBUG_STRIKE - PHASE 1 RAW RESPONSE Snippet (First 500 chars): {res[:500]}...")
        res_json = parse_llm_json_response(res)
        
        # v3 ABSOLUTE FACT-SLAVE FILTER: Programmatically remove any skill injected from the JD
        # We use regex word boundaries to prevent substring matches (e.g., 'S3' matching 'CSS3')
        import re
        raw_master = candidate_data.lower()
        if "skills" in res_json and isinstance(res_json["skills"], list):
            clean_skills = []
            for skill in res_json["skills"]:
                # Escape skill to handle special chars (+, ., etc.)
                pattern = rf"\b{re.escape(str(skill).lower())}\b"
                if re.search(pattern, raw_master):
                    clean_skills.append(skill)
                else:
                    logger.warning(f"HALLUCINATION STRIKE: Surgically removed injected skill '{skill}'")
            res_json["skills"] = clean_skills

        # v3 UI Armor: Ensure name/contact/location are NOT empty
        if not res_json.get("full_name"):
            res_json["full_name"] = source_profile.get("name", "Candidate Name")
        if not res_json.get("contact"):
             res_json["contact"] = f"{source_profile.get('email', '')} | {source_profile.get('phone', '')}"
        if not res_json.get("location"):
             res_json["location"] = source_profile.get("location", "Hyderabad, India")
             
        # v3 MANDATORY SUMMARY: If empty, use a default high-impact expansion and logs
        if not res_json.get("summary") or len(res_json.get("summary", "").split()) < 10:
            logger.warning("Empty summary detected! Triggering mandatory expansion strike.")
            res_json["summary"] = f"Results-driven {role_brand} with deep expertise in the tools extracted from the master resume. Committed to high-precision software delivery and technical excellence."

        await asyncio.to_thread(_write_text_file, BASE_DIR / "raw_llm_response_ph1.txt", res)
        return res_json

    async def _run_phase2(self, extraction_results, role_profile, job_info):
        logger.info("Running Phase 2: HTML Generation")
        
        category_order = " -> ".join(role_profile.get("categories", []))
        architect_system = f"""STRICT RULES FOR RESUME FORMAT - COPY FROM MASTER RESUME EXACTLY:

1. SECTION HEADERS: LEFT-ALIGNED with uppercase and FULL-WIDTH underline border
   - Use: <h2 style="text-align: left; text-transform: uppercase; border-bottom: 1.5px solid #111;">SECTION NAME</h2>

2. PROFESSIONAL SUMMARY - USE THE EXACT TEXT FROM THE "summary" FIELD OF THE INPUT JSON VERBATIM:
   - Do NOT rewrite, modify, rephrase, or shorten this summary.
   - Use the text from the "summary" key of the input JSON exactly as provided.
   - Ensure it is displayed as a clean paragraph under the section header.

3. TECHNICAL SKILLS - DYNAMIC CATEGORIES BASED ON ACTUAL SKILLS:
   - ANALYZE the skills in the JSON data
   - CREATE 4-6 meaningful category names based on the actual skills present
   - Example categories (USE THESE PATTERNS IF SKILLS MATCH):
     - <p><strong>Programming Languages:</strong> Python, Java</p>
     - <p><strong>Web Technologies:</strong> React, HTML, CSS</p>
     - <p><strong>Backend:</strong> Node.js, Django, Spring Boot</p>
     - <p><strong>Database:</strong> MySQL, MongoDB, PostgreSQL</p>
     - <p><strong>Tools & Technologies:</strong> Git, Docker, AWS</p>
   - Each category on a NEW LINE
   - Use <strong>Category Name:</strong> skill1, skill2 format
   - If no skills in a category, SKIP that category

4. EXPERIENCE FORMAT - MUST INCLUDE COMPANY AND DURATION:
   <h3>Software Engineer | Company Name | Jan 2023 - Present</h3>
   <ul><li>Responsibility 1</li><li>Responsibility 2</li></ul>

5. PROJECTS - MUST INCLUDE TECH STACK PROMINENTLY:
   <h3>Project Name</h3>
   <p><strong>Tech Stack:</strong> React, Node.js, MongoDB</p>
   <ul><li>Description 1</li><li>Description 2</li></ul>

6. SECTION ORDER (EXACT):
   - PROFESSIONAL SUMMARY (Use exact text from JSON without truncating)
   - EDUCATION  
   - TECHNICAL SKILLS (dynamic categories based on actual skills, each on new line)
   - EXPERIENCE (with company | duration)
   - PROJECTS (with tech stack)

7. DO NOT output name, role, contact - handled by master template.

8. Use <ul><li> for bullets. Keep everything LEFT-ALIGNED."""

        prompt = f"""
GENERATE HTML for this resume:
{json.dumps(extraction_results, indent=2)}
"""
        from ai_engine.core.llm_client import groq_llm_call_with_fallback_async
        res, _, _ = await groq_llm_call_with_fallback_async(prompt, system_prompt=architect_system)
        if not res:
            raise Exception("Phase 2 LLM call failed")
            
        content_html = strip_markdown_code_fences(res)
        
        # Enforce "v2 Original" Template Alignment and Styling
        full_resume_html = self._apply_v2_template(content_html, extraction_results)
        
        return remove_empty_html_elements(full_resume_html)

    def _apply_v2_template(self, content: str, data: Dict[str, Any]) -> str:
        """
        Wraps raw resume content in the template.
        Uses master_template if provided, otherwise uses default v2 layout.
        """
        # Use master template if available, otherwise use default
        template = getattr(self, 'master_template', None)
        
        # v3 "Absolute Zero" Purge: Wipe out every AI-hallucinated header block
        content = re.sub(r"<!DOCTYPE[^>]*>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"</?(?:html|head|meta|title|body)\b[^>]*>", "", content, flags=re.IGNORECASE)
        
        # Surgical Strike: Delete everything BEFORE the first H2 header (e.g., Professional Summary)
        # This permanently removes the duplicate name/contact info circled in red.
        content = re.sub(r'^.*?<h2', '<h2', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Surgical Summary Injection: Force the verbatim generated summary into the HTML
        if data.get("summary"):
            summary_verbatim = data["summary"].strip()
            pattern_h2 = r"(<h2[^>]*>\s*PROFESSIONAL\s+SUMMARY\s*</h2>)(.*?)(?=<h2)"
            new_content, count = re.subn(pattern_h2, rf"\g<1>\n<p>{summary_verbatim}</p>\n", content, flags=re.IGNORECASE | re.DOTALL)
            if count > 0:
                content = new_content
            else:
                pattern_p = r"(<h2[^>]*>\s*PROFESSIONAL\s+SUMMARY\s*</h2>\s*)<p[^>]*>.*?</p>"
                content = re.sub(pattern_p, rf"\g<1><p>{summary_verbatim}</p>", content, flags=re.IGNORECASE | re.DOTALL)
        
        
        # Extract Socials
        links = data.get('links', [])
        linkedin_link = next((l for l in links if "linkedin.com" in l.lower()), None)
        github_link = next((l for l in links if "github.com" in l.lower()), None)
        other_links = [l for l in links if l != linkedin_link and l != github_link]
        
        social_parts = []
        if linkedin_link: social_parts.append(f'<a href="{linkedin_link}">LinkedIn</a>')
        if github_link: social_parts.append(f'<a href="{github_link}">GitHub</a>')
        for l in other_links[:1]: social_parts.append(f'<a href="{l}">Portfolio</a>')
        
        contact_val = data.get('contact', '')
        if isinstance(contact_val, dict):
            contact_str = " | ".join([str(v) for v in contact_val.values() if v])
        elif isinstance(contact_val, list):
            contact_str = " | ".join([str(v) for v in contact_val if v])
        else:
            contact_str = str(contact_val)

        # v3 Master-Row Extraction: [Email | Phone | City | Socials]
        parts = [p.strip() for p in contact_str.split('|')]
        email = next((p for p in parts if "@" in p), "")
        phone = next((p for p in parts if any(c.isdigit() for c in p) and "@" not in p), "")
        city = data.get('location', 'Hyderabad, India')
        
        row_items = list(filter(None, [email, phone, city]))
        social_row_str = " | ".join(social_parts)
        
        final_contact_line = " | ".join(row_items)
        if social_row_str:
            final_contact_line += f" | {social_row_str}"
        
        # Use master template values or fall back to defaults
        template = getattr(self, 'master_template', None) or {}
        
        alignment = template.get('alignment', 'center')
        font_family = template.get('font_family', 'Calibri')
        font_size_name = template.get('font_size_name', 24)
        font_size_role = template.get('font_size_role', 14)
        font_size_contact = template.get('font_size_contact', 10)
        font_size_section = template.get('font_size_section', 13)
        font_size_body = template.get('font_size_body', 11)
        line_height = template.get('line_height', 1.25)
        margin_top = template.get('margin_top', 0.20)
        margin_bottom = template.get('margin_bottom', 0.20)
        margin_left = template.get('margin_left', 0.5)
        margin_right = template.get('margin_right', 0.5)
        
        header_alignment = 'center' if alignment == 'center' else 'left'
        
        header_html = f"""
        <div style="text-align: {header_alignment}; margin-bottom: 5px;">
            <h1 style="margin: 0; font-size: {font_size_name}pt; text-transform: uppercase; font-family: '{font_family}', sans-serif;">{data.get('full_name', '')}</h1>
            <div style="margin-top: 2px; font-size: {font_size_role}pt; font-weight: bold; color: #333;">{data.get('role_title', '')}</div>
            <div style="margin-top: 4px; font-size: {font_size_contact}pt; color: #555;">{final_contact_line}</div>
            <hr style="border: 0; border-top: 1.5px solid #111; margin: 10px 0 12px 0;">
        </div>
        """
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: '{font_family}', 'Arial', sans-serif;
    font-size: {font_size_body}pt;
    line-height: {line_height};
    color: #111111;
    margin: 0;
    padding: {margin_top}in {margin_right}in {margin_bottom}in {margin_left}in;
    max-width: 8.27in;
  }}
  h1, h2, h3, p, ul, li, strong, a {{
    font-family: '{font_family}', sans-serif;
    color: #111111;
    text-decoration: none;
    display: block;
    width: 100%;
    clear: both;
  }}
  a {{ color: #111111; display: inline-block; width: auto; clear: none; }}
  strong {{ display: inline; width: auto; clear: none; }}
  li {{ display: list-item; width: auto; clear: none; }}
  h1 {{
    font-weight: 700;
  }}
  h2 {{
    margin: 15px 0 6px 0;
    font-size: {font_size_section}pt;
    font-weight: 700;
    text-transform: uppercase;
    text-align: left;
    border-bottom: 1.5px solid #111111;
    padding-bottom: 2px;
  }}
  h3 {{
    margin: 10px 0 2px 0;
    font-size: 11pt;
    font-weight: 700;
  }}
  p {{
    margin: 0 0 8px 0;
    text-align: justify;
  }}
  ul {{
    margin: 0 0 10px 18px;
    padding: 0;
    display: block;
    width: 100%;
  }}
  li {{
    margin: 0 0 4px 0;
    text-align: justify;
  }}
</style>
</head>
<body>
    {header_html}
    {content}
</body>
</html>"""
