#!/usr/bin/env python3
"""
Generate 5-6 Role PDFs from Yamuna's DOCX Resume
================================================
Uses AI Engine API to generate role-specific resumes.
Names PDFs by role only (frontend.pdf, backend.pdf, etc.)
"""

import asyncio
import os
import sys
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# Install mammoth if not available
try:
    import mammoth
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mammoth", "-q"])
    import mammoth

# Setup path
PROJECT_ROOT = Path("D:/ai-bot-resumes/job_automation_system")
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT.parent / "backend" / ".env")

# Role configurations
ROLE_CONFIGS = {
    "frontend": {
        "title": "Frontend Developer",
        "jd": """Job Title: Frontend Developer
Required Skills: React, JavaScript, TypeScript, HTML, CSS, Angular, Vue, Redux, Bootstrap, Tailwind CSS
Experience: 1-3 years
Focus: UI development, responsive design, modern JavaScript frameworks"""
    },
    "backend": {
        "title": "Backend Developer",
        "jd": """Job Title: Backend Developer
Required Skills: Node.js, Python, Java, SQL, MongoDB, Express, REST API, GraphQL, PostgreSQL, Docker
Experience: 1-3 years
Focus: API development, database management, server-side architecture"""
    },
    "fullstack": {
        "title": "Full Stack Developer",
        "jd": """Job Title: Full Stack Developer (MERN)
Required Skills: React, Node.js, MongoDB, Express, JavaScript, TypeScript, REST API, AWS, Docker
Experience: 1-3 years
Focus: End-to-end web development, full stack technologies"""
    },
    "java": {
        "title": "Java Developer",
        "jd": """Job Title: Java Developer
Required Skills: Java, Spring Boot, Hibernate, SQL, Microservices, JDBC, JPA, Maven, REST API, MySQL
Experience: 1-3 years
Focus: Enterprise applications, backend development with Java"""
    },
    "python": {
        "title": "Python Developer",
        "jd": """Job Title: Python Developer
Required Skills: Python, Django, Flask, Pandas, SQL, API, Machine Learning, NumPy, SQLAlchemy, FastAPI
Experience: 1-3 years
Focus: Web development, data processing, Python frameworks"""
    },
    "data_engineer": {
        "title": "Data Engineer",
        "jd": """Job Title: Data Engineer
Required Skills: Python, SQL, ETL, Spark, Hadoop, Airflow, PostgreSQL, MongoDB, AWS, Data Pipeline, Kafka
Experience: 1-3 years
Focus: Data pipelines, ETL processes, big data technologies"""
    }
}

# Paths
YAMUNA_DOCX = "D:/ai-bot-resumes/backend/uploads/1775133653220-yamuna_peddi.docx"
OUTPUT_DIR = Path("D:/ai-bot-resumes/ai_engine/resumes")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_URL = f"{os.getenv('LOCAL_API_URL', 'http://localhost:8000').rstrip('/')}/generate"


def extract_docx_text(docx_path: str) -> str:
    """Extract text from DOCX file"""
    try:
        import mammoth
        with open(docx_path, "rb") as docx_file:
            result = mammoth.extract_raw_text(docx_file)
            return result.value
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
        return ""


def generate_resume_via_api(retrieved_chunks: str, job_description: str, role_key: str) -> dict:
    """Call AI Engine API to generate resume"""
    print(f"  Calling API for role: {role_key}...")
    
    try:
        response = requests.post(
            API_URL,
            json={
                "retrievedChunks": retrieved_chunks,
                "jobDescription": job_description,
                "disableCache": False,
                "refreshCache": True
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  [OK] {role_key} - Score: {result.get('score', 'N/A')}")
            return result
        else:
            print(f"  [ERROR] {role_key} - Status: {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] {role_key} - Cannot connect to API server (port 8000)")
        return None
    except Exception as e:
        print(f"  [ERROR] {role_key} - {e}")
        return None


async def main():
    print("=" * 70)
    print("GENERATING 5-6 ROLE PDFs FROM YAMUNA'S RESUME")
    print("=" * 70)
    
    # Step 1: Extract text from DOCX
    print(f"\n[1] Extracting text from DOCX: {YAMUNA_DOCX}")
    resume_text = extract_docx_text(YAMUNA_DOCX)
    
    if not resume_text:
        print("ERROR: Could not extract text from DOCX")
        return 1
    
    print(f"  Extracted {len(resume_text)} characters")
    
    # Step 2: Generate PDF for each role
    print(f"\n[2] Generating PDFs for {len(ROLE_CONFIGS)} roles...")
    
    results = {}
    for role_key, config in ROLE_CONFIGS.items():
        print(f"\n  --- Processing: {config['title']} ---")
        
        # Call API
        result = generate_resume_via_api(
            resume_text,
            config["jd"],
            role_key
        )
        
        if result and result.get("pdfPath"):
            pdf_path = result["pdfPath"]
            
            # Rename to role-only name
            new_name = f"{role_key}.pdf"
            new_path = OUTPUT_DIR / new_name
            
            # Copy/rename file
            if os.path.exists(pdf_path):
                import shutil
                shutil.copy2(pdf_path, new_path)
                print(f"  Saved: {new_path}")
                results[role_key] = {"success": True, "path": str(new_path), "score": result.get("score")}
            else:
                print(f"  [ERROR] PDF not found at: {pdf_path}")
                results[role_key] = {"success": False, "error": "PDF not generated"}
        else:
            print(f"  [FAILED] {role_key}")
            results[role_key] = {"success": False, "error": "API call failed"}
    
    # Step 3: Summary
    print("\n" + "=" * 70)
    print("GENERATION SUMMARY")
    print("=" * 70)
    
    success_count = sum(1 for r in results.values() if r.get("success"))
    
    for role_key, result in results.items():
        status = "SUCCESS" if result.get("success") else "FAILED"
        score = result.get("score", "")
        path = result.get("path", "")
        print(f"  {role_key}: {status} {f'(Score: {score})' if score else ''}")
        if path:
            print(f"    -> {path}")
    
    print(f"\nTotal: {success_count}/{len(ROLE_CONFIGS)} roles generated successfully")
    
    # Check if API server is running
    if success_count == 0:
        print("\n" + "=" * 70)
        print("IMPORTANT: API Server is not running!")
        print("To start it, run: python ai_engine/api/main.py")
        print("=" * 70)
    
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
