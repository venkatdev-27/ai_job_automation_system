import requests
import json
import logging
import time
import random
import socket
import os
from ai_engine.config import GROQ_API_KEY, DEFAULT_PRIMARY_MODEL, DEFAULT_FALLBACK_MODELS
from ai_engine.utils.text_processing import squash_spaces

logger = logging.getLogger("ai_engine.llm_client")

# DNS fallback settings
DNS_RESOLVER_TIMEOUT = 5
DNS_RETRIES = 3

# Connection pool settings
_session = None
_http2_client = None
_httpx_client = None
_httpx_client_loop = None
_async_llm_semaphore = None


def _get_async_llm_semaphore():
    global _async_llm_semaphore
    if _async_llm_semaphore is None:
        import asyncio
        max_concurrency = max(1, int(os.getenv("LLM_MAX_CONCURRENCY", "4")))
        _async_llm_semaphore = asyncio.Semaphore(max_concurrency)
    return _async_llm_semaphore

def get_session():
    """Get or create a requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # We handle retries manually
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session

async def _get_httpx_client():
    """Get one shared AsyncClient per event loop to avoid per-call socket churn."""
    global _httpx_client, _httpx_client_loop
    import asyncio
    import httpx

    current_loop = asyncio.get_running_loop()
    if (
        _httpx_client is None
        or _httpx_client.is_closed
        or _httpx_client_loop is not current_loop
    ):
        if _httpx_client is not None and not _httpx_client.is_closed:
            try:
                await _httpx_client.aclose()
            except Exception as exc:
                logger.warning(f"Failed to close old async LLM HTTP client: {exc}")

        _httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        _httpx_client_loop = current_loop
    return _httpx_client

async def close_llm_clients():
    """Close shared HTTP clients during service shutdown."""
    global _httpx_client, _httpx_client_loop, _session
    if _httpx_client is not None and not _httpx_client.is_closed:
        try:
            await _httpx_client.aclose()
        finally:
            _httpx_client = None
            _httpx_client_loop = None
    if _session is not None:
        _session.close()
        _session = None

async def _resolve_with_fallback(hostname):
    """Try to resolve hostname with fallback DNS servers."""
    import asyncio
    for attempt in range(DNS_RETRIES):
        try:
            socket.setdefaulttimeout(DNS_RESOLVER_TIMEOUT)
            result = socket.getaddrinfo(hostname, None)
            return result
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {hostname}: {e}")
            if attempt < DNS_RETRIES - 1:
                await asyncio.sleep(1)
    return None

async def async_groq_llm_call(prompt, model=DEFAULT_PRIMARY_MODEL, system_prompt="You are a helpful assistant.", max_retries=5):
    """v3 Optimization: Parallel LLM capability using httpx with DNS fallback and connection pooling."""
    if not GROQ_API_KEY:
        logger.error("No GROQ_API_KEY found in environment.")
        return None
    
    import asyncio
    
    async with _get_async_llm_semaphore():
        # DNS error counter for logging
        dns_errors = 0
        client = await _get_httpx_client()
        
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0
                    }
                )
                
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
                
                if response.status_code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit ({model}). Waiting {wait:.2f}s...")
                    await asyncio.sleep(wait)
                    continue
                
                logger.error(f"Groq API Error {response.status_code}: {response.text}")
                if response.status_code >= 500:
                    await asyncio.sleep(2 + random.uniform(0, 1))
                    continue
                return None
                    
            except Exception as e:
                error_str = str(e).lower()
                if 'connect' in error_str or 'getaddrinfo' in error_str or 'name or service not known' in error_str:
                    dns_errors += 1
                    logger.warning(f"Connection/DNS error in LLM call (attempt {attempt + 1}/{max_retries}): {e}")
                else:
                    logger.error(f"Groq Async Call failed: {str(e)}")
                await asyncio.sleep(2 + random.uniform(0, 1))
        
        if dns_errors > 0:
            logger.warning(f"Total DNS errors encountered: {dns_errors}")
    return None

def groq_llm_call(prompt, model=DEFAULT_PRIMARY_MODEL, system_prompt="You are a helpful assistant.", max_retries=5):
    """Synchronous LLM call with connection pooling and DNS error handling."""
    if not GROQ_API_KEY:
        logger.error("No GROQ_API_KEY found in environment.")
        return None
    
    session = get_session()
    dns_errors = 0
    
    for attempt in range(max_retries):
        try:
            response = session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            
            if response.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limit hit ({model}). Waiting {wait:.2f}s...")
                time.sleep(wait)
                continue
            
            logger.error(f"Groq API Error {response.status_code}: {response.text}")
            if response.status_code >= 500:
                time.sleep(2)
                continue
            return None
                
        except requests.exceptions.ConnectionError as e:
            error_str = str(e).lower()
            if 'getaddrinfo' in error_str or 'name or service not known' in error_str:
                dns_errors += 1
                logger.warning(f"DNS resolution failed (attempt {attempt + 1}/{max_retries}): {e}")
            else:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(2 + random.uniform(0, 1))
        except Exception as e:
            error_str = str(e).lower()
            if 'getaddrinfo' in error_str or 'name or service not known' in error_str:
                dns_errors += 1
                logger.warning(f"DNS error in LLM call: {e}")
            else:
                logger.error(f"Groq Call failed: {str(e)}")
            time.sleep(2)
    
    if dns_errors > 0:
        logger.warning(f"Total DNS errors encountered: {dns_errors}")
    return None

def get_model_sequence(primary_model=None, fallback_models=None):
    primary = primary_model or DEFAULT_PRIMARY_MODEL
    fallbacks = fallback_models or DEFAULT_FALLBACK_MODELS
    ordered = []
    for m in [primary] + (fallbacks if isinstance(fallbacks, list) else fallbacks.split(',')):
        m = squash_spaces(m)
        if m and m not in ordered:
            ordered.append(m)
    return ordered

async def groq_llm_call_with_fallback_async(prompt, model=None, system_prompt="You are a helpful assistant.", max_retries=5, fallback_models=None):
    tried_models = []
    for candidate_model in get_model_sequence(primary_model=model, fallback_models=fallback_models):
        tried_models.append(candidate_model)
        result = await async_groq_llm_call(prompt, model=candidate_model, system_prompt=system_prompt, max_retries=max_retries)
        if result:
            return result, candidate_model, tried_models
    return None, None, tried_models

def groq_llm_call_with_fallback(prompt, model=None, system_prompt="You are a helpful assistant.", max_retries=5, fallback_models=None):
    tried_models = []
    for candidate_model in get_model_sequence(primary_model=model, fallback_models=fallback_models):
        tried_models.append(candidate_model)
        result = groq_llm_call(prompt, model=candidate_model, system_prompt=system_prompt, max_retries=max_retries)
        if result:
            return result, candidate_model, tried_models
    return None, None, tried_models

def parse_llm_json_response(raw_text):
    text = str(raw_text or "").strip()
    if not text: raise ValueError("Empty response")
    
    # v3 Robust Sanitizer: Strip C-style (//) and Block (/* */) comments
    import re
    text = re.sub(r"(?<!:)//.*", "", text) # Strip comments but preserve URLs like https://
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL) # Multi-line strip
    
    logger.info(f"CLEANED TEXT FOR PARSING Snippet: {text[:300]}...")
    
    # Try direct parse
    try: return json.loads(text)
    except Exception as e:
        logger.warning(f"Direct JSON parse failed: {e}")
        pass

    # Try code block extraction
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        try: return json.loads(match.group(1).strip())
        except: pass

    # Try raw decode find
    decoder = json.JSONDecoder()
    start = text.find("{")
    if start != -1:
        try:
            res, _ = decoder.raw_decode(text[start:])
            return res
        except: pass
    
    raise ValueError("Could not parse JSON from LLM response")
