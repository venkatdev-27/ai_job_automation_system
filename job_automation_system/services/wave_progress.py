"""
Student Wave Progress
=====================
Stores compact per-student/per-schedule progress in Redis for monitoring and
recovery decisions.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from services.redis_client import redis_client


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def wave_key(student_id: str, schedule_name: str, date: str | None = None) -> str:
    return f"wave:{date or _today()}:{schedule_name}:{student_id}"


def update_wave_progress(
    student_id: str,
    schedule_name: str,
    platform: str,
    target: int,
    applied: int,
    skipped: int = 0,
    failed: int = 0,
    status: str = "unknown",
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "platform": platform,
        "target": int(target or 0),
        "applied": int(applied or 0),
        "skipped": int(skipped or 0),
        "failed": int(failed or 0),
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if error:
        payload["error"] = str(error)[:500]

    key = wave_key(student_id, schedule_name)
    redis_client.client.hset(key, platform, json.dumps(payload, sort_keys=True))
    redis_client.client.expire(key, 86400 * 7)


def finalize_wave_progress(
    student_id: str,
    schedule_name: str,
    status: str,
    summary: dict[str, Any],
) -> None:
    key = wave_key(student_id, schedule_name)
    redis_client.client.hset(
        key,
        "_summary",
        json.dumps(
            {
                "status": status,
                "summary": summary,
                "updated_at": datetime.utcnow().isoformat(),
            },
            sort_keys=True,
        ),
    )
    redis_client.client.expire(key, 86400 * 7)


def get_incomplete_students(schedule_name: str, date: str | None = None) -> list[str]:
    date_str = date or _today()
    pattern = f"wave:{date_str}:{schedule_name}:*"
    keys = redis_client.client.keys(pattern)
    if not keys:
        return []

    incomplete = []
    for key in keys:
        key_str = key.decode() if isinstance(key, bytes) else key
        parts = key_str.split(":")
        if len(parts) >= 4:
            student_id = parts[3]
            summary_raw = redis_client.client.hget(key, "_summary")
            if not summary_raw:
                incomplete.append(student_id)
            else:
                try:
                    summary_data = json.loads(summary_raw.decode() if isinstance(summary_raw, bytes) else summary_raw)
                    if summary_data.get("status") != "completed":
                        incomplete.append(student_id)
                except (json.JSONDecodeError, TypeError):
                    incomplete.append(student_id)
    return incomplete
