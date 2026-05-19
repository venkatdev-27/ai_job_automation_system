"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              REAL RAG ENGINE with HyDE + MiniMax M 2.5 LLM                  ║
║  Features: Embeddings, FAISS Vector DB, HyDE Retrieval, Dynamic JD Extract  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
from config.settings import settings

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
import httpx
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import requests
from dotenv import load_dotenv

# Load environment from project root (one level up)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# LangChain imports
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

logger = logging.getLogger("RAGEngine")

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

MINIMAX_API_KEY = settings.minimax_api_key
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")  # MiniMax M 2.5 equivalent
GEMINI_API_KEY = settings.gemini_api_key or settings.openrouter_api_key or os.getenv("GOOGLE_API_KEY", "")

# RAG Configuration
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 23
HYDE_TEMPERATURE = 0.2
RAG_TEMPERATURE = 0.1

def is_chromadb_available() -> bool:
    """Check if ChromaDB is installed and available"""
    try:
        import chromadb
        return True
    except ImportError:
        return False

# --- Global Rate Limiting (CRITICAL IMPROVEMENT) ---
# Limits max parallel requests and ensures burst prevention across all LLM clients.
GLOBAL_LLM_SEMAPHORE = None

def get_llm_semaphore():
    global GLOBAL_LLM_SEMAPHORE
    if GLOBAL_LLM_SEMAPHORE is None:
        # Increased to 8 to match total worker slots across all platforms
        GLOBAL_LLM_SEMAPHORE = asyncio.Semaphore(8)
    return GLOBAL_LLM_SEMAPHORE


# ──────────────────────────────────────────────────────────────────────────────
# MiniMax LLM Client (Direct API - no LangChain wrapper needed)
# ──────────────────────────────────────────────────────────────────────────────

class MiniMaxLLM:
    """
    Groq-powered LLM client (defaults to Llama 3.1 8b).
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        # Prioritize Groq API Key and High-Speed Llama model
        self.api_key = api_key or settings.groq_api_key or settings.minimax_api_key
        self.model = model or os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"
        
        # Determine gateway (default to Groq)
        if self.api_key and (self.api_key.startswith("gsk_") or "groq" in os.environ.get("GROQ_API_KEY", "").lower()):
            logger.info(f"Using Groq API - Model: {self.model}")
            self.base_url = settings.groq_api_url + "/chat/completions"
        elif self.api_key and self.api_key.startswith("sk-or-"):
            logger.info("Using OpenRouter Gateway")
            self.base_url = settings.openrouter_api_url + "/chat/completions"
        else:
            logger.info("Using Native MiniMax API Fallback")
            self.base_url = settings.minimax_api_url + "/text/chatcompletion_v2"
        
        if not self.api_key:
            logger.warning("No API key found for LLM. RAG will not function.")
    
    async def async_generate(
        self,
        prompt: str,
        system: str = "You are a helpful AI assistant.",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        retries: int = 3,
        preferred_model: str = None
    ) -> str:
        """Async generate with Smart Throttling and Multi-Tier strategy."""
        if not self.api_key: return ""
        
        # 1. Global Semaphore & Multi-Tier Strategy
        target_model = preferred_model or self.model
        retry_delay = 2.0
        semaphore = get_llm_semaphore()
        
        async with httpx.AsyncClient() as client:
            for attempt in range(retries):
                try:
                    # IMPLEMENTATION: Global locking to prevent parallel spikes (VERY IMPORTANT)
                    async with semaphore:
                        # Extra jittered wait inside the lock to ensure pacing
                        await asyncio.sleep(random.uniform(2, 4))
                        
                        # Use 70b -> if 429 -> retry 70b -> if still 429 -> downgrade to 8b
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/kosurivenky/ai-bot-resumes",
                        "X-Title": "AI Resume Automation Bot"
                    }
                    payload = {
                        "model": target_model,
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False
                    }

                    response = await client.post(self.base_url, headers=headers, json=payload, timeout=120.0)
                    
                    if response.status_code == 200:
                        # SUCCESS: Apply mandatory Smart Throttling jittered delay
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        
                        # Mandatory Jitter (avoids burst detection)
                        await asyncio.sleep(random.uniform(2, 4))
                        return content
                        
                    elif response.status_code == 429:
                        # DYNAMIC DOWNGRADE: If 70B fails twice, switch to 8B permanently for this request
                        if "70b" in target_model.lower():
                            if attempt == 0:
                                logger.warning(f"Groq 70B Limit hit (429). Retrying original model in 3s...")
                                await asyncio.sleep(3)
                                continue
                            else:
                                logger.warning("Groq 70B persists 429. DOWNGRADING to 8B-Instant for this task.")
                                target_model = "llama-3.1-8b-instant"
                                await asyncio.sleep(retry_delay)
                                continue
                        
                        # Exponential Backoff for 8B or others
                        wait = retry_delay + random.uniform(1, 3)
                        logger.warning(f"LLM Rate Limit (429) on {target_model}. Retrying in {wait:.1f}s...")
                        await asyncio.sleep(wait)
                        retry_delay *= 2
                        continue
                    else:
                        logger.error(f"LLM API Error: {response.status_code} - {response.text}")
                except Exception as e:
                    logger.error(f"Generation attempt {attempt+1} failed ({target_model}): {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                    
        return ""
    
    # Sync generate_json is deprecated.

    async def async_generate_json(
        self,
        prompt: str,
        system: str = "You are a JSON-only API. Return valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        retries: int = 3,
        preferred_model: str = None
    ) -> dict:
        """Async generate and parse JSON."""
        raw = await self.async_generate(prompt, system, temperature, max_tokens, retries, preferred_model=preferred_model)
        return self._parse_json(raw)
    
    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Parse JSON from LLM response."""
        text = (raw or "").strip()
        if not text:
            return {}
        
        # Try find first { }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except:
                pass
        
        return {}


class GroqLLM:
    """
    Direct Groq API client for HyDE generation.
    Used for high-speed, reliable retrieval tasks.
    """
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.base_url = settings.groq_api_url + "/chat/completions"
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set. HyDE will use direct retrieval fallback.")
    
    # Sync generate is deprecated.

    async def async_generate(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        temperature: float = 0.2,
        max_tokens: int = 2000,
        retries: int = 3,
        preferred_model: str = None
    ) -> str:
        """Wrapper for MiniMaxLLM which now handles multi-tier logic."""
        client = MiniMaxLLM(api_key=self.api_key, model=self.model)
        return await client.async_generate(prompt, system, temperature, max_tokens, retries, preferred_model=preferred_model)

    # Sync generate_json is deprecated.

    async def async_generate_json(
        self,
        prompt: str,
        system: str = "You are a JSON-only API. Return valid JSON only.",
        temperature: float = 0.1,
        max_tokens: int = 3000,
        preferred_model: str = None
    ) -> dict:
        raw = await self.async_generate(prompt, system, temperature, max_tokens, preferred_model=preferred_model)
        return self._parse_json(raw)
    
    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Parse JSON from LLM response."""
        text = (raw or "").strip()
        if not text:
            return {}
        
        # Try find first { }
        import json
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except:
                pass
        
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Output Schema for RAG Analysis
# ──────────────────────────────────────────────────────────────────────────────

class JDExtractionResult(BaseModel):
    """Schema for extracted job description requirements."""
    required_skills: List[str] = Field(description="List of required technical skills")
    preferred_skills: List[str] = Field(description="List of preferred/nice-to-have skills")
    experience_level: str = Field(description="Required experience level (fresher, junior, mid, senior)")
    key_responsibilities: List[str] = Field(description="Main job responsibilities")
    domain_keywords: List[str] = Field(description="Domain-specific keywords")
    soft_skills: List[str] = Field(description="Required soft skills")


class RAGMatchResult(BaseModel):
    """Schema for RAG-based resume-JD matching."""
    match_score: int = Field(description="Match score from 0 to 100")
    matched_skills: List[str] = Field(description="Skills that matched between resume and JD")
    missing_skills: List[str] = Field(description="Critical skills missing from resume")
    strength_areas: List[str] = Field(description="Areas where candidate excels")
    gap_areas: List[str] = Field(description="Areas needing improvement")
    hyde_relevance: float = Field(description="Relevance score of HyDE retrieval (0-1)")
    reason: str = Field(description="Brief explanation for the score")


# ──────────────────────────────────────────────────────────────────────────────
# Real RAG Engine
# ──────────────────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Production-grade RAG system with:
    - Real embeddings (Google Gemini Embeddings)
    - ChromaDB vector database (primary) with FAISS fallback
    - HyDE (Hypothetical Document Embeddings) retrieval
    - MongoDB fallback for resume text retrieval
    """
    # v3 Optimization: Static Class-Level Singleton Cache
    _VECTORSTORE_CACHE = {}
    _EMBEDDINGS_INSTANCE = None
    _CHROMA_CLIENT_CACHE = {}  # Per-path ChromaDB client cache

    def __init__(
        self,
        minimax_api_key: str = None,
        gemini_api_key: str = None,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        top_k: int = TOP_K_RETRIEVAL,
    ):
        self.minimax_key = minimax_api_key or settings.minimax_api_key
        self.gemini_key = gemini_api_key or settings.gemini_api_key or os.getenv("GOOGLE_API_KEY")
        
        # v4 Silence: Only set one key in environment to stop the noisy warning
        if self.gemini_key:
            os.environ["GOOGLE_API_KEY"] = self.gemini_key
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        
        # Storage path - ChromaDB on D drive
        self.chroma_path = settings.chroma_db_dir
        
        # Initialize components
        self.llm = MiniMaxLLM(api_key=os.getenv("GROQ_API_KEY", self.minimax_key))
        self.hyde_llm = GroqLLM() # Dedicated Groq client for HyDE
        self.embeddings = None
        self.text_splitter = None
        self.vectorstore = None
        self._initialized = False
        
        logger.info("Using ChromaDB for vector storage (D: drive)")
        
        # Fallback: MongoDB resume text storage
        self._mongodb_text_cache = {}
        self._current_student_id = None  # Can be set externally for MongoDB fallback
        
        self._initialize()
    
    def set_student_id(self, student_id: str):
        """Set current student ID for MongoDB fallback"""
        self._current_student_id = student_id
    
    def _get_mongodb_resume_text(self) -> str:
        """Get resume text from MongoDB as fallback"""
        if not self._current_student_id:
            logger.debug("No student_id set, skipping MongoDB fallback")
            return ""
        
        try:
            from utils.student_mongodb import get_student_by_id
            student = get_student_by_id(self._current_student_id)
            if student:
                # Check for extracted text in master_template
                master_template = student.get("master_template", {})
                if master_template:
                    # Return the extracted text
                    return str(master_template.get("text", ""))
            logger.debug(f"No MongoDB text found for student: {self._current_student_id}")
        except ImportError:
            logger.debug("student_mongodb not available")
        except Exception as e:
            logger.warning(f"MongoDB fallback error: {e}")
        
        return ""
    
    def _get_chroma_client(self):
        """Get or create ChromaDB client singleton (per path)"""
        if self.chroma_path not in RAGEngine._CHROMA_CLIENT_CACHE:
            try:
                import chromadb
                RAGEngine._CHROMA_CLIENT_CACHE[self.chroma_path] = chromadb.PersistentClient(
                    path=self.chroma_path
                )
            except Exception as e:
                logger.warning(f"Failed to create ChromaDB client: {e}")
                RAGEngine._CHROMA_CLIENT_CACHE[self.chroma_path] = None
        return RAGEngine._CHROMA_CLIENT_CACHE[self.chroma_path]
    
    def _initialize(self):
        """Initialize embeddings (Singleton) and text splitter."""
        try:
            if self.gemini_key:
                # v3 Singleton Optimization: Do not re-init embeddings (silences logs)
                if RAGEngine._EMBEDDINGS_INSTANCE is None:
                    RAGEngine._EMBEDDINGS_INSTANCE = GoogleGenerativeAIEmbeddings(
                        model="models/gemini-embedding-001"
                    )
                
                self.embeddings = RAGEngine._EMBEDDINGS_INSTANCE
                
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                self._initialized = True
                if not hasattr(RAGEngine, "_logged_init"):
                    logger.info("RAG Engine initialized with Gemini embeddings (Singleton)")
                    RAGEngine._logged_init = True
            else:
                logger.warning("GEMINI_API_KEY not set. Embeddings will not function.")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Engine: {e}")
    
    def index_resume(self, resume_text: str, force_reindex: bool = False) -> bool:
        """
        Index resume text using ChromaDB only.
        """
        if not self._initialized: return False
        
        # 1. RAM-Singleton Check (Sub-Millisecond Skip)
        content_hash = hashlib.md5(resume_text.encode()).hexdigest()
        cache_key = f"chroma_{content_hash}"
        
        if not force_reindex and cache_key in RAGEngine._VECTORSTORE_CACHE:
            self.vectorstore = RAGEngine._VECTORSTORE_CACHE[cache_key]
            return True

        # 2. Index with ChromaDB
        try:
            return self._index_with_chromadb(resume_text, content_hash, cache_key, force_reindex)
        except Exception as e:
            logger.error(f"ChromaDB indexing failed: {e}")
            return False
    
    def _index_with_chromadb(self, resume_text: str, content_hash: str, cache_key: str, force_reindex: bool) -> bool:
        """Index resume using ChromaDB"""
        try:
            import chromadb
        except ImportError:
            raise Exception("ChromaDB not installed")
        
        # Ensure persist directory exists
        os.makedirs(self.chroma_path, exist_ok=True)
        
        # Create collection name based on content hash
        collection_name = f"resume_{content_hash[:12]}"
        
        # Check if collection already exists (skip if not force_reindex)
        if not force_reindex:
            try:
                chroma_client = self._get_chroma_client()
                if chroma_client:
                    existing_collections = chroma_client.list_collections()
                    if collection_name in [c.name for c in existing_collections]:
                        # Load existing collection using langchain Chroma with client
                        self.vectorstore = Chroma(
                            client=chroma_client,
                            collection_name=collection_name,
                            embedding_function=self.embeddings
                        )
                        RAGEngine._VECTORSTORE_CACHE[cache_key] = self.vectorstore
                        logger.info(f"Loaded existing ChromaDB collection: {collection_name}")
                        return True
            except Exception as e:
                logger.warning(f"Failed to check existing ChromaDB collection: {e}")
        
        # Split text into chunks
        chunks = self.text_splitter.split_text(resume_text)
        if not chunks:
            logger.warning("No chunks generated from resume text")
            return False
        
        # Get or create ChromaDB client
        chroma_client = self._get_chroma_client()
        if not chroma_client:
            raise Exception("Failed to get ChromaDB client")
        
        # Create new ChromaDB collection using client
        self.vectorstore = Chroma(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=self.embeddings
        )
        
        # Add documents to collection
        self.vectorstore.add_texts(texts=chunks, metadatas=[{"source": "resume", "chunk_id": i} for i in range(len(chunks))])
        
        self._all_chunks = chunks
        RAGEngine._VECTORSTORE_CACHE[cache_key] = self.vectorstore
        
        logger.info(f"Indexed {len(chunks)} chunks to ChromaDB (Hash: {content_hash[:12]})")
        return True
    
    async def retrieve_all_chunks_async(self) -> List[str]:
        """v3 Absolute Retention: Returns the full raw text to ensure ZERO data loss.
        Tries: 1) Cached chunks 2) ChromaDB 3) MongoDB fallback 4) PDF extraction"""
        
        # 1. Try cached chunks first
        if hasattr(self, "_all_chunks") and self._all_chunks:
            return ["\n".join(self._all_chunks)]
        
        # 2. Try vectorstore retrieval
        if hasattr(self, "vectorstore") and self.vectorstore:
            try:
                docs = await asyncio.to_thread(self.vectorstore.similarity_search, query=" ", k=100)
                if docs:
                    return [doc.page_content for doc in docs]
            except Exception as e:
                logger.warning(f"Vectorstore retrieval failed: {e}")
        
        # 3. MongoDB Fallback - Get resume from MongoDB directly
        try:
            mongodb_text = self._get_mongodb_resume_text()
            if mongodb_text:
                logger.info("Using MongoDB fallback for resume text")
                # Also index it for future use
                self.index_resume(mongodb_text)
                return [mongodb_text]
        except Exception as e:
            logger.warning(f"MongoDB fallback failed: {e}")
        
        # 4. PDF Extraction Fallback
        try:
            from utils.pdf_reader import extract_text_from_pdf
            master_resume_path = settings.base_dir.parent / "temp_pipeline" / "Venkat_Kosuri.pdf"
            if master_resume_path.exists():
                 logger.info(f"RECOVERY_STRIKE: Deep-scanning {master_resume_path.name} for 100% parity.")
                 full_text = extract_text_from_pdf(str(master_resume_path))
                 if full_text:
                     return [full_text]
        except Exception as e:
            logger.error(f"Recovery Strike Failed: {e}")

        return []
    
    def _get_mongodb_resume_text(self) -> str:
        """Get resume text from MongoDB as fallback"""
        try:
            from utils.student_mongodb import get_student_resume_text
            # Try to get from MongoDB - this will need student_id context
            # For now, return empty - actual implementation needs student_id
            return ""
        except ImportError:
            return ""

    async def retrieve_with_hyde_async(self, query: str, k: int = None, total_context: bool = False) -> List[str]:
        """Async HyDE retrieval with optional Total Context override.
        Uses ChromaDB, falls back to MongoDB if fails."""
        
        # Try total context retrieval first if requested
        if total_context:
            if hasattr(self, "vectorstore") and self.vectorstore:
                try:
                    # ChromaDB doesn't have index_to_docstore_id, get count differently
                    k = 100
                except: 
                    k = 100 
            else:
                return await self.retrieve_all_chunks_async()
        
        if not self.vectorstore:
            # Fallback: Return MongoDB text or PDF
            return await self.retrieve_all_chunks_async()
        
        k = k or self.top_k
        
        try:
            hyde_prompt = f"Write a short hypothetical candidate profile matching this query: {query}"
            hypothetical_doc = await self.hyde_llm.async_generate(
                hyde_prompt,
                system="You are an expert HR recruiter writing candidate profiles.",
                temperature=HYDE_TEMPERATURE,
                max_tokens=300
            ) if self.hyde_llm else ""

            search_query = hypothetical_doc if hypothetical_doc else query
            
            # ChromaDB uses query parameter
            docs = await asyncio.to_thread(
                self.vectorstore.similarity_search, 
                query=search_query, 
                k=k
            )
            return [doc.page_content for doc in docs]
        except Exception as e:
            logger.warning(f"Vector search failed, falling back: {e}")
            # Fallback to all chunks
            return await self.retrieve_all_chunks_async()

    def retrieve_with_hyde(self, query: str, k: int = None) -> List[str]:
        return asyncio.run(self.retrieve_with_hyde_async(query, k))
    
    async def extract_jd_requirements_async(self, job_description: str) -> dict:
        """Async JD extraction with robust key mapping."""
        prompt = f"Analyze this job description and extract structured requirements as JSON:\n{job_description[:8000]}"
        result = await self.llm.async_generate_json(
            prompt,
            system="You are an expert job description analyzer. Return valid JSON only with 'required_skills' and 'experience_level'.",
            temperature=0.1,
            max_tokens=2500
        )
        
        # Robust mapping for varying LLM outputs + Lower-case normalization
        return {
            "required_skills": [s.lower().strip() for s in result.get("required_skills", result.get("technical_skills", result.get("skills", []))) if s],
            "preferred_skills": [s.lower().strip() for s in result.get("preferred_skills", result.get("nice_to_have", [])) if s],
            "experience_level": str(result.get("experience_level", result.get("experience", "unknown"))).lower(),
            "key_responsibilities": result.get("key_responsibilities", result.get("responsibilities", [])),
            "domain_keywords": [s.lower().strip() for s in result.get("domain_keywords", []) if s],
            "soft_skills": [s.lower().strip() for s in result.get("soft_skills", []) if s],
        }

    def extract_jd_requirements(self, job_description: str) -> dict:
        return asyncio.run(self.extract_jd_requirements_async(job_description))
    
    async def analyze_match_async(self, job_description: str, retrieved_context: str) -> dict:
        """Async match analysis with score normalization."""
        prompt = (
            f"Compare the resume context against the Job Description.\n"
            f"Evaluate how well the candidate's skills and experience match the requirements.\n"
            f"Return a JSON object with match_score, matched_skills, missing_skills, strength_areas, gap_areas, and reason.\n\n"
            f"JD: {job_description[:5000]}\n"
            f"CONTEXT: {retrieved_context[:5000]}"
        )
        
        result = await self.llm.async_generate_json(
            prompt,
            system="You are an expert ATS evaluator. Return valid JSON only. Always provide a match_score as an integer 0-100.",
            temperature=0.1,
            max_tokens=2500
        )
        
        # Normalize score
        raw_score = result.get("match_score", 50)
        try:
            # If LLM returned 0.0-1.0 range, convert to percentage
            if isinstance(raw_score, float) and 0 <= raw_score <= 1.0:
                score = int(raw_score * 100)
            else:
                score = int(float(raw_score))
                if score < 1: score = 50 # Fallback for garbage
        except:
            score = 50

        return {
            "match_score": score,
            "matched_skills": result.get("matched_skills", []),
            "missing_skills": result.get("missing_skills", []),
            "strength_areas": result.get("strength_areas", []),
            "gap_areas": result.get("gap_areas", []),
            "hyde_relevance": result.get("hyde_relevance", 0.5),
            "reason": result.get("reason", "Analysis completed"),
        }

    def analyze_match(self, job_description: str, retrieved_context: str) -> dict:
        return asyncio.run(self.analyze_match_async(job_description, retrieved_context))

    async def full_rag_pipeline_async(self, resume_text: str, job_description: str, total_context: bool = False) -> dict:
        """
        Zero-Redundancy Async Pipeline:
        1. Index (Cache-aware)
        2. Parallel (Extract JD + Retrieve HyDE)
        3. Match Analysis
        """
        # 1. Index (Sync but fast if cached)
        self.index_resume(resume_text)

        # 2. Parallel Extraction & Retrieval
        jd_task = self.extract_jd_requirements_async(job_description)
        hyde_task = self.retrieve_with_hyde_async(job_description[:2000], total_context=total_context) 
        
        jd_requirements, retrieved_chunks = await asyncio.gather(jd_task, hyde_task)
        retrieved_context = "\n\n---\n\n".join(retrieved_chunks)

        # 3. Analyze Match
        match_analysis = await self.analyze_match_async(job_description, retrieved_context)

        return {
            "success": True,
            "jd_requirements": jd_requirements,
            "match_analysis": match_analysis,
            "retrieved_context": retrieved_context,
            "hyde_queries_used": 1,
            "chunks_retrieved": len(retrieved_chunks),
        }

    def full_rag_pipeline(self, resume_text: str, job_description: str, profile_data: dict = None) -> dict:
        return asyncio.run(self.full_rag_pipeline_async(resume_text, job_description))
    
    # ──────────────────────────────────────────────────────────────────────────────
    # ChromaDB Cleanup Methods
    # ──────────────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def cleanup_student_collection(student_id: str, chroma_path: str = None) -> bool:
        """Delete ChromaDB collection when student removed"""
        if chroma_path is None:
            chroma_path = settings.chroma_db_dir
        
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(anonymized_telemetry=False)
            )
            collection_name = f"resume_{student_id}"
            client.delete_collection(collection_name)
            logger.info(f"Cleaned ChromaDB collection for student: {student_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cleanup ChromaDB collection: {e}")
            return False
    
    @staticmethod
    def cleanup_inactive_collections(days: int = 7, chroma_path: str = None) -> int:
        """Delete collections inactive for X days. Returns count of deleted collections."""
        if chroma_path is None:
            chroma_path = settings.chroma_db_dir
        
        deleted_count = 0
        try:
            import chromadb
            from chromadb.config import Settings
            import time
            
            client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            collections = client.list_collections()
            current_time = time.time()
            cutoff_time = current_time - (days * 24 * 60 * 60)
            
            for collection in collections:
                try:
                    # Get metadata to check last access
                    metadata = collection.metadata or {}
                    last_access = metadata.get("last_access", 0)
                    
                    if last_access > 0 and last_access < cutoff_time:
                        client.delete_collection(collection.name)
                        deleted_count += 1
                        logger.info(f"Deleted inactive collection: {collection.name}")
                except Exception:
                    pass
            
            logger.info(f"Cleanup complete: {deleted_count} collections deleted")
            return deleted_count
        except Exception as e:
            logger.warning(f"Failed to cleanup inactive collections: {e}")
            return deleted_count
    
    @staticmethod
    def cleanup_all_chroma_collections(chroma_path: str = None) -> int:
        """Delete all ChromaDB collections. Use with caution!"""
        if chroma_path is None:
            chroma_path = settings.chroma_db_dir
        
        deleted_count = 0
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            collections = client.list_collections()
            for collection in collections:
                try:
                    client.delete_collection(collection.name)
                    deleted_count += 1
                except Exception:
                    pass
            
            logger.info(f"Deleted all {deleted_count} ChromaDB collections")
            return deleted_count
        except Exception as e:
            logger.warning(f"Failed to cleanup all collections: {e}")
            return deleted_count
    


# ──────────────────────────────────────────────────────────────────────────────
# Integration Helper for JobApplicationEngine
# ──────────────────────────────────────────────────────────────────────────────

class RAGTailorIntegration:
    """
    Helper class to integrate RAG Engine with the existing JobApplicationEngine.
    Provides a drop-in replacement for the simple rag_context string approach.
    """
    
    def __init__(self, rag_engine: RAGEngine = None):
        self.rag_engine = rag_engine or RAGEngine()
        self._cache = {}
    
    def get_rag_context(
        self,
        resume_text: str,
        job_description: str,
        force_rebuild: bool = False
    ) -> str:
        """
        Get RAG-retrieved context for a given resume and job description.
        Uses caching to avoid redundant processing.
        """
        cache_key = f"{hash(resume_text)}_{hash(job_description)}"
        
        if not force_rebuild and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Run RAG pipeline
        result = self.rag_engine.full_rag_pipeline(resume_text, job_description)
        
        if result.get("success"):
            context = result["retrieved_context"]
            self._cache[cache_key] = context
            return context
        
        return ""
    
    def get_match_score(
        self,
        resume_text: str,
        job_description: str
    ) -> dict:
        """
        Get detailed match analysis between resume and job description.
        """
        result = self.rag_engine.full_rag_pipeline(resume_text, job_description)
        
        if result.get("success"):
            return {
                "score": result["match_analysis"].get("match_score", 50),
                "matched_skills": result["match_analysis"].get("matched_skills", []),
                "missing_skills": result["match_analysis"].get("missing_skills", []),
                "strengths": result["match_analysis"].get("strength_areas", []),
                "gaps": result["match_analysis"].get("gap_areas", []),
                "reason": result["match_analysis"].get("reason", ""),
                "hyde_quality": result["match_analysis"].get("hyde_relevance", 0.5),
            }
        
        return {
            "score": 50,
            "matched_skills": [],
            "missing_skills": [],
            "strengths": [],
            "gaps": [],
            "reason": "RAG analysis failed",
            "hyde_quality": 0.0,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Demo / Test
# ──────────────────────────────────────────────────────────────────────────────

def _demo():
    """Quick demonstration of the RAG Engine capabilities."""
    
    sample_resume = """
    John Doe - Software Engineer
    Email: john@example.com | Phone: +1-555-0123
    
    EXPERIENCE:
    Senior Software Engineer at TechCorp (2020-2024)
    - Developed microservices using Python, FastAPI, and Docker
    - Built React.js frontends with TypeScript and Redux
    - Implemented CI/CD pipelines using GitHub Actions
    - Managed AWS infrastructure (EC2, S3, RDS, Lambda)
    - Led team of 3 junior developers
    
    Software Developer at StartupXYZ (2018-2020)
    - Built REST APIs using Node.js and Express
    - Developed MongoDB database schemas and queries
    - Implemented authentication with JWT and OAuth2
    - Created automated testing suites with Jest and Pytest
    
    SKILLS:
    Languages: Python, JavaScript, TypeScript, SQL
    Frameworks: React, Node.js, FastAPI, Express, Django
    Cloud: AWS (EC2, S3, Lambda, RDS), GCP basics
    Tools: Docker, Kubernetes, Git, GitHub Actions, Terraform
    Databases: PostgreSQL, MongoDB, Redis
    
    EDUCATION:
    B.S. Computer Science, State University (2018)
    """
    
    sample_jd = """
    We are looking for a Full Stack Engineer to join our growing team.
    
    Requirements:
    - 3+ years of experience in software development
    - Strong proficiency in Python and JavaScript/TypeScript
    - Experience with React and Node.js or FastAPI
    - Familiarity with AWS cloud services
    - Experience with Docker and containerization
    - Knowledge of CI/CD practices
    - Database experience with SQL and NoSQL
    
    Nice to have:
    - Experience with Kubernetes
    - Knowledge of Terraform or Infrastructure as Code
    - Experience leading small teams
    """
    
    print("=" * 70)
    print("RAG ENGINE DEMO")
    print("=" * 70)
    
    # Check if API keys are available
    if not MINIMAX_API_KEY:
        print("\n[WARNING] MINIMAX_API_KEY not set. Demo will use mock responses.")
        print("Set MINIMAX_API_KEY environment variable for full functionality.\n")
    
    if not GEMINI_API_KEY:
        print("\n[WARNING] GEMINI_API_KEY not set. Embeddings will not work.")
        print("Set GEMINI_API_KEY environment variable for full functionality.\n")
    
    # Initialize RAG Engine
    rag = RAGEngine()
    
    # Run full pipeline
    result = rag.full_rag_pipeline(sample_resume, sample_jd, {"name": "John Doe"})
    
    print("\n📊 JD REQUIREMENTS EXTRACTED:")
    print(json.dumps(result.get("jd_requirements", {}), indent=2))
    
    print("\n🎯 MATCH ANALYSIS:")
    print(json.dumps(result.get("match_analysis", {}), indent=2))
    
    print("\n📝 TAILORED CONTENT:")
    for key, value in result.get("tailored_content", {}).items():
        print(f"\n--- {key.upper()} ---")
        print(value[:500] if value else "No content generated")
    
    print("\n" + "=" * 70)
    print(f"Chunks Retrieved: {result.get('chunks_retrieved', 0)}")
    print(f"HyDE Queries Used: {result.get('hyde_queries_used', 0)}")
    print("=" * 70)



# ──────────────────────────────────────────────────────────────────────────────
# Production RAG Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

class ProductionRAGOrchestrator:
    """
    High-fidelity production pipeline: RAG + Polishing + Cloudinary Upload.
    Coordinates downloading, tailoring, and re-uploading resumes.
    """
    def __init__(self, settings_obj: Any = None):
        from config.settings import settings
        self.settings = settings_obj or settings
        self.rag_engine = RAGEngine()
        self.logger = logging.getLogger("ProductionRAG")

    async def run_pipeline(self, old_cloudinary_url: str, job_info: dict[str, Any]) -> str:
        """
        Runs the full high-fidelity pipeline and returns the NEW Cloudinary URL.
        """
        try:
            # 1. Download source resume
            from utils.helpers import download_file
            import hashlib
            
            url_hash = hashlib.md5(old_cloudinary_url.encode()).hexdigest()
            temp_dir = Path(getattr(self.settings, "base_dir", ".")) / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"source_{url_hash}.pdf"
            
            self.logger.info(f"Downloading source resume for RAG: {old_cloudinary_url}")
            local_path = download_file(old_cloudinary_url, str(temp_path))
            
            # 2. Extract text for RAG indexing
            from utils.pdf_reader import extract_text_from_pdf
            resume_text = extract_text_from_pdf(local_path)
            
            # 3. Run RAG Analysis
            jd = job_info.get("description") or job_info.get("job_description") or ""
            company = job_info.get("company", "Target Company")
            
            self.logger.info(f"Running RAG tailoring for {company}...")
            # We don't strictly need the result here if the generator handles it,
            # but indexing it helps if the generator uses the engine.
            await self.rag_engine.full_rag_pipeline_async(resume_text, jd)
            
            # 4. Generate polished PDF
            from .rag_resume_generator import RAGResumeGenerator
            # Use a dummy student_id or resolve from context if possible
            student_id = job_info.get("student_id", "prod_user")
            generator = RAGResumeGenerator(logger=self.logger, student_id=student_id)
            
            # Note: generator.get_tailed_resume is sync but uses LLM?
            # Actually, RAGResumeGenerator.get_tailed_resume is often sync with internal async calls
            # (Check the file to see if it needs await)
            tailored_pdf_path = generator.get_tailed_resume(jd, company)
            
            if not tailored_pdf_path or not Path(tailored_pdf_path).exists():
                self.logger.warning("Tailored PDF generation failed, returning original URL")
                return old_cloudinary_url
                
            # 5. Upload to Cloudinary
            from utils.role_resume_manager import upload_to_cloudinary
            self.logger.info("Uploading tailored resume to Cloudinary...")
            new_url, _ = upload_to_cloudinary(tailored_pdf_path, folder="tailored_resumes")
            
            return new_url
            
        except Exception as e:
            self.logger.error(f"Production RAG Pipeline failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return old_cloudinary_url

if __name__ == "__main__":
    _demo()
