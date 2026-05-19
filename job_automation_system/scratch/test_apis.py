import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from config import settings
import requests

def test_groq():
    print(f"Testing Groq API with key: {settings.groq_api_key[:10]}...")
    
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "user", "content": "Hello, are you working?"}
        ],
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("[SUCCESS] Groq API is WORKING!")
            print(f"Response: {response.json()['choices'][0]['message']['content']}")
        else:
            print(f"[FAILED] Groq API FAILED with status {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"[ERROR] Groq API Error: {e}")

def test_gemini():
    print(f"Testing Gemini API with key: {settings.gemini_api_key[:10]}...")
    # Gemini embeddings test
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vector = embeddings.embed_query("Hello world")
        print(f"[SUCCESS] Gemini Embeddings are WORKING! (Vector size: {len(vector)})")
    except Exception as e:
        print(f"[ERROR] Gemini Embeddings FAILED: {e}")

if __name__ == "__main__":
    test_groq()
    print("-" * 30)
    test_gemini()
