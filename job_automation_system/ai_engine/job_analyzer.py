from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from utils.job_utils import (
    extract_skills,
    infer_role_category,
    location_score,
    parse_experience_range,
    semantic_title_similarity,
    top_keywords,
)


@dataclass
class JobAnalysis:
    top_skills: list[str]
    required_tools: list[str]
    experience_expectation: str
    experience_min: int
    experience_max: int
    role_category: str
    ats_keywords: list[str]
    role_profile: str
    priority_skills: list[str]
    title_similarity: float
    skill_match_score: float
    location_match_score: float
    domain_alignment: bool
    match_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JobAnalyzer:
    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger

    def analyze(self, job: dict[str, Any], profile: Any) -> JobAnalysis:
        title = str(job.get("title", ""))
        company = str(job.get("company", ""))
        location = str(job.get("location", ""))
        description = str(job.get("description", ""))
        role_category = str(job.get("role_category", "")) or infer_role_category(f"{title} {description}")

        required_skills = [str(skill).lower() for skill in job.get("required_skills", []) if str(skill).strip()]
        if not required_skills:
            required_skills = extract_skills(
                f"{title} {description}",
                extra_vocab=[*profile.skills, *self.settings.include_keywords],
            )

        ats_keywords = top_keywords(f"{title} {description}", limit=12)
        experience_min, experience_max, experience_expectation = parse_experience_range(
            f"{title} {description} {job.get('experience_text', '')}"
        )

        title_similarity = semantic_title_similarity(title, profile.candidate_titles)

        profile_skills = {str(skill).lower() for skill in profile.skills}
        required_skill_set = {str(skill).lower() for skill in required_skills}
        overlap = profile_skills.intersection(required_skill_set)
        if required_skill_set:
            skill_match_score = len(overlap) / len(required_skill_set)
        else:
            skill_match_score = 0.0

        effective_locations = profile.preferred_locations or self.settings.preferred_locations
        location_match_score = location_score(location, effective_locations)

        domain_text = " ".join(
            [title.lower(), description.lower(), role_category.lower(), " ".join(ats_keywords).lower()]
        )
        domain_alignment = any(
            keyword.lower() in domain_text for keyword in (profile.domain_keywords or self.settings.candidate_domain_keywords)
        )

        match_score = (
            (title_similarity * self.settings.title_weight)
            + (skill_match_score * self.settings.skill_weight)
            + (location_match_score * self.settings.location_weight)
        )
        if domain_alignment:
            match_score += 0.08

        match_score = int(max(0, min(100, round(match_score * 100))))

        top_skills = required_skills[:10]
        required_tools = [
            skill
            for skill in required_skills
            if skill
            in {
                "docker",
                "kubernetes",
                "aws",
                "azure",
                "git",
                "mongodb",
                "postgresql",
                "mysql",
                "redis",
            }
        ][:8]

        missing_priority_skills = [skill for skill in top_skills if skill.lower() not in profile_skills]
        priority_skills = (list(overlap) + missing_priority_skills)[:8]

        role_profile = (
            f"{title} at {company} ({role_category}) focusing on "
            f"{', '.join(top_skills[:4]) or 'software development'}."
        )

        return JobAnalysis(
            top_skills=top_skills,
            required_tools=required_tools,
            experience_expectation=experience_expectation or job.get("experience_text", ""),
            experience_min=experience_min,
            experience_max=experience_max,
            role_category=role_category,
            ats_keywords=ats_keywords,
            role_profile=role_profile,
            priority_skills=priority_skills,
            title_similarity=round(title_similarity, 4),
            skill_match_score=round(skill_match_score, 4),
            location_match_score=round(location_match_score, 4),
            domain_alignment=domain_alignment,
            match_score=match_score,
        )

