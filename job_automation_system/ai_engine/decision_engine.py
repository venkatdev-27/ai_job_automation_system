from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.job_utils import is_senior_title


@dataclass
class DecisionResult:
    should_apply: bool
    status: str
    match_score: int
    reasons: list[str] = field(default_factory=list)


class DecisionEngine:
    def __init__(self, threshold: int = 65, exclude_keywords: list[str] | None = None) -> None:
        self.threshold = threshold
        self.exclude_keywords = [keyword.lower().strip() for keyword in (exclude_keywords or []) if keyword.strip()]

    async def evaluate(
        self,
        job: dict[str, Any],
        analysis: dict[str, Any],
        profile: Any,
        settings: Any,
        llm_answers: Any = None
    ) -> DecisionResult:
        reasons: list[str] = []
        match_score = int(analysis.get("match_score", 0))

        # v3 MASTER OVERRIDE: If threshold is 0, we FORCE application for verification
        if self.threshold <= 0:
            reasons.append(f"VERIFICATION MODE ACTIVE: Forcing strike on score {match_score}")
            return DecisionResult(
                should_apply=True,
                status="eligible_forced",
                match_score=match_score,
                reasons=reasons,
            )
        title = str(job.get("title", ""))
        employment_type = str(job.get("employment_type", "unknown")).lower()
        full_text = " ".join(
            [
                title,
                str(job.get("description", "")),
                str(job.get("experience_text", "")),
                str(job.get("location", "")),
            ]
        ).lower()

        blocked_keywords = [token for token in self.exclude_keywords if token and token in full_text]
        if blocked_keywords:
            reasons.append(f"Excluded keywords found: {', '.join(blocked_keywords[:3])}")
            return DecisionResult(
                should_apply=False,
                status="skipped_irrelevant",
                match_score=int(analysis.get("match_score", 0)),
                reasons=reasons,
            )

        if is_senior_title(title):
            reasons.append("Senior role filtered out")
            return DecisionResult(
                should_apply=False,
                status="skipped_senior_role",
                match_score=int(analysis.get("match_score", 0)),
                reasons=reasons,
            )

        # V2 HARDENED FRESHER SHIELD: Skip 'evertime' if experience > 1 year
        min_exp = int(analysis.get("experience_min", 0))
        if min_exp > 1:
            reasons.append(f"Fresher Shield: requires {min_exp}+ years (Skipping > 1yr requirement)")
            return DecisionResult(
                should_apply=False,
                status="skipped_experience_mismatch",
                match_score=int(analysis.get("match_score", 0)),
                reasons=reasons,
            )

        # V2 SKILL QUALITY GUARD: Require at least 3-4 major skill matches (LLM BACKED)
        skills_pass = False
        if llm_answers:
            try:
                skill_audit_prompt = (
                    f"Candidate Skills: {', '.join(profile.skills)}\n"
                    f"Job Requirements: {', '.join(analysis.get('top_skills', []))}\n"
                    "Does the candidate possess at least 3-4 MAJOR core skills required for this job? "
                    "Return ONLY 'YES' followed by the number of matches (e.g. 'YES - 4 matches') or 'NO'. No explanations."
                )
                audit_res = await llm_answers._ask_llm(skill_audit_prompt, max_tokens=20)
                if "YES" in audit_res.upper():
                    skills_pass = True
                else:
                    reasons.append(f"AI Skill Audit Failed: {audit_res.strip()} (Need 3-4 major matches)")
                    return DecisionResult(
                        should_apply=False,
                        status="skipped_skill_mismatch",
                        match_score=int(analysis.get("match_score", 0)),
                        reasons=reasons,
                    )
            except Exception:
                # Fallback to standard set intersection
                profile_skills = {s.lower() for s in profile.skills}
                required_skills = {s.lower() for s in analysis.get("top_skills", [])}
                overlap = profile_skills.intersection(required_skills)
                if len(overlap) >= 3:
                     skills_pass = True
                else:
                    reasons.append(f"Low Quality Match: only {len(overlap)} skills match (Need 3-4 minimum)")
                    return DecisionResult(
                        should_apply=False,
                        status="skipped_low_skill_overlap",
                        match_score=int(analysis.get("match_score", 0)),
                        reasons=reasons,
                    )

        # V2 TITLE FLEXIBILITY: If skills pass, lower the similarity hurdle
        title_similarity = float(analysis.get("title_similarity", 0.0))
        # Lower threshold if skills match (0.4 vs default 0.6)
        min_title_score = 0.35 if skills_pass else settings.min_title_similarity
        
        if title_similarity < min_title_score:
            reasons.append(
                f"Low title similarity ({title_similarity:.2f} < {min_title_score:.2f})"
            )
            return DecisionResult(
                should_apply=False,
                status="skipped_title_mismatch",
                match_score=int(analysis.get("match_score", 0)),
                reasons=reasons,
            )

        skill_match = float(analysis.get("skill_match_score", 0.0))
        if skill_match < settings.min_skill_match:
            reasons.append(f"Low skill match ({skill_match:.2f} < {settings.min_skill_match:.2f})")
            return DecisionResult(
                should_apply=False,
                status="skipped_skill_mismatch",
                match_score=int(analysis.get("match_score", 0)),
                reasons=reasons,
            )

        match_score = int(analysis.get("match_score", 0))
        if match_score < self.threshold:
            reasons.append(f"Match score below threshold ({match_score} < {self.threshold})")
            return DecisionResult(
                should_apply=False,
                status="skipped_low_score",
                match_score=match_score,
                reasons=reasons,
            )

        reasons.append(f"Eligible: match score {match_score} >= {self.threshold}")
        return DecisionResult(
            should_apply=True,
            status="eligible",
            match_score=match_score,
            reasons=reasons,
        )

