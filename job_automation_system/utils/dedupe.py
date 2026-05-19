from __future__ import annotations

import hashlib
from typing import Any

from utils.job_utils import normalize_url


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def canonical_job_key(job: dict[str, Any]) -> str:
    normalized_url = normalize_url(_clean(job.get("url")))
    raw = "|".join(
        [
            _clean(job.get("source")),
            _clean(job.get("title")),
            _clean(job.get("company")),
            _clean(job.get("location")),
            normalized_url,
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for job in jobs:
        key = canonical_job_key(job)
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)

    return unique
