"""
Skill Scorer - Three-Tier Job Matching
=======================================
Compares Job Description (JD) with Candidate Resume.
Uses comprehensive skill relationships for precise matching.

Scoring:
- Primary Match (exact match) = 20 points
- Secondary Match (related skill) = 10 points
- Partial Match (same category) = 6 points
- No Match = 0 points

Threshold: 65% minimum to SELECT
"""

from typing import Dict, List, Tuple

from utils.job_utils import normalize_skills
from utils.skill_relations import is_related_to

# Legacy partial matches (kept for backward compatibility)
PARTIAL_MATCHES = {
    "django": ["python", "flask"],
    "flask": ["python", "django"],
    "fastapi": ["python", "flask"],
    "java": ["java8", "java11", "java17", "spring"],
    "spring": ["spring boot", "spring framework"],
    "spring boot": ["spring", "spring framework"],
    "mongodb": ["mongo", "mongoose"],
    "mysql": ["mysql2", "mariadb"],
    "postgresql": ["postgres", "postgresql"],
    "sql": ["mysql", "postgresql", "mongodb", "sql server"],
    "docker": ["docker-compose", "dockerfile"],
    "kubernetes": ["k8s", "kubectl"],
    "aws": ["amazon web services", "amazon s3", "ec2"],
    "azure": ["azure devops"],
    "react native": ["react", "reactjs", "mobile"],
    "flutter": ["dart"],
    "machine learning": ["ml", "deep learning", "ai"],
    "data science": ["data analysis", "data analytics"],
    "pandas": ["pandas python", "numpy"],
    "numpy": ["pandas", "numpy python"],
}


class SkillScorer:
    """Percentage-based skill matcher"""

    MIN_MATCH_PERCENTAGE = 65.0

    def __init__(self, min_percentage: float = 65.0):
        self.min_percentage = min_percentage if min_percentage is not None else 65.0

    def normalize_skill(self, skill: str) -> str:
        """Normalize skill name for comparison"""
        return skill.lower().strip().replace(" ", "").replace("-", "")

    def _canonical_unique_skills(self, skills: List[str]) -> List[str]:
        """
        Normalize + dedupe skills so repeated words are counted only once.
        Example: ["JavaScript", "javascript", "JavaScript"] -> ["javascript"]
        """
        cleaned = [str(s) for s in (skills or []) if str(s).strip()]
        return normalize_skills(cleaned)

    def is_primary_match(self, skill: str, jd_skills: List[str]) -> bool:
        """Check if skill is a primary/critical match"""
        skill_lower = skill.lower()
        jd_lower = [s.lower() for s in jd_skills]

        if skill_lower in jd_lower:
            return True

        for jd_skill in jd_lower:
            if skill_lower in jd_skill or jd_skill in skill_lower:
                return True

        return False

    def is_partial_match(self, skill: str, jd_skills: List[str]) -> bool:
        """Check if skill is a partial/transferable match"""
        skill_norm = self.normalize_skill(skill)

        for key, partials in PARTIAL_MATCHES.items():
            if skill_norm == key.replace(" ", ""):
                for p in partials:
                    p_norm = p.replace(" ", "")
                    for jd in jd_skills:
                        jd_norm = jd.lower().replace(" ", "")
                        if p_norm in jd_norm or jd_norm in p_norm:
                            return True

        return False

    def calculate_score(self, resume_skills: List[str], jd_skills: List[str]) -> Dict:
        """
        Calculate three-tier match score between resume and JD skills.

        Duplicate handling:
        - Resume duplicates are removed before matching.
        - JD duplicates are removed before matching.
        - Each JD skill can contribute at most one match.
        """
        unique_resume_skills = self._canonical_unique_skills(resume_skills)
        unique_jd_skills = self._canonical_unique_skills(jd_skills)

        if not unique_resume_skills or not unique_jd_skills:
            return {
                "total_points": 0,
                "max_possible": 0,
                "percentage": 0.0,
                "matched_skills": [],
                "missing_skills": [],
                "matched_count": 0,
                "jd_count": len(unique_jd_skills),
                "resume_unique_count": len(unique_resume_skills),
                "jd_unique_count": len(unique_jd_skills),
                "decision": "REJECTED",
            }

        total_points = 0
        matched_skills = []
        missing_skills = []
        max_possible = len(unique_jd_skills) * 20

        # Score per JD requirement: one best resume match per JD skill.
        for jd_skill in unique_jd_skills:
            best_match = {"skill": "", "jd_match": jd_skill, "category": "none", "points": 0}
            best_points = 0

            for resume_skill in unique_resume_skills:
                is_related, category, points = is_related_to(resume_skill, jd_skill)
                if is_related and points > best_points:
                    best_match = {
                        "skill": resume_skill,
                        "jd_match": jd_skill,
                        "category": category,
                        "points": points,
                    }
                    best_points = points

            if best_points > 0:
                total_points += best_points
                matched_skills.append(best_match)
            else:
                missing_skills.append(jd_skill)

        matched_count = len(matched_skills)
        jd_count = len(unique_jd_skills)
        percentage = (matched_count / jd_count) * 100 if jd_count > 0 else 0.0
        decision = "SELECTED" if percentage >= self.min_percentage else "REJECTED"

        return {
            "total_points": total_points,
            "max_possible": max_possible,
            "matched_count": matched_count,
            "jd_count": jd_count,
            "percentage": round(percentage, 2),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "resume_unique_count": len(unique_resume_skills),
            "jd_unique_count": len(unique_jd_skills),
            "decision": decision,
        }

    def match(self, resume_skills: List[str], jd_skills: List[str]) -> Tuple[bool, Dict]:
        """Main matching function."""
        result = self.calculate_score(resume_skills, jd_skills)
        return result["decision"] == "SELECTED", result


def calculate_match_percentage(resume_skills: List[str], jd_skills: List[str], min_percentage: float = 65.0) -> Dict:
    """Convenience function to calculate match percentage."""
    # Handle None min_percentage
    if min_percentage is None:
        min_percentage = 65.0
    scorer = SkillScorer(min_percentage)
    return scorer.calculate_score(resume_skills, jd_skills)


if __name__ == "__main__":
    test_cases = [
        {
            "name": "Good Match",
            "resume": ["React", "Redux", "Node.js", "Express", "MongoDB", "JavaScript"],
            "jd": ["React", "Node.js", "MongoDB", "Express", "JavaScript", "TypeScript"],
        },
        {
            "name": "Partial Match",
            "resume": ["React", "JavaScript", "JavaScript"],
            "jd": ["React", "Next.js", "Node.js", "TypeScript"],
        },
        {
            "name": "Poor Match",
            "resume": ["Python", "Django", "Python"],
            "jd": ["React", "Node.js", "MongoDB"],
        },
    ]

    print("=== Skill Scorer Test ===\n")
    for test in test_cases:
        result = calculate_match_percentage(test["resume"], test["jd"])
        print(f"{test['name']}:")
        print(f"  Resume: {test['resume']}")
        print(f"  JD: {test['jd']}")
        print(f"  Score: {result['total_points']}/{result['max_possible']} = {result['percentage']}%")
        print(f"  Decision: {result['decision']}")
        print()
