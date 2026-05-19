import re
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "of", "on", "or", "the", "this", "to",
    "what", "with", "you", "your"
}

def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

def get_tokens(text: str) -> Set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", str(text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    clean = compact_text(text)
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks

def retrieve_field_relevant_chunks(query: str, texts: List[str], limit: int = 5) -> List[str]:
    """
    Field-specific RAG from v2: Uses token overlap to find precise context for a form question.
    """
    query_tokens = get_tokens(query)
    if not query_tokens:
        return []

    scored = []
    for text in texts:
        if not text:
            continue
        for chunk in chunk_text(text):
            chunk_tokens = get_tokens(chunk)
            if not chunk_tokens:
                continue
            score = len(query_tokens & chunk_tokens)
            if score:
                scored.append((score, len(chunk_tokens), chunk))

    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [chunk for _, _, chunk in scored[:limit]]

def build_field_payload(
    label: str,
    field_type: str = "",
    options: list | None = None,
    input_type: str = "",
) -> dict:
    """
    Mirrors v2 _build_field_payload for consistent field normalization.
    """
    normalized_type = compact_text(field_type).lower()
    if normalized_type in {"select", "combobox", "listbox"}:
        normalized_type = "dropdown"
    if normalized_type in {"input", ""}:
        normalized_type = "text"
    if normalized_type == "number":
        normalized_type = "text"
    
    in_type = compact_text(input_type).lower()
    if in_type == "checkbox":
        normalized_type = "checkbox"
    elif in_type == "radio":
        normalized_type = "radio"
        
    return {
        "label": compact_text(label),
        "type": normalized_type,
        "input_type": in_type,
        "options": options or [],
    }

def is_placeholder_option(option_text: str) -> bool:
    text = compact_text(option_text).lower()
    if not text:
        return True
    if re.fullmatch(r"[-–—\s]{2,}", text):
        return True
    known_placeholders = {
        "select", "select option", "select an option", "choose", "choose option",
        "choose an option", "please select", "please make a selection",
        "make a selection", "--select--", "-select-", "default",
    }
    if text in known_placeholders:
        return True
    if text.startswith("select ") and len(text) <= 40:
        return True
    if text.startswith("choose ") and len(text) <= 40:
        return True
    if "make a selection" in text:
        return True
    return False

def get_real_options(options: List[str]) -> List[str]:
    cleaned = [compact_text(opt) for opt in (options or []) if compact_text(opt)]
    non_placeholder = [opt for opt in cleaned if not is_placeholder_option(opt)]
    return non_placeholder or cleaned

def fuzzy_match_option(selection: str, options: List[str]) -> str:
    """
    Fuzzy matching ported from v2 _click_option_by_text logic.
    """
    wanted = compact_text(selection).lower()
    if not wanted:
        return options[0] if options else ""
    
    real_opts = get_real_options(options)
    
    best = None
    for opt in real_opts:
        lower = opt.lower()
        if lower == wanted:
            return opt # Exact match priority
        if wanted in lower or lower in wanted:
            best = best or opt
            
    return best or (real_opts[0] if real_opts else "")
