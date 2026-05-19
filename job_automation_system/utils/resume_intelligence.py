import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, List

# Import our new PDF reader
try:
    from .pdf_reader import extract_text_from_pdf
except ImportError:
    try:
        from utils.pdf_reader import extract_text_from_pdf
    except ImportError:
        from pdf_reader import extract_text_from_pdf

# Import RAG engine components
try:
    from rag_engine.rag_engine import MiniMaxLLM, get_llm_semaphore
except ImportError:
    from ..rag_engine import MiniMaxLLM, get_llm_semaphore

logger = logging.getLogger(__name__)

class ResumeIntelligence:
    """
    Utility to analyze a resume PDF and extract search roles, skills, and profile data.
    """
    
    def __init__(self, settings: Any = None):
        self.settings = settings
        self.llm = MiniMaxLLM()

    async def extract_profile_from_pdf(self, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Extracts candidate profile data (Role, Skills, etc.) from a PDF resume.
        """
        resume_text = extract_text_from_pdf(pdf_path)
        if not resume_text:
            logger.error("Could not extract text from PDF.")
            return {}

        logger.info(f"Analyzing resume profile intelligence for: {pdf_path}")
        
        prompt = f"""
        Analyze this resume text and extract the candidate's core professional profile as JSON.
        We need this to automate their job search.
        
        RESUME TEXT:
        {resume_text[:6000]}
        
        Return ONLY this JSON structure:
        {{
          "full_name": "string",
          "email": "string",
          "phone": "string",
          "location": "string",
          "target_role": "Short job title (e.g. MERN Full Stack Developer)",
          "search_keywords": ["skill1", "skill2", "role keyword"],
          "technical_skills": ["List EVERY professional skill/tool found in resume (e.g. React, Node, HTML, CSS, SQL, Docker, Redux, etc)"],
          "summary": "Short 2-sentence summary"
        }}
        """

        try:
            profile = await self.llm.async_generate_json(
                prompt,
                system="You are an expert talent acquisition agent. Return valid JSON only.",
                temperature=0.1
            )
            
            # Validation / Fallback
            if not profile.get("target_role"):
                profile["target_role"] = "Software Developer"
            
            logger.info(f"Successfully extracted dynamic profile. Role: {profile['target_role']}")
            profile["resume_text"] = resume_text
            return profile

        except Exception as e:
            logger.error(f"Failed to extract profile intelligence: {e}")
            return {"resume_text": resume_text, "target_role": "Software Developer"}

async def get_dynamic_search_config(pdf_resume_path: str | Path) -> Dict[str, Any]:
    """
    Helper function to get just the role and keywords for search initialization.
    """
    intel = ResumeIntelligence()
    profile = await intel.extract_profile_from_pdf(pdf_resume_path)
    return {
        "role": profile.get("target_role", "Software Developer"),
        "keywords": profile.get("search_keywords", []),
        "profile": profile
    }

if __name__ == "__main__":
    # Test
    import sys
    async def test():
        if len(sys.argv) > 1:
            res = await get_dynamic_search_config(sys.argv[1])
            print(json.dumps(res, indent=2))
    
    if len(sys.argv) > 1:
        asyncio.run(test())
