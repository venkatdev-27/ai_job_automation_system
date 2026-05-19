import re
import html
from ai_engine.config import STOPWORDS
from ai_engine.utils.regex_patterns import EMPTY_HTML_P

def squash_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def clean_text(text):
    if not text:
        return ""
    # Support for list inputs (v2 robustness)
    if isinstance(text, list):
        text = "\n".join([str(t) for t in text if t])
    
    replacements = {
        "Ã¢â‚¬â€œ": "-", "Ã¢â‚¬â€ ": "-", "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Å“": '"', "Ã¢â‚¬?": '"', "â€¢": "",
        "Ã¢â‚¬Â¢": "", "\u00e2\u20ac\u201c": "-", "\u00e2\u20ac\u201d": "-",
        "&nbsp;": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def normalize_text_for_match(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())

def count_words(text):
    return len(re.findall(r"\b[\w.+#/-]+\b", str(text or "")))

def strip_tags(text):
    return squash_spaces(re.sub(r"<[^>]+>", " ", str(text or "")))

def dedupe_preserve_order(items):
    unique = []
    seen = set()
    for item in items:
        key = normalize_text_for_match(item)
        if not item or not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique

def remove_empty_html_elements(resume_text):
    previous = None
    cleaned = resume_text
    while cleaned != previous:
        previous = cleaned
        cleaned = EMPTY_HTML_P.sub("", cleaned)
    return cleaned

def split_source_lines(text):
    return [squash_spaces(line) for line in re.split(r"[\r\n]+", str(text or "")) if squash_spaces(line)]

def strip_markdown_code_fences(text):
    if not text:
        return ""
    text = re.sub(r"^```\w*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n```$", "", text, flags=re.MULTILINE)
    return text.strip()
