import asyncio
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings(
    "ignore",
    message=r"All support for the `google\.generativeai` package has ended.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module=r"langchain_google_genai\.chat_models",
)

from scraper_adapter.naukri import NaukriScraper
from scraper_adapter.foundit import FoundItScraper
from scraper_adapter.linkedin import LinkedIn10_10


class _FakeLocator:
    def __init__(self, text: str | None):
        self._text = text

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1 if self._text is not None else 0

    async def inner_text(self) -> str:
        if self._text is None:
            raise RuntimeError("No text available")
        return self._text


class _FakePage:
    def __init__(self, selector_to_text: dict[str, str]):
        self._selector_to_text = selector_to_text

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._selector_to_text.get(selector))


def test_naukri_extracts_role_and_company():
    scraper = NaukriScraper.__new__(NaukriScraper)
    page = _FakePage(
        {
            "h1.jd-header-title": "Backend Engineer",
            ".jd-header-comp-name": "Acme Corp",
        }
    )
    role, company = asyncio.run(NaukriScraper._extract_job_identity(scraper, page))
    assert role == "Backend Engineer"
    assert company == "Acme Corp"


def test_foundit_extracts_role_and_company():
    scraper = FoundItScraper.__new__(FoundItScraper)
    page = _FakePage(
        {
            "h1": "Software Developer",
            ".company-name": "Globex",
        }
    )
    role, company = asyncio.run(FoundItScraper._extract_job_identity(scraper, page))
    assert role == "Software Developer"
    assert company == "Globex"


def test_linkedin_extracts_role_and_company():
    scraper = LinkedIn10_10.__new__(LinkedIn10_10)
    page = _FakePage(
        {
            ".job-details-jobs-unified-top-card__job-title": "SDE I",
            ".job-details-jobs-unified-top-card__company-name": "Innotech",
        }
    )
    role, company = asyncio.run(LinkedIn10_10._extract_job_identity(scraper, page))
    assert role == "SDE I"
    assert company == "Innotech"


def test_identity_extractors_have_safe_defaults():
    naukri = NaukriScraper.__new__(NaukriScraper)
    foundit = FoundItScraper.__new__(FoundItScraper)
    linkedin = LinkedIn10_10.__new__(LinkedIn10_10)
    page = _FakePage({})

    n_role, n_company = asyncio.run(NaukriScraper._extract_job_identity(naukri, page))
    f_role, f_company = asyncio.run(FoundItScraper._extract_job_identity(foundit, page))
    l_role, l_company = asyncio.run(LinkedIn10_10._extract_job_identity(linkedin, page))

    assert (n_role, n_company) == ("Software Engineer", "Naukri")
    assert (f_role, f_company) == ("Software Engineer", "FoundIt")
    assert (l_role, l_company) == ("Software Engineer", "LinkedIn")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([str(Path(__file__))]))
