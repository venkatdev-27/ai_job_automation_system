import json
import re
import time
import random
import requests
from datetime import datetime
from .config import GROQ_API_KEY, GROQ_API_BASE, GROQ_MODEL, OPENROUTER_API_KEY, OPENROUTER_MODEL, C

def log(msg, color=C.CYAN):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}{C.BOLD}[{ts}]{C.RESET} {color}{msg}{C.RESET}", flush=True)

def log_warn(msg): log(f"[WARN] {msg}", C.YELLOW)
def log_err(msg):  log(f"[ERR] {msg}", C.RED)

def groq_call(prompt: str, system: str = "You are an expert resume and career assistant.", max_retries: int = 3) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{GROQ_API_BASE}/chat/completions",
                headers=headers,
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                },
                timeout=60
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                log_warn(f"Rate limit. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            log_err(f"Groq API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            log_err(f"Groq call failed: {e}")
            time.sleep(2)
    return ""

def openrouter_call(
    prompt: str,
    system: str = "You are a specialized AI assistant that reasons through complex form-filling tasks.",
    max_retries: int = 3,
    max_tokens: int = 1200,
) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Antigravity Assistant"
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1, # Low temperature for factual consistency
                    "max_tokens": max(128, int(max_tokens)),
                },
                timeout=60
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                log_warn(f"OpenRouter Rate limit. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            log_err(f"OpenRouter API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            log_err(f"OpenRouter call failed: {e}")
            time.sleep(2)
    return ""

def parse_json_from_llm(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    # Try direct
    try:
        return json.loads(text)
    except:
        pass
    # Try code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except:
            pass
    # Try find first { }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except:
            pass
    return {}
