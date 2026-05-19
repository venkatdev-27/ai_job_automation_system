from __future__ import annotations

import html
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

SKILL_ALIASES = {
    "react": "react.js",
    "reactjs": "react.js",
    "node": "node.js",
    "nodejs": "node.js",
    "js": "javascript",
    "ts": "typescript",
    "dotnet": ".net",
    "asp.net": ".net",
    "asp.net core": ".net",
    "restful api": "rest api",
    "restful apis": "rest api",
    "postgres": "postgresql",
    "mongo": "mongodb",
}

DEFAULT_SKILL_VOCAB = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react.js",
    "node.js",
    ".net",
    "sql",
    "mongodb",
    "postgresql",
    "mysql",
    "rest api",
    "html",
    "css",
    "django",
    "flask",
    "spring boot",
    "azure",
    "aws",
    "git",
    "docker",
    "kubernetes",
    "redis",
    "machine learning",
    "data analysis",
}

SENIOR_HINTS = {
    "senior",
    "lead",
    "staff",
    "principal",
    "architect",
    "manager",
    "director",
    "head of",
    "consultant",
}

FRESHER_HINTS = {
    "fresher",
    "entry level",
    "entry-level",
    "graduate",
    "0-1",
    "0 to 1",
    "0 - 1",
    "0-2",
    "intern",
    "internship",
    "junior",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "you",
    "your",
    "will",
    "this",
    "that",
    "from",
    "our",
    "are",
    "have",
    "has",
    "job",
    "role",
    "work",
    "team",
    "skills",
    "experience",
    "years",
    "year",
    "candidate",
    "required",
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = raw
    try:
        from bs4 import BeautifulSoup

        text = BeautifulSoup(raw, "html.parser").get_text(" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return normalize_whitespace(text)


def normalize_skill(skill: str) -> str:
    token = normalize_whitespace(skill).lower()
    token = token.replace("/", " ")
    token = token.strip(" -_.,;:()[]{}")
    if token in SKILL_ALIASES:
        return SKILL_ALIASES[token]
    return token


def normalize_skills(skills: list[str]) -> list[str]:
    normalized = [normalize_skill(skill) for skill in skills if normalize_skill(skill)]
    deduped: list[str] = []
    seen: set[str] = set()
    for skill in normalized:
        if skill in seen:
            continue
        seen.add(skill)
        deduped.append(skill)
    return deduped


def extract_skills(text: str, extra_vocab: list[str] | None = None) -> list[str]:
    content = f" {text.lower()} "
    vocab = set(DEFAULT_SKILL_VOCAB)
    for token in extra_vocab or []:
        if token:
            vocab.add(normalize_skill(token))

    matched: list[str] = []
    for raw_skill in sorted(vocab):
        if not raw_skill:
            continue
        pattern = rf"(?<!\w){re.escape(raw_skill)}(?!\w)"
        if re.search(pattern, content):
            matched.append(raw_skill)
    return matched


def infer_role_category(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("frontend", "react", "angular", "ui", "javascript")):
        return "frontend"
    if any(keyword in lowered for keyword in ("backend", "api", "django", "spring", "node", "database")):
        return "backend"
    if any(keyword in lowered for keyword in ("full stack", "fullstack")):
        return "full-stack"
    if any(keyword in lowered for keyword in ("machine learning", "data scientist", "ai", "nlp")):
        return "ai-ml"
    if any(keyword in lowered for keyword in (".net", "asp.net", "c#")):
        return ".net"
    return "software"


def classify_job_type(text: str) -> str:
    lowered = text.lower()
    if "intern" in lowered:
        return "internship"
    if any(keyword in lowered for keyword in ("full time", "full-time", "permanent")):
        return "full-time"
    return "unknown"


def parse_experience_range(text: str) -> tuple[int, int, str]:
    lowered = text.lower()
    normalized = lowered.replace("yrs", "years").replace("yr", "year")
    patterns = [
        r"(\d+)\s*[-to]+\s*(\d+)\s*\+?\s*years?",
        r"(\d+)\s*\+\s*years?",
        r"minimum\s*(\d+)\s*years?",
        r"(\d+)\s*years?",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        groups = match.groups()
        if len(groups) >= 2 and groups[1]:
            minimum = int(groups[0])
            maximum = int(groups[1])
        else:
            minimum = int(groups[0])
            maximum = minimum
            if "+" in match.group(0):
                maximum = minimum + 10
        return minimum, maximum, match.group(0)

    if any(hint in normalized for hint in FRESHER_HINTS):
        return 0, 1, "fresher"

    return 0, 99, ""


def is_senior_title(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in SENIOR_HINTS)


def is_fresher_friendly(text: str, max_experience: int = 1) -> bool:
    min_exp, _, _ = parse_experience_range(text)
    lowered = text.lower()
    if is_senior_title(lowered):
        return False
    if min_exp > max_experience:
        return False
    if any(hint in lowered for hint in FRESHER_HINTS):
        return True
    return min_exp <= max_experience


def normalize_location(value: str) -> str:
    return normalize_whitespace(value).lower()


def location_score(location: str, preferred_locations: list[str]) -> float:
    normalized = normalize_location(location)
    if not normalized:
        return 0.0
    preferred = [normalize_location(item) for item in preferred_locations]
    if any(token == normalized for token in preferred):
        return 1.0
    if any(token in normalized for token in preferred):
        return 0.85
    if "remote" in normalized and any("remote" in token for token in preferred):
        return 1.0
    return 0.0


def _tokenize_title(title: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9+.# ]+", " ", title.lower())
    return {token for token in cleaned.split() if token and token not in STOPWORDS}


def semantic_title_similarity(title: str, candidate_titles: list[str]) -> float:
    if not title or not candidate_titles:
        return 0.0
    title_tokens = _tokenize_title(title)
    best = 0.0

    for candidate_title in candidate_titles:
        candidate_tokens = _tokenize_title(candidate_title)
        token_overlap = 0.0
        if title_tokens and candidate_tokens:
            intersection = len(title_tokens.intersection(candidate_tokens))
            union = len(title_tokens.union(candidate_tokens))
            if union:
                token_overlap = intersection / union

        sequence_score = SequenceMatcher(None, title.lower(), candidate_title.lower()).ratio()
        score = (0.65 * token_overlap) + (0.35 * sequence_score)
        if score > best:
            best = score
    return round(best, 4)


def top_keywords(text: str, limit: int = 10) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{2,}", text.lower())
    filtered = [token for token in tokens if token not in STOPWORDS]
    if not filtered:
        return []
    return [token for token, _ in Counter(filtered).most_common(limit)]


def normalize_url(url: str, base_url: str | None = None) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if base_url:
        value = urljoin(base_url, value)
    parts = urlsplit(value)
    query = parts.query
    for noisy_param in ("utm_source", "utm_medium", "utm_campaign", "src"):
        query = re.sub(rf"(^|&){re.escape(noisy_param)}=[^&]*", "", query)
    query = query.strip("&")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def normalize_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(job)
    normalized["title"] = normalize_whitespace(str(job.get("title", "")))
    normalized["company"] = normalize_whitespace(str(job.get("company", "")))
    normalized["location"] = normalize_whitespace(str(job.get("location", "")))
    normalized["description"] = normalize_whitespace(str(job.get("description", "")))
    normalized["url"] = normalize_url(str(job.get("url", "")))
    normalized["required_skills"] = normalize_skills(
        [str(skill) for skill in job.get("required_skills", []) if str(skill).strip()]
    )

    combined_text = " ".join(
        [
            normalized.get("title", ""),
            normalized.get("description", ""),
            normalized.get("experience_text", ""),
            normalized.get("employment_type", ""),
        ]
    )
    if not normalized["required_skills"]:
        normalized["required_skills"] = extract_skills(combined_text)

    if not normalized.get("role_category"):
        normalized["role_category"] = infer_role_category(combined_text)
    if not normalized.get("employment_type"):
        normalized["employment_type"] = classify_job_type(combined_text)

    min_exp, max_exp, raw_exp = parse_experience_range(combined_text)
    normalized["experience_min"] = int(job.get("experience_min", min_exp))
    normalized["experience_max"] = int(job.get("experience_max", max_exp))
    normalized["experience_text"] = normalize_whitespace(str(job.get("experience_text", raw_exp)))

    return normalized

