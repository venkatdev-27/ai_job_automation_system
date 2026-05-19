from __future__ import annotations
from pathlib import Path
from typing import Any
from utils.helpers import latest_file_from_patterns, download_file
from utils.path_contract import resolve_ai_engine_pdf_path
from rag_engine.rag_engine import RAGEngine, ProductionRAGOrchestrator
import asyncio


class ResumeClient:
    """
    Selects an already generated resume file.
    This module never edits or regenerates resume content.
    """

    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger

    async def get_resume_for_job(self, profile: Any, job: dict[str, Any]) -> Path:
        """
        Main entry point for retrieving or generating a resume.
        Now calls generate_tailored_resume to ensure a fresh, role-aligned PDF.
        """
        # Support for production Cloudinary URLs
        resume_url = job.get("resume_url")
        if resume_url and (resume_url.startswith("http://") or resume_url.startswith("https://")):
            return self.resolve_remote_resume(resume_url)

        try:
            return await self.generate_tailored_resume(profile, job)
        except Exception as exc:
            self.logger.error(f"Resume generation failed: {exc}. Falling back to latest existing.")
            return self._get_latest_existing_resume()

    def resolve_remote_resume(self, url: str) -> Path:
        """
        Downloads a remote resume (Cloudinary) to the local temp directory.
        """
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        temp_path = self.settings.base_dir / "temp" / f"remote_resume_{url_hash}.pdf"
        
        self.logger.info(f"Resolving remote resume from Cloudinary: {url}")
        return download_file(url, temp_path)

    async def generate_production_resume(self, old_cloudinary_url: str, job_info: dict[str, Any]) -> str:
        """
        High-fidelity production pipeline: RAG + Polishing + Cloudinary Upload.
        Returns the NEW Cloudinary URL.
        """
        orchestrator = ProductionRAGOrchestrator(self.settings)
        return await orchestrator.run_pipeline(old_cloudinary_url, job_info)

    async def generate_tailored_resume(self, profile: Any, job: dict[str, Any]) -> Path:
        import requests
        import json
        import os
        from utils.pdf_reader import extract_text_from_pdf
        
        # New API endpoint for the modular engine.
        in_docker = os.getenv("IN_DOCKER", "false").lower() == "true"
        default_url = "http://ai-engine:8000" if in_docker else "http://localhost:8000"
        api_base_url = os.getenv("LOCAL_API_URL", default_url).rstrip("/")
        api_url = f"{api_base_url}/generate"
        
        # 1. RAG Processing (High-Fidelity)
        self.logger.info("Initializing RAG-FAISS Engine for tailor-resume context...")
        rag = RAGEngine()
        
        resume_path = profile.resume_path or os.getenv("STUDENT_RESUME_PATH")
        if not resume_path or not os.path.exists(resume_path):
             self.logger.warning("No Master Resume found for RAG. Falling back to profile text.")
             retrieved_chunks = getattr(profile, "raw_resume_context", "") or str(profile)
        else:
            self.logger.info(f"Indexing Master Resume: {resume_path}")
            resume_text = extract_text_from_pdf(resume_path)
            
            # Use Universal Context Strike for tailoring (fetch ALL chunks)
            jd_text = job.get("description", "")
            results = await rag.full_rag_pipeline_async(resume_text, jd_text, total_context=True)
            retrieved_chunks = results.get("retrieved_context", "")
            
            # Prepend Header Persistence (Crucial for V2)
            header = f"""
            NAME: {profile.name}
            EMAIL: {profile.email}
            PHONE: {profile.phone}
            LOCATION: {profile.location}
            """
            retrieved_chunks = header + "\n\n" + retrieved_chunks
            self.logger.info(f"Retrieved {results.get('chunks_retrieved', 0)} high-fidelity chunks via FAISS.")

        input_data = {
            "jobDescription": job.get("description", ""),
            "retrievedChunks": retrieved_chunks,
            "disableCache": False,
            "refreshCache": True
        }
        
        self.logger.info(f"Connecting to AI Resume Engine at {api_url}")
        try:
            # We use a thread to run the synchronous requests.post call in an async context
            def do_post():
                return requests.post(api_url, json=input_data, timeout=300)
                
            response = await asyncio.to_thread(do_post)
            
            if response.status_code != 200:
                self.logger.error(f"AI Engine Error {response.status_code}: {response.text}")
                raise Exception(f"AI Engine failed with status {response.status_code}")

            result = response.json()
            pdf_path = resolve_ai_engine_pdf_path(result)
            
            if pdf_path:
                self.logger.info(f"Generated tailored resume via API: {pdf_path}")
                return pdf_path
            
            raise Exception("API returned success but PDF path is missing or invalid.")
            
        except requests.exceptions.ConnectionError:
            self.logger.error("Could not connect to AI Resume Engine. Ensure uvicorn is running on port 8000.")
            raise
        except Exception as e:
            self.logger.error(f"API call to Resume Engine failed: {e}")
            raise

    def _get_latest_existing_resume(self) -> Path:
        # Priority 1: Check for any PDF files first
        latest_pdf = latest_file_from_patterns(
            self.settings.resume_directory,
            ["*.pdf"],
        )
        if latest_pdf:
            self.logger.info("Using latest existing PDF resume: %s", latest_pdf)
            return latest_pdf

        # Priority 2: Fallback to Word documents only if no PDF exists
        latest_word = latest_file_from_patterns(
            self.settings.resume_directory,
            ["*.docx", "*.doc"],
        )
        if latest_word:
            self.logger.info("No PDF found. Falling back to Word document: %s", latest_word)
            return latest_word

        raise FileNotFoundError(
            f"No resume found in {self.settings.resume_directory}."
        )
