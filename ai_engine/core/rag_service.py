import os
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

# LangChain imports
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("RAGService")

class RAGService:
    """
    RAG Service for AI Engine:
    - ChromaDB for vector storage
    - Gemini embeddings
    - Fact-only retrieval from master resumes
    """
    _INSTANCE = None
    _EMBEDDINGS = None

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if self.gemini_key:
            os.environ["GOOGLE_API_KEY"] = self.gemini_key
        
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/app/ai_engine/cache/chroma_db")
        os.makedirs(self.persist_dir, exist_ok=True)
        
        self.embeddings = self._get_embeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        self.vectorstore = None

    def _get_embeddings(self):
        if RAGService._EMBEDDINGS is None and self.gemini_key:
            RAGService._EMBEDDINGS = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001"
            )
        return RAGService._EMBEDDINGS

    @classmethod
    def get_instance(cls):
        if cls._INSTANCE is None:
            cls._INSTANCE = RAGService()
        return cls._INSTANCE

    def index_resume(self, text: str, student_id: str):
        """Index student resume text into ChromaDB."""
        if not text or not self.embeddings:
            return False
            
        content_hash = hashlib.md5(text.encode()).hexdigest()
        collection_name = f"res_{student_id}_{content_hash[:8]}"
        
        try:
            self.vectorstore = Chroma(
                persist_directory=self.persist_dir,
                collection_name=collection_name,
                embedding_function=self.embeddings
            )
            
            # Check if already indexed
            if self.vectorstore.get()["ids"]:
                logger.info(f"Resume already indexed for {student_id}")
                return True
                
            chunks = self.text_splitter.split_text(text)
            self.vectorstore.add_texts(
                texts=chunks,
                metadatas=[{"student_id": student_id, "source": "master_resume"}]
            )
            logger.info(f"Indexed {len(chunks)} chunks for {student_id}")
            return True
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return False

    async def retrieve_context(self, query: str, student_id: str, k: int = 5) -> str:
        """Retrieve relevant facts from the indexed resume."""
        if not self.vectorstore:
            logger.warning("No vectorstore available for retrieval")
            return ""
            
        try:
            docs = await asyncio.to_thread(
                self.vectorstore.similarity_search,
                query=query,
                k=k
            )
            return "\n\n".join([doc.page_content for doc in docs])
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return ""
