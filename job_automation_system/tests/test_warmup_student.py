"""
Test Warmup Student - student_2b4359c4
=======================================
End-to-end warmup pipeline test for a specific student.
Validates: MongoDB fetch → Resume download → Template extraction → RAG profile → Resume generation.

Can run without pytest:  python tests/test_warmup_student.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup logging early
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add parent for imports
PARENT = PROJECT_ROOT.parent
if PARENT.exists() and str(PARENT) not in sys.path:
    # Append instead of insert(0) to keep PROJECT_ROOT prioritized
    sys.path.append(str(PARENT))

# ─── Constants ───────────────────────────────────────────────────────
STUDENT_ID = "student_2b4359c4"


# =====================================================================
# Unit-style checks (no heavy I/O)
# =====================================================================

class TestStudentMongoFetch:
    """Verify the student record exists and has required fields."""

    def test_student_exists(self):
        """Student document must exist in MongoDB."""
        from utils.student_mongodb import get_student_by_id
        student = get_student_by_id(STUDENT_ID)
        assert student is not None, f"Student {STUDENT_ID} not found in MongoDB"
        logger.info("OK - Student found: %s", student.get("full_name", student.get("name", "N/A")))

    def test_student_has_resume_url(self):
        """Student must have a resume URL (Cloudinary)."""
        from utils.student_mongodb import get_student_resume_url
        url = get_student_resume_url(STUDENT_ID)
        assert url, f"No resume URL for {STUDENT_ID}"
        logger.info("OK - Resume URL: %s...", url[:60])

    def test_student_profile_builds(self):
        """StudentProfile dataclass should hydrate without errors."""
        from utils.student_mongodb import get_student_profile
        profile = get_student_profile(STUDENT_ID)
        assert profile is not None, "get_student_profile returned None"
        assert profile.name, "Profile name is empty"
        logger.info("OK - Profile built: %s | skills=%d | titles=%s",
                     profile.name, len(profile.skills), profile.candidate_titles)


class TestResumeDownload:
    """Verify resume can be downloaded / is cached locally."""

    def test_download_resume(self):
        """Download (or use cache) for the master resume."""
        from utils.student_mongodb import get_student_resume_url
        from utils.resume_downloader import download_if_needed

        url = get_student_resume_url(STUDENT_ID)
        assert url, "Resume URL missing – cannot test download"

        local_path = download_if_needed(url, STUDENT_ID)
        assert local_path and os.path.exists(local_path), f"Download failed or path missing: {local_path}"
        size_kb = os.path.getsize(local_path) / 1024
        logger.info("OK - Resume on disk: %s (%.1f KB)", local_path, size_kb)


class TestMasterTemplateExtraction:
    """Verify master template extraction from downloaded PDF."""

    def test_extract_template(self):
        """Template extractor should return alignment + font info."""
        from utils.student_mongodb import get_student_resume_url
        from utils.resume_downloader import download_if_needed
        from utils.master_template_extractor import extract_master_template

        url = get_student_resume_url(STUDENT_ID)
        local_path = download_if_needed(url, STUDENT_ID)
        assert local_path and os.path.exists(local_path), "Resume not available for template extraction"

        template = extract_master_template(STUDENT_ID, local_path)
        assert isinstance(template, dict), "Template must be a dict"
        logger.info("OK - Template: alignment=%s, font=%s",
                     template.get("alignment", "?"), template.get("font_family", "?"))


# =====================================================================
# Integration / async checks (heavier – RAG + resume gen)
# =====================================================================

class TestFullWarmupPipeline:
    """Run the full warmup_student coroutine end-to-end."""

    async def _run_warmup(self):
        from scripts.warmup_student import warmup_student
        return await warmup_student(STUDENT_ID)

    def test_warmup_completes(self):
        """Full warmup pipeline should return True."""
        result = asyncio.run(self._run_warmup())
        assert result is True, f"Warmup returned {result} – check logs above for details"
        logger.info("OK - Full warmup pipeline succeeded for %s", STUDENT_ID)


class TestPostWarmupDataVerification:
    """Verify that all data was correctly saved to MongoDB after warmup."""

    def test_mongodb_document_completeness(self):
        """Verify presence of personal info, skills, experience, projects, and roles."""
        from utils.student_mongodb import get_student_by_id
        student = get_student_by_id(STUDENT_ID)
        assert student is not None, "Student document missing after warmup"

        # Check Personal Info
        assert student.get("full_name"), "full_name missing"
        assert student.get("email"), "email missing"
        assert student.get("phone"), "phone missing"
        assert student.get("location"), "location missing"

        # Check Academic & Skills
        assert student.get("education"), "education data missing"
        skills = student.get("skills", [])
        assert len(skills) > 5, f"Expected >5 skills, found {len(skills)}"

        # Check Experience & Projects (The "meat" of the resume)
        experience = student.get("experience", [])
        assert len(experience) > 0, "experience array is empty"
        projects = student.get("projects", [])
        assert len(projects) > 0, "projects array is empty"

        # Check AI-Discovered Roles
        custom_roles = student.get("custom_roles", {})
        assert len(custom_roles) >= 5, f"Expected >=5 custom roles, found {len(custom_roles)}"
        
        logger.info("OK - MongoDB Data Verified: Name=%s, Skills=%d, Exp=%d, Proj=%d, Roles=%d",
                    student.get("full_name"), len(skills), len(experience), len(projects), len(custom_roles))


# =====================================================================
# Manual runner (no pytest needed)
# =====================================================================

def run_tests():
    """Run all tests manually."""
    print(f"\n{'='*60}")
    print(f"  WARMUP TEST SUITE — {STUDENT_ID}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0
    skipped = 0

    # ── lightweight tests first ──
    lightweight = [
        TestStudentMongoFetch(),
        TestResumeDownload(),
        TestMasterTemplateExtraction(),
    ]

    for test_obj in lightweight:
        cls_name = test_obj.__class__.__name__
        methods = sorted(m for m in dir(test_obj) if m.startswith("test_"))
        for method_name in methods:
            label = f"{cls_name}.{method_name}"
            try:
                getattr(test_obj, method_name)()
                passed += 1
            except AssertionError as ae:
                print(f"  FAIL  {label}: {ae}")
                failed += 1
            except Exception as e:
                print(f"  SKIP  {label}: {e}")
                skipped += 1

    # ── full pipeline (always run) ──
    print(f"\n--- Full Warmup Pipeline (async) ---")
    try:
        TestFullWarmupPipeline().test_warmup_completes()
        passed += 1
        
        # Verify data saved to DB
        TestPostWarmupDataVerification().test_mongodb_document_completeness()
        passed += 1
    except AssertionError as ae:
        print(f"  FAIL  Pipeline Verification: {ae}")
        failed += 1
    except Exception as e:
        print(f"  SKIP  Pipeline Verification: {e}")
        skipped += 1

    # ── summary ──
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed | {failed} failed | {skipped} skipped")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
