import re
import asyncio
import logging
from typing import List, Optional
from rag_engine.rag_engine import GroqLLM

# Setup logging
logger = logging.getLogger("AI_Extractor")

class AIExtractor:
    def __init__(self, llm: Optional[GroqLLM] = None):
        self.llm = llm or GroqLLM()

    async def extract_skills_async(self, jd_text: str) -> List[str]:
        """
        Extracts technical skills from JD with a high-recall prompt.
        Ensures multiple skills are returned whenever possible.
        """
        if not jd_text or len(jd_text.strip()) < 50:
            return []

        # Truncate to reasonable length for token limits
        truncated_jd = jd_text[:4000]

        system_prompt = (
            "You are a Technical Sourcing Specialist. Your goal is to identify EVERY technology, "
            "programming language, framework, database, cloud provider, and tool mentioned in a job description. "
            "Be extremely thorough. Do not limit yourself to just the 'main' skills; include secondary and "
            "supporting tools as well. Return ONLY a comma-separated list of technical terms. No sentences."
        )

        prompt = f"""
ANALYZE THE FOLLOWING JOB DESCRIPTION AND EXTRACT ALL TECHNICAL SKILLS.

EXAMPLES OF WHAT TO EXTRACT:
- Languages: Python, Java, C++, TypeScript, Go
- Frameworks: React, Django, Spring Boot, Node.js, FastAPI
- Databases: PostgreSQL, MongoDB, Redis, Cassandra
- Cloud/DevOps: AWS, Azure, Docker, Kubernetes, Jenkins, Terraform
- Tools/Libraries: Git, NumPy, Pandas, Kafka, RabbitMQ, Redux
- Methodologies: Agile, Scrum, CI/CD, Microservices

STRICT RULES:
1. Identify AT LEAST 10-15 skills if the JD is long enough. 
2. Return ONLY comma-separated values.
3. No descriptions (e.g., don't say "Python for scripting", just say "Python").
4. If no skills are found, return an empty string.

JOB DESCRIPTION:
{truncated_jd}
"""

        try:
            # Using a slightly higher temperature for better discovery
            result = await self.llm.async_generate(
                prompt=prompt,
                system=system_prompt,
                max_tokens=300
            )

            if not result:
                logger.warning("AI Extractor returned empty result")
                return []

            # Clean and split the result
            # Handle cases where AI might add numbering or bullets despite instructions
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', result, flags=re.MULTILINE)
            skills = [s.strip() for s in re.split(r'[,\n]', cleaned) if s.strip()]
            
            # Additional cleanup: remove bullet points or numbering if they leaked through
            skills = [re.sub(r'^[-*•]\s*', '', s) for s in skills]
            
            # Filter out generic high-level non-technical words if they appear
            blacklist = {"strong", "experience", "skills", "good", "ability", "excellent", "working"}
            skills = [s for s in skills if s.lower() not in blacklist and len(s) > 1 and len(s) < 40]

            # Dedupe while preserving order
            seen = set()
            deduped_skills = []
            for s in skills:
                s_lower = s.lower()
                if s_lower not in seen:
                    deduped_skills.append(s)
                    seen.add(s_lower)

            logger.info(f"AI Extraction complete. Found {len(deduped_skills)} skills.")
            return deduped_skills

        except Exception as e:
            logger.error(f"AI skill extraction failed in utility: {e}")
            return []

    async def extract_details_async(self, jd_text: str) -> dict:
        """
        Extracts skills, qualifications, and experience requirements from JD.
        Returns a dict with 'skills', 'qualifications', and 'experience_years'.
        """
        if not jd_text or len(jd_text.strip()) < 50:
            return {"skills": [], "qualifications": [], "experience_years": "0"}

        truncated_jd = jd_text[:5000]

        system_prompt = (
            "You are a Senior Technical Recruiter. Your task is to analyze job descriptions "
            "and extract structured requirements. Focus on identifying specific technologies (skills) "
            "and educational/professional prerequisites (qualifications)."
        )

        prompt = f"""
ANALYZE THE FOLLOWING JOB DESCRIPTION AND EXTRACT DETAILS.

REQUIRED OUTPUT FORMAT (JSON ONLY):
{{
  "skills": ["Skill1", "Skill2", ...],
  "qualifications": ["Qualification1", "Qualification2", ...],
  "experience_years": "number or range"
}}

STRICT RULES:
1. 'skills' should include programming languages, frameworks, tools, etc.
2. 'qualifications' should include degrees (B.E, B.Tech, MCA), certifications, or specific domain experience.
3. 'experience_years' should be the minimum years required (e.g., '2', '3-5').
4. Return ONLY valid JSON. No extra text.

JOB DESCRIPTION:
{truncated_jd}
"""

        try:
            from rag_engine.rag_engine import GroqLLM
            llm = self.llm or GroqLLM()
            
            # Use generate_json if available, else parse manually
            result_json = await llm.async_generate_json(
                prompt=prompt,
                system=system_prompt,
                max_tokens=600
            )

            if not result_json:
                # Fallback to manual extraction if JSON generation failed
                logger.warning("AI Extractor JSON generation failed, using fallback")
                skills = await self.extract_skills_async(jd_text)
                return {"skills": skills, "qualifications": [], "experience_years": "0"}

            # Normalize keys
            final_result = {
                "skills": result_json.get("skills", []),
                "qualifications": result_json.get("qualifications", []),
                "experience_years": str(result_json.get("experience_years", "0"))
            }
            
            logger.info(f"AI Detail Extraction complete. Found {len(final_result['skills'])} skills and {len(final_result['qualifications'])} qualifications.")
            return final_result

        except Exception as e:
            logger.error(f"AI detail extraction failed: {e}")
            return {"skills": [], "qualifications": [], "experience_years": "0"}

# Singleton instance for easy reuse
_extractor_instance = None

def get_ai_extractor() -> AIExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = AIExtractor()
    return _extractor_instance
