from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Mapping


def _is_docker() -> bool:
    return os.getenv("IN_DOCKER", "").lower() == "true" or Path("/app").exists()


def _raw_path_values(result: Mapping[str, Any] | str | None) -> list[str]:
    if not result:
        return []
    if isinstance(result, str):
        return [result]

    preferred = (
        ["containerPath", "pdfPath", "hostPath"]
        if _is_docker()
        else ["pdfPath", "hostPath", "containerPath"]
    )
    values: list[str] = []
    for key in preferred:
        value = result.get(key)
        if value:
            values.append(str(value))
    return values


def _mapped_candidates(raw_path: str) -> Iterable[Path]:
    normalized = raw_path.replace("\\", "/")
    yield Path(raw_path)

    mappings = [
        (
            "/app/ai_engine/resumes",
            os.getenv("RESUMES_DIR", "D:/ai-bot-resumes/ai_engine/resumes"),
        ),
        (
            "D:/ai-bot-resumes/ai_engine/resumes",
            os.getenv("RESUMES_DIR", "/app/ai_engine/resumes" if _is_docker() else "D:/ai-bot-resumes/ai_engine/resumes"),
        ),
        (
            "/app/temp_resumes",
            os.getenv("TEMP_RESUMES_DIR", "D:/ai-bot-resumes/temp_resumes"),
        ),
        (
            "D:/ai-bot-resumes/temp_resumes",
            os.getenv("TEMP_RESUMES_DIR", "/app/temp_resumes" if _is_docker() else "D:/ai-bot-resumes/temp_resumes"),
        ),
    ]

    for source_root, target_root in mappings:
        source = source_root.rstrip("/")
        if normalized.lower().startswith(source.lower() + "/"):
            suffix = normalized[len(source) :].lstrip("/")
            yield Path(target_root) / Path(*suffix.split("/"))


def resolve_ai_engine_pdf_path(result: Mapping[str, Any] | str | None) -> Path | None:
    """Resolve an AI-engine PDF response to a path visible in this process."""
    seen: set[str] = set()
    for raw_path in _raw_path_values(result):
        for candidate in _mapped_candidates(raw_path):
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
    return None
