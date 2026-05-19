import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs
from playwright.async_api import async_playwright

# Add project root to path for engine imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

## Import Core Engine and RAG components
try:
    from ai_job_auto_apply.job_application_engine import FormAnswerer, FormField, JobInput, UserProfile
except ImportError:
    # Fallback for direct script execution
    sys.path.append(str(PROJECT_ROOT / "ai_job_auto_apply"))
    from job_application_engine import FormAnswerer, FormField, JobInput, UserProfile

# Global Brain
BRAIN = FormAnswerer()

from .config import (
    LINKEDIN_EMAIL, LINKEDIN_PASSWORD, USER_AGENT, VIEWPORT, LOCALE,
    COOKIES_FILE, LINKEDIN_LOCATION, LINKEDIN_EXPERIENCE_FILTER,
    LINKEDIN_TIME_FILTER, C, TIMEZONE_ID, PIPELINE_DATA_DIR, ARCHIVE_EXTRACTED_JD
)
from .llm import groq_call, openrouter_call
from .utils import log_info, log_ok, log_err, log_warn



def extract_job_id_from_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        qs = parse_qs(parsed.query)
        if qs.get("currentJobId"):
            return qs["currentJobId"][0]
        m = re.search(r"/jobs/view/(\d+)", parsed.path)
        if m: return m.group(1)
    except: pass
    return ""

def _json_from_text(raw: str):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            pass
    return None

def _clean_list(items, limit: int = 12) -> list[str]:
    cleaned = []
    for item in items or []:
        text = re.sub(r"\s+", " ", str(item or "")).strip(" -•\t\r\n")
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:limit]

def extract_requirement_groups(jd_text: str, jd_points: list[str], job_skills: list[str]) -> dict:
    clean_jd = re.sub(r"\s+", " ", str(jd_text or "")).strip()
    if not clean_jd:
        return {"must_have": [], "should_have": [], "responsibilities": [], "skills": job_skills}

    prompt = f"""
Extract requirements from this job description as JSON.

Return exactly:
{{
  "must_have": ["required qualifications, mandatory skills, must bring"],
  "should_have": ["nice-to-have, preferred, add-on skills"],
  "responsibilities": ["main responsibilities"],
  "skills": ["technical skills/tools only"]
}}

Rules:
- Keep each item short and factual.
- Use only the job description.
- Do not invent.

Job description:
{clean_jd[:7000]}
"""
    try:
        raw = groq_call(prompt, system="You extract structured job requirements. Return only JSON.")
        parsed = _json_from_text(raw)
        if isinstance(parsed, dict):
            return {
                "must_have": _clean_list(parsed.get("must_have"), 14),
                "should_have": _clean_list(parsed.get("should_have"), 12),
                "responsibilities": _clean_list(parsed.get("responsibilities"), 14),
                "skills": _clean_list(parsed.get("skills") or job_skills, 18),
            }
    except Exception as e:
        log_warn(f"Requirement extraction via LLM failed: {e}")

    must_patterns = r"(required|must|what you must bring|qualifications|requirements)"
    should_patterns = r"(preferred|nice to have|good to have|add-on|bonus)"
    must_have = [p for p in jd_points if re.search(must_patterns, p, re.IGNORECASE)]
    should_have = [p for p in jd_points if re.search(should_patterns, p, re.IGNORECASE)]
    responsibilities = [p for p in jd_points if p not in must_have and p not in should_have]
    return {
        "must_have": _clean_list(must_have, 14),
        "should_have": _clean_list(should_have, 12),
        "responsibilities": _clean_list(responsibilities, 14),
        "skills": _clean_list(job_skills, 18),
    }
def is_logged_in(page):
    """Returns True if the page is currently on a logged-in view."""
    return "feed" in page.url or "mynetwork" in page.url or "messaging" in page.url

def is_login_wall(page):
    """Returns True if the page has been redirected to a login/checkpoint wall."""
    return any(x in page.url for x in ["login", "checkpoint", "challenge", "signup", "uas/login"])

async def simulate_human_behavior(page):
    """Simulates realistic human-like mouse movements and scrolling with high randomization."""
    log_info("Simulating human behavior...")
    try:
        # 1. Randomized Mouse Movements (2-5 iterations)
        for _ in range(random.randint(2, 5)):
            await page.mouse.move(
                random.randint(100, 800),
                random.randint(100, 600)
            )
            # Human-like wait timeouts (500ms - 2000ms)
            await asyncio.sleep(random.uniform(0.5, 2.0))
        
        # 2. Natural Scrolling (Variable amounts: 200px - 800px)
        if random.random() > 0.3:
            scroll_amount = random.randint(200, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
    except Exception as e:
        log_warn(f"Behavior simulation skipped: {e}")

async def retry_action(action, retries=3, delay=2.0):
    """Retries an asynchronous action multiple times with a delay."""
    for attempt in range(retries):
        try:
            return await action()
        except Exception as e:
            if attempt < retries - 1:
                log_warn(f"Action failed, retrying ({attempt + 1}/{retries})... Error: {e}")
                await asyncio.sleep(delay)
            else:
                log_err(f"Action failed after {retries} retries: {e}")
                raise e

async def ensure_session(page):
    """Ensures the account is logged in, waiting for manual intervention if challenged."""
    if is_login_wall(page):
        log_err("[ALERT] Session expired or challenged. Please login again...")
        log_info("[PROMPT] The script will resume once you reach the Feed page.")
        try:
            # Wait up to 5 minutes for the user to resolve challenges
            await page.wait_for_url("https://www.linkedin.com/feed/", timeout=300000)
            log_ok("Session restored. Resuming...")
            return True
        except:
            log_err("Manual login/challenge resolution timed out.")
            return False
    return is_logged_in(page)

# Keep check_for_lockout as an alias for compatibility with run_pipeline_v2.py
async def check_for_lockout(page):
    if is_login_wall(page):
        log_err("[ALERT] Account lockout or security challenge detected!")
        log_info("[PROMPT] Please resolve the challenge manually in the browser window.")
        try:
            # Wait up to 5 minutes for the user to resolve challenges
            await page.wait_for_url("https://www.linkedin.com/feed/", timeout=300000)
            log_ok("Lockout resolved. Resuming...")
            return True
        except:
            log_err("Lockout resolution timed out.")
            return False
    return True

async def get_stealth_context(browser, storage_state=None):
    """Creates a browser context with stealth properties."""
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        locale=LOCALE,
        storage_state=storage_state
    )
    # Add extra stealth if needed (e.g. navigator.webdriver = false)
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return context

async def setup_single_tab(page):
    """Ensures the page stays in a single tab where possible, but allows necessary popups."""
    # We remove the aggressive closer to allow Easy Apply windows to function.
    log_info("Single-tab stabilization active (relaxed for Easy Apply).")

async def linkedin_login(page):
    """Handles LinkedIn login with a hybrid automated/manual flow."""
    log_info("Verifying LinkedIn session...")
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log_warn(f"Feed navigation slow: {e}")

    await asyncio.sleep(2)
    if is_logged_in(page):
        log_ok("Already logged in via existing session.")
        return True

    user_selectors = ["#username", "input#username", "input[name='session_key']", "input[type='email']"]
    pass_selectors = ["#password", "input#password", "input[name='session_password']", "input[type='password']"]
    login_btn_selectors = ["button[type='submit']", ".btn__primary--large", "button:has-text('Sign in')"]

    if LINKEDIN_EMAIL and LINKEDIN_PASSWORD:
        log_info("Active session not found. Attempting automatic credential login...")
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            log_warn(f"LinkedIn login page navigation issue: {e}")

        user_found = False
        for selector in user_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                input_el = page.locator(selector).first
                if await input_el.count() > 0:
                    await input_el.click()
                    await input_el.fill("")
                    await input_el.fill(LINKEDIN_EMAIL)
                    user_found = True
                    break
            except Exception:
                continue

        pass_found = False
        for selector in pass_selectors:
            try:
                input_el = page.locator(selector).first
                if await input_el.count() > 0:
                    await input_el.click()
                    await input_el.fill("")
                    await input_el.fill(LINKEDIN_PASSWORD)
                    pass_found = True
                    break
            except Exception:
                continue

        clicked_login = False
        for btn_sel in login_btn_selectors:
            try:
                btn = page.locator(btn_sel).first
                if await btn.count() > 0:
                    await btn.click()
                    clicked_login = True
                    break
            except Exception:
                continue

        if user_found and pass_found and clicked_login:
            log_info("Automatic login submitted. Waiting for feed...")
            try:
                await page.wait_for_url("https://www.linkedin.com/feed/", timeout=45000)
            except Exception:
                await asyncio.sleep(3)

            if is_logged_in(page):
                log_ok("Automatic login successful.")
                await page.context.storage_state(path=str(COOKIES_FILE))
                return True

            if is_login_wall(page):
                log_warn("Challenge/login wall detected after auto-login.")
            else:
                log_warn(f"Auto-login did not land on feed. Current URL: {page.url}")
        else:
            log_warn("Auto-login fields/buttons not fully available. Falling back to manual login.")
    else:
        log_warn("LinkedIn credentials are missing. Skipping auto-login.")

    log_info("Please complete login manually. Waiting up to 5 minutes for feed page...")
    try:
        await page.wait_for_url("https://www.linkedin.com/feed/", timeout=300000)
        log_ok("Manual login detected. Session restored.")
        await page.context.storage_state(path=str(COOKIES_FILE))
        return True
    except Exception as e:
        log_err(f"Login failed after manual fallback wait: {e}")
        return False

async def linkedin_extract_job(page, profile: dict, skip_ids: set = None) -> dict:
    """Search for jobs and extract details from the first matching one not in skip_ids."""
    if skip_ids is None: skip_ids = set()
    search_role = profile.get("target_role", "Software Engineer")
    log_info(f"Searching for: {search_role}")
    
    search_url = (
        f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(search_role)}"
        f"&location={quote_plus(LINKEDIN_LOCATION)}"
        f"&f_E={quote_plus(LINKEDIN_EXPERIENCE_FILTER)}&f_AL=true&f_TPR={LINKEDIN_TIME_FILTER}"
        f"&f_JT=F"
    )
    
    if not await check_for_lockout(page): return {}
    # Referrer spoofing
    await page.goto(search_url, wait_until="domcontentloaded", referer="https://www.linkedin.com/feed/")
    await asyncio.sleep(random.uniform(5, 10)) # Human-like wait for initial load
    await simulate_human_behavior(page)
    
    # Robust card selectors
    card_selectors = [
        "li[data-occludable-job-id]",
        ".job-card-container",
        ".job-card-list__entity-lockup",
        ".jobs-search-results__list-item",
        "div.job-search-card",
        "div.base-card"
    ]
    
    # Wait for cards to appear with retries
    max_retries = 3
    found_selector = None
    
    for attempt in range(max_retries):
        log_info(f"Scanning for job cards (Attempt {attempt + 1}/{max_retries})...")
        for selector in card_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    found_selector = selector
                    break
            except: continue
        
        if found_selector:
            break
            
        log_warn("No job cards found. Reloading page...")
        await page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(4, 6))

    if not found_selector:
        log_err("Could not find any job cards on the results page after multiple reloads.")
        return {}

    cards = await page.locator(found_selector).all()
    log_info(f"Found {len(cards)} job cards. Filtering out {len(skip_ids)} seen jobs...")
    
    async def _has_easy_apply_button(job_page) -> bool:
        # If already applied badge exists, treat as non-applicable for this run.
        try:
            applied_badges = [
                ".jobs-apply-button--applied",
                "button[aria-label*='Applied']",
                "span:has-text('Applied')",
            ]
            for sel in applied_badges:
                node = job_page.locator(sel).first
                if await node.count() > 0 and await node.is_visible():
                    return False
        except Exception:
            pass

        easy_apply_selectors = [
            "button.jobs-apply-button:has-text('Easy Apply')",
            "button[aria-label*='Easy Apply']",
            ".jobs-apply-button--top-card button:has-text('Easy Apply')",
        ]
        for sel in easy_apply_selectors:
            try:
                btn = job_page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    if not await btn.is_disabled():
                        return True
            except Exception:
                continue
        return False

    target_id = None
    for card in cards:
        try:
            # Extract ID from card link or attribute
            jid = await card.get_attribute("data-occludable-job-id")
            if not jid:
                link = card.locator("a").first
                if await link.count() > 0:
                    href = await link.get_attribute("href")
                    jid = extract_job_id_from_url(href)

            if not jid or jid in skip_ids:
                continue

            log_info(f"Evaluating Easy Apply availability for Job ID: {jid}")
            await simulate_human_behavior(page)
            await card.click()
            await asyncio.sleep(random.uniform(4.0, 6.0))

            has_easy_apply = await _has_easy_apply_button(page)
            if not has_easy_apply:
                log_warn(f"Skipping job {jid}: Easy Apply button not available.")
                skip_ids.add(jid)
                continue

            target_id = jid
            log_ok(f"Easy Apply detected for Job ID: {jid}. Proceeding to JD extraction.")
            break
        except Exception as e:
            log_warn(f"Card evaluation failed: {e}")
            continue

    if not target_id:
        log_warn("No new Easy Apply jobs found in current result set.")
        return {}
    
    # Wait for JD to load with more patience
    title_selectors = [".topcard__link h2", "h1.t-24", ".jobs-unified-top-card__job-title"]
    log_info("Waiting for JD title to appear...")
    try:
        await page.wait_for_selector(", ".join(title_selectors), timeout=15000)
    except: pass

    # --- NEW: Mandatory 'Show more' click to get FULL description ---
    try:
        show_more_selectors = [
            "button.jobs-description__footer-button",
            "button.jobs-description-content__button",
            "button.show-more-less-html__button--more",
            "button[aria-label*='Show more']",
            "button:has-text('Show more')"
        ]
        for sms in show_more_selectors:
            btn = page.locator(sms).first
            if await btn.count() > 0 and await btn.is_visible():
                log_info(f"Clicking 'Show more' ({sms}) for full extraction...")
                await btn.click()
                await asyncio.sleep(1)
                break
    except: pass

    # Title extraction fallbacks
    title = "Unknown"
    for ts in title_selectors:
        if await page.locator(ts).count() > 0:
            title = await page.locator(ts).first.inner_text()
            break

    # Company extraction fallbacks
    company_selectors = [
        ".topcard__org-name-link", 
        ".jobs-unified-top-card__company-name", 
        ".jobs-unified-top-card__company-name a",
        "div.job-details-jobs-unified-top-card__company-name",
        "span.jobs-unified-top-card__company-name",
        ".job-details-jobs-unified-top-card__primary-description a"
    ]
    company = "Unknown"
    for cs in company_selectors:
        try:
            if await page.locator(cs).count() > 0:
                company = await page.locator(cs).first.inner_text()
                break
        except: continue
    
    # JD extraction (Harden with robust selectors)
    jd_selectors = [
        "#job-details", 
        ".jobs-description-content__text", 
        ".show-more-less-html__markup", 
        ".jobs-description__container",
        ".jobs-box__html-content"
    ]
    jd_container = None
    for js in jd_selectors:
        try:
            if await page.locator(js).count() > 0:
                jd_container = page.locator(js).first
                break
        except: continue
    
    jd_text = ""
    jd_points = []
    jd_600_words = ""
    
    if jd_container:
        # Get raw text
        jd_text = await jd_container.inner_text()
        
        # Optional: archive full JD for audit/debug only when enabled.
        if ARCHIVE_EXTRACTED_JD:
            try:
                archive_dir = PIPELINE_DATA_DIR / "extracted_jds"
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / f"{target_id}.txt"
                archive_path.write_text(jd_text, encoding="utf-8")
                log_info(f"Full JD archived to: temp_pipeline/extracted_jds/{target_id}.txt")
            except Exception as e:
                log_warn(f"Failed to archive JD: {e}")
        
        # 1. Extract Points (li tags or bullet markers)
        li_elements = jd_container.locator("li")
        count = await li_elements.count()
        if count > 0:
            for i in range(count):
                txt = (await li_elements.nth(i).inner_text()).strip()
                if txt: jd_points.append(txt)
        else:
            # Fallback regex for text bullets (â€¢, *, -, numbers)
            jd_points = [p.strip() for p in re.findall(r"(?:^|\n)[ \t]*[â€¢\*\-\d\.]+[ \t]+(.*)", jd_text) if p.strip()]

        # 2. Clean text and limit to 600 words (normalize spaces)
        clean_text = re.sub(r"\s+", " ", jd_text).strip()
        words = clean_text.split()
        jd_600_words = " ".join(words[:600])

    # 3. Extract Skills via LLM for Enhanced Targeting
    def _fallback_skill_extract(text: str, title_text: str = "") -> list[str]:
        corpus = f"{title_text} {text}".lower()
        skill_catalog = [
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "ruby", "php",
            "react", "next.js", "angular", "vue", "node.js", "express", "nestjs",
            "html", "css", "tailwind", "bootstrap",
            "mongodb", "mysql", "postgresql", "redis", "sqlite", "dynamodb",
            "graphql", "rest", "rest api", "microservices",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
            "git", "github", "ci/cd", "linux", "nginx",
            "selenium", "playwright", "pytest", "jest", "mocha",
            "machine learning", "ai", "llm", "rag",
        ]
        found = []
        for skill in skill_catalog:
            if skill in corpus:
                found.append(skill)
        # Deduplicate and normalize casing
        seen = set()
        normalized = []
        for s in found:
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(s)
        return normalized[:15]

    job_skills = []
    if jd_600_words:
        try:
            skill_prompt = f"Extract a comma-separated list of the top 10 technical skills and tools from this job description:\n\n{jd_600_words}"
            raw_skills = groq_call(skill_prompt, system="You are a technical recruiter. Return ONLY a comma-separated list.")
            if raw_skills:
                job_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        except: pass

    # Deterministic fallback if LLM extraction is empty.
    if not job_skills:
        source_text = jd_600_words or jd_text
        job_skills = _fallback_skill_extract(source_text, title)
        if job_skills:
            log_info(f"Fallback skill extractor detected: {', '.join(job_skills)}")

    requirement_groups = extract_requirement_groups(jd_text, jd_points, job_skills)
    if requirement_groups.get("skills"):
        job_skills = requirement_groups["skills"]

    job_data = {
        "job_title": title.strip(),
        "job_company": company.strip(),
        "job_url": page.url,
        "job_id": target_id,
        "job_description": jd_text.strip(),
        "job_description_clean": jd_600_words,
        "job_points": jd_points,
        "job_skills": job_skills,
        "must_have": requirement_groups.get("must_have", []),
        "should_have": requirement_groups.get("should_have", []),
        "responsibilities": requirement_groups.get("responsibilities", []),
    }
    
    if jd_text:
        log_ok(f"EXTRACT SUCCESS: {job_data['job_title']} at {job_data['job_company']}")
        log_info(f"Skills Extracted: {', '.join(job_skills)}")
        log_info(f"Must-have requirements: {len(job_data['must_have'])}; Should-have: {len(job_data['should_have'])}")
    else:
        log_err("FAILED to extract Job Description text.")

    return job_data

FORM_ANSWER_CACHE: dict[str, str] = {}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "of", "on", "or", "the", "this", "to",
    "what", "with", "you", "your"
}

def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", str(text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }

def _chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    clean = _compact_text(text)
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks

def _retrieve_relevant_chunks(query: str, texts: list[str], limit: int = 3) -> list[str]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    scored = []
    for text in texts:
        for chunk in _chunk_text(text):
            chunk_tokens = _tokens(chunk)
            if not chunk_tokens:
                continue
            score = len(query_tokens & chunk_tokens)
            if score:
                scored.append((score, len(chunk_tokens), chunk))

    scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    return [chunk for _, _, chunk in scored[:limit]]

def _safe_first_line(value: str, max_len: int = 120) -> str:
    answer = _compact_text(value).split("\n")[0].strip()
    if len(answer) > max_len:
        answer = answer[:max_len].rstrip()
    return answer

def _is_placeholder_option(option_text: str) -> bool:
    text = _compact_text(option_text).lower()
    if not text:
        return True
    if re.fullmatch(r"[-–—\s]{2,}", text):
        return True
    known_placeholders = {
        "select",
        "select option",
        "select an option",
        "choose",
        "choose option",
        "choose an option",
        "please select",
        "please make a selection",
        "make a selection",
        "--select--",
        "-select-",
        "default",
    }
    if text in known_placeholders:
        return True
    if text.startswith("select ") and len(text) <= 40:
        return True
    if text.startswith("choose ") and len(text) <= 40:
        return True
    if "make a selection" in text:
        return True
    return False

def _real_options(options: list[str]) -> list[str]:
    cleaned = [_compact_text(opt) for opt in (options or []) if _compact_text(opt)]
    non_placeholder = [opt for opt in cleaned if not _is_placeholder_option(opt)]
    return non_placeholder or cleaned

def _pick_option(answer: str, options: list[str]) -> str:
    if not options:
        return answer
    options = _real_options(options)
    clean_answer = _compact_text(answer).lower()
    for opt in options:
        if _compact_text(opt).lower() == clean_answer:
            return opt
    for opt in options:
        opt_clean = _compact_text(opt).lower()
        if opt_clean and (opt_clean in clean_answer or clean_answer in opt_clean):
            return opt
    yes_no = {"yes", "no"}
    if clean_answer in yes_no:
        for opt in options:
            if _compact_text(opt).lower().startswith(clean_answer):
                return opt
    return options[0]

def _extract_first_int(value: str) -> int | None:
    try:
        match = re.search(r"-?\d+", str(value or ""))
        if not match:
            return None
        return int(match.group(0))
    except Exception:
        return None

def _guess_profile_experience_years(profile: dict) -> int:
    if not isinstance(profile, dict):
        return 2

    candidate_values = []
    for key in ["experience_years", "years_of_experience", "total_experience"]:
        raw = profile.get(key)
        if isinstance(raw, (int, float)):
            candidate_values.append(int(raw))
        elif isinstance(raw, str):
            parsed = _extract_first_int(raw)
            if parsed is not None:
                candidate_values.append(parsed)

    text_blobs = [
        profile.get("summary", ""),
        profile.get("resume_text", ""),
        json.dumps(profile.get("resume_data", {}), ensure_ascii=False),
    ]
    for blob in text_blobs:
        for hit in re.findall(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", str(blob or "").lower()):
            parsed = _extract_first_int(hit)
            if parsed is not None:
                candidate_values.append(parsed)

    if not candidate_values:
        return 2
    guessed = max(candidate_values)
    return max(0, min(99, guessed))

def _looks_numeric_field(question: str, input_type: str = "") -> bool:
    itype = _compact_text(input_type).lower()
    if itype in {"number", "range"}:
        return True

    q = _compact_text(question).lower()
    numeric_markers = [
        "how many years",
        "years of",
        "yrs of",
        "whole number",
        "enter a number",
        "0 and 99",
        "0-99",
        "experience do you currently have",
        "expected ctc",
        "current ctc",
        "notice period",
        "month",
        "months",
        "ranking",
        "rank",
        "score",
        "points",
        "percentage",
        "salary",
        "stipend",
        "commission",
        "%"
    ]
    return any(marker in q for marker in numeric_markers)

def _coerce_numeric_answer(answer: str, question: str, profile: dict) -> str:
    q = _compact_text(question).lower()
    num = _extract_first_int(answer)

    if num is None:
        if any(marker in q for marker in ["years", "experience", "exp"]):
            num = _guess_profile_experience_years(profile)
        elif "notice" in q and "day" in q:
            num = 30
        elif "notice" in q:
            num = 1
        else:
            # Default to 0 for unknown numeric fields to avoid validation errors
            num = 0

    low, high = 0, 99
    # For rankings or large scores, allow higher bounds
    if any(m in q for m in ["ranking", "rank", "score", "points"]):
        high = 999999
        
    bounded = re.search(r"between\s+(\d{1,9})\s+and\s+(\d{1,9})", q)
    if bounded:
        try:
            low = int(bounded.group(1))
            high = int(bounded.group(2))
        except Exception:
            pass
            
    if low > high:
        low, high = high, low
    num = max(low, min(high, num))
    return str(num)

RULES = {
    "authorized to work": "Yes",
    "need sponsorship": "No",
    "notice period": "Immediate",
    "current location": "India",
}

def classify_field(field: dict):
    if field["type"] in ["text", "textarea"]:
        return "LLM"
    elif field["type"] in ["dropdown", "radio", "checkbox"]:
        return "RULE"
    elif "experience" in field["label"].lower():
        return "DERIVED"
    else:
        return "DEFAULT"

def _build_field_payload(
    label: str,
    field_type: str = "",
    options: list | None = None,
    input_type: str = "",
) -> dict:
    normalized_type = _compact_text(field_type).lower()
    if normalized_type in {"select", "combobox", "listbox"}:
        normalized_type = "dropdown"
    if normalized_type in {"input", ""}:
        normalized_type = "text"
    if normalized_type == "number":
        normalized_type = "text"
    if _compact_text(input_type).lower() == "checkbox":
        normalized_type = "checkbox"
    elif _compact_text(input_type).lower() == "radio":
        normalized_type = "radio"
    return {
        "label": _compact_text(label),
        "type": normalized_type,
        "input_type": _compact_text(input_type).lower(),
        "options": _real_options(options or []),
    }

def _normalize_bool_answer(value: str) -> str:
    v = _compact_text(value).lower()
    if v in {"yes", "true", "1", "y", "check", "checked"}:
        return "Yes"
    if v in {"no", "false", "0", "n", "uncheck", "unchecked"}:
        return "No"
    return _compact_text(value)

def _rule_to_option(rule_value: str, options: list[str]) -> str | None:
    opts = _real_options(options or [])
    if not opts:
        return _compact_text(rule_value) or None
    wanted = _compact_text(rule_value).lower()
    if not wanted:
        return None

    for opt in opts:
        ol = _compact_text(opt).lower()
        if ol == wanted:
            return opt
    for opt in opts:
        ol = _compact_text(opt).lower()
        if wanted in ol or ol in wanted:
            return opt

    if wanted in {"yes", "no"}:
        for opt in opts:
            ol = _compact_text(opt).lower()
            if ol.startswith(wanted):
                return opt
    if wanted == "immediate":
        immediate_markers = ["immediate", "immediately", "0", "same day"]
        for opt in opts:
            ol = _compact_text(opt).lower()
            if any(marker in ol for marker in immediate_markers):
                return opt
    return None

def _rule_engine_answer(field: dict, profile: dict) -> str | None:
    label = _compact_text(field.get("label", "")).lower()
    ftype = _compact_text(field.get("type", "")).lower()
    options = field.get("options") or []
    profile = profile if isinstance(profile, dict) else {}

    dynamic_rules = dict(RULES)
    location = _compact_text(profile.get("location", ""))
    if location:
        dynamic_rules["current location"] = location
    if profile.get("work_authorization"):
        dynamic_rules["authorized to work"] = str(profile.get("work_authorization"))
    if profile.get("sponsorship_required") is not None:
        dynamic_rules["need sponsorship"] = "Yes" if bool(profile.get("sponsorship_required")) else "No"

    # Question-key matching
    rule_value = None
    for key, value in dynamic_rules.items():
        if key in label:
            rule_value = str(value)
            break

    # Strong heuristics for common job form questions.
    if rule_value is None and ("authorized" in label and "work" in label):
        rule_value = dynamic_rules.get("authorized to work", "Yes")
    if rule_value is None and ("sponsorship" in label or "visa" in label):
        rule_value = dynamic_rules.get("need sponsorship", "No")
    if rule_value is None and "notice period" in label:
        rule_value = dynamic_rules.get("notice period", "Immediate")
    if rule_value is None and ("location" in label or "commuting" in label or "hybrid" in label):
        if "comfortable" in label:
            rule_value = "Yes"
        else:
            rule_value = dynamic_rules.get("current location", "India")

    # Checkbox/radio usually accept yes/no style answers.
    if rule_value is None and ftype == "checkbox":
        if _looks_like_legal_ack(label):
            rule_value = "Yes"

    if rule_value is None:
        return None
    rule_value = _normalize_bool_answer(rule_value)
    if options:
        return _rule_to_option(rule_value, options)
    return rule_value

def validate_answer(answer: str, field: dict) -> bool:
    value = _compact_text(answer)
    if not value:
        return False

    label = _compact_text(field.get("label", ""))
    ftype = _compact_text(field.get("type", "")).lower()
    input_type = _compact_text(field.get("input_type", "")).lower()
    options = _real_options(field.get("options") or [])

    if _looks_numeric_field(label, input_type):
        return _extract_first_int(value) is not None

    if ftype in {"dropdown", "radio"} and options:
        return _rule_to_option(value, options) is not None

    if ftype == "checkbox":
        normalized = _normalize_bool_answer(value).lower()
        return normalized in {"yes", "no"}

    return True

async def _safe_input_value(field) -> str:
    try:
        return _compact_text(await field.input_value())
    except Exception:
        pass
    try:
        value_attr = await field.get_attribute("value")
        return _compact_text(value_attr)
    except Exception:
        pass
    return ""

async def _type_field_dynamically(field, value: str) -> bool:
    text = _compact_text(value)
    if not text:
        return False
    try:
        await field.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        await field.click(timeout=2000)
    except Exception:
        pass
    try:
        await field.fill("")
    except Exception:
        pass
    try:
        await field.type(text, delay=random.randint(20, 70))
        try:
            await field.dispatch_event("change")
            await field.dispatch_event("blur")
        except Exception:
            pass
        return True
    except Exception:
        pass
    try:
        await field.fill(text)
        try:
            await field.dispatch_event("input")
            await field.dispatch_event("change")
            await field.dispatch_event("blur")
        except Exception:
            pass
        return True
    except Exception:
        return False

async def _field_has_error(field) -> bool:
    try:
        container = field.locator(
            "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
        )
        err = container.locator(
            ".artdeco-inline-feedback--error, [role='alert'], "
            ".fb-dash-form-element__error-message, .jobs-easy-apply-form-error"
        )
        return await err.count() > 0
    except Exception:
        return False

def _looks_like_legal_ack(question: str) -> bool:
    q = _compact_text(question).lower()
    markers = [
        "agree", "consent", "privacy", "policy", "terms", "declaration",
        "authorize", "permission", "gdpr", "confirm"
    ]
    return any(marker in q for marker in markers)

async def _is_checked_field(field, tag: str, input_type: str, role: str) -> bool:
    try:
        if role == "checkbox":
            return (await field.get_attribute("aria-checked") or "").lower() == "true"
    except Exception:
        pass
    try:
        if role == "radio":
            return (await field.get_attribute("aria-checked") or "").lower() == "true"
    except Exception:
        pass
    try:
        if tag == "input" and input_type in {"checkbox", "radio"}:
            return await field.is_checked()
    except Exception:
        pass
    return False

async def _click_option_by_text(scope, selection: str) -> bool:
    wanted = _compact_text(selection).lower()
    if not wanted:
        return False
    try:
        candidates = await scope.locator(
            "[role='option'], [role='radio'], .artdeco-dropdown__item, .artdeco-list__item, "
            "li, label, button, span, div, .fb-dropdown__item, .fb-single-select__option"
        ).all()
    except Exception:
        return False

    best = None
    for node in candidates:
        try:
            if not await node.is_visible():
                continue
            text = _compact_text(await node.inner_text())
            if not text:
                continue
            lower = text.lower()
            if lower == wanted:
                best = node
                break
            if wanted in lower or lower in wanted:
                best = best or node
        except Exception:
            continue
    if not best:
        return False
    try:
        await best.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        await best.click(force=True, timeout=2000)
        return True
    except Exception:
        return False

async def _dispatch_value_events(field) -> None:
    try:
        await field.dispatch_event("input")
        await field.dispatch_event("change")
        await field.dispatch_event("blur")
    except Exception:
        pass

async def _extract_select_option_pairs(select) -> list[tuple[str, str]]:
    option_pairs: list[tuple[str, str]] = []
    try:
        option_nodes = await select.locator("option").all()
        for node in option_nodes:
            label = _compact_text(await node.inner_text())
            value = _compact_text(await node.get_attribute("value"))
            if label:
                option_pairs.append((label, value))
    except Exception:
        return []
    return option_pairs

def _pick_option_pair(selection: str, option_pairs: list[tuple[str, str]]) -> tuple[str, str] | None:
    if not option_pairs:
        return None
    labels = [label for label, _ in option_pairs]
    chosen_label = _pick_option(selection, labels)
    chosen_label_l = _compact_text(chosen_label).lower()

    for label, value in option_pairs:
        if _compact_text(label).lower() == chosen_label_l:
            return label, value
    for label, value in option_pairs:
        ll = _compact_text(label).lower()
        if ll and (ll in chosen_label_l or chosen_label_l in ll):
            return label, value

    # Fallback to first non-placeholder, then first option.
    for label, value in option_pairs:
        if not _is_placeholder_option(label):
            return label, value
    return option_pairs[0]

async def _select_native_dropdown_value(
    select,
    question: str,
    profile: dict,
    job_context: dict,
    handled_questions: set,
) -> bool:
    option_pairs = await _extract_select_option_pairs(select)
    option_texts = _real_options([label for label, _ in option_pairs])
    if not option_texts:
        return False
    handled_questions.add(question)
    selection = await llm_form_answer(
        question,
        profile,
        options=option_texts,
        job_context=job_context,
        field_type="dropdown",
        input_type="select",
    )
    chosen = _pick_option_pair(selection, option_pairs)
    if not chosen:
        return False
    label, value = chosen

    selected_ok = False
    try:
        result = await select.select_option(label=label)
        selected_ok = bool(result)
    except Exception:
        selected_ok = False
    if not selected_ok and value:
        try:
            result = await select.select_option(value=value)
            selected_ok = bool(result)
        except Exception:
            selected_ok = False
    if not selected_ok:
        return False

    await _dispatch_value_events(select)
    await asyncio.sleep(0.2)
    return True

async def _set_checkbox_checked(cb, tag: str, input_type: str, role: str, modal_scope=None) -> bool:
    if await _is_checked_field(cb, tag, input_type, role):
        return True
    try:
        await cb.scroll_into_view_if_needed()
    except Exception:
        pass

    if tag == "input":
        try:
            await cb.check(force=True, timeout=1500)
            if await _is_checked_field(cb, tag, input_type, role):
                return True
        except Exception:
            pass
    try:
        await cb.click(force=True, timeout=1500)
        if await _is_checked_field(cb, tag, input_type, role):
            return True
    except Exception:
        pass

    try:
        cid = await cb.get_attribute("id")
        if cid and modal_scope is not None:
            label = modal_scope.locator(f"label[for='{cid}']").first
            if await label.count() > 0 and await label.is_visible():
                await label.scroll_into_view_if_needed()
                await label.click(force=True, timeout=1500)
                if await _is_checked_field(cb, tag, input_type, role):
                    return True
    except Exception:
        pass

    try:
        wrap_label = cb.locator("xpath=ancestor::label[1]").first
        if await wrap_label.count() > 0 and await wrap_label.is_visible():
            await wrap_label.scroll_into_view_if_needed()
            await wrap_label.click(force=True, timeout=1500)
            if await _is_checked_field(cb, tag, input_type, role):
                return True
    except Exception:
        pass

    try:
        await cb.focus()
        await cb.press("Space")
        if await _is_checked_field(cb, tag, input_type, role):
            return True
    except Exception:
        pass
    return False

async def _collect_dropdown_options(scope) -> list[str]:
    selectors = (
        "[role='option'], [role='listbox'] [role='option'], .artdeco-dropdown__item, "
        ".artdeco-list__item, .fb-dropdown__item, .fb-single-select__option, .fb-typeahead__result, "
        "li[role='option'], li[class*='option'], div[class*='option'], [role='radio']"
    )
    out: list[str] = []
    try:
        texts = await scope.locator(selectors).all_inner_texts()
        for text in texts:
            clean = _compact_text(text)
            if not clean:
                continue
            # Skip noisy paragraphs rendered inside option containers.
            if len(clean) > 120:
                continue
            if clean not in out:
                out.append(clean)
    except Exception:
        return []
    return _real_options(out)

async def _collect_native_radio_groups(modal_scope) -> dict[str, list]:
    groups: dict[str, list] = {}
    radios = await modal_scope.locator("input[type='radio']").all()
    for idx, radio in enumerate(radios):
        try:
            name = _compact_text(await radio.get_attribute("name"))
            if not name:
                container = radio.locator(
                    "xpath=ancestor::*[self::fieldset or @role='radiogroup' or contains(@class,'fb-dash-form-element')][1]"
                ).first
                if await container.count() > 0:
                    container_text = _compact_text(await container.inner_text())
                    if container_text:
                        name = f"radio_group_{container_text[:120]}"
            if not name:
                name = f"radio_group_{idx}"
            groups.setdefault(name, []).append(radio)
        except Exception:
            continue
    return groups

async def _radio_option_label(radio, modal_scope) -> str:
    try:
        aria = _compact_text(await radio.get_attribute("aria-label"))
        if aria:
            return aria
    except Exception:
        pass
    try:
        rid = await radio.get_attribute("id")
        if rid:
            linked_label = modal_scope.locator(f"label[for='{rid}']").first
            if await linked_label.count() > 0:
                text = _compact_text(await linked_label.inner_text())
                if text:
                    return text
    except Exception:
        pass
    try:
        wrap_label = radio.locator("xpath=ancestor::label[1]").first
        if await wrap_label.count() > 0:
            text = _compact_text(await wrap_label.inner_text())
            if text:
                return text
    except Exception:
        pass
    try:
        sibling_label = radio.locator("xpath=following-sibling::label[1]").first
        if await sibling_label.count() > 0:
            text = _compact_text(await sibling_label.inner_text())
            if text:
                return text
    except Exception:
        pass
    try:
        sibling = radio.locator("xpath=following-sibling::*[1]").first
        if await sibling.count() > 0:
            text = _compact_text(await sibling.inner_text())
            if text:
                return text.split("\n")[0][:80]
    except Exception:
        pass
    try:
        value = _compact_text(await radio.get_attribute("value"))
        if value:
            return value
    except Exception:
        pass
    return ""

async def _click_native_radio_by_label(group_radios: list, label: str, modal_scope) -> bool:
    wanted = _compact_text(label).lower()
    if not wanted:
        return False
    first_visible = None
    for radio in group_radios:
        try:
            if await radio.is_visible():
                first_visible = first_visible or radio
            text = (await _radio_option_label(radio, modal_scope)).lower()
            value = _compact_text(await radio.get_attribute("value")).lower()
            tokens = [tok for tok in [text, value] if tok]
            matched = any(tok == wanted or wanted in tok or tok in wanted for tok in tokens)
            if not matched and wanted in {"yes", "no"}:
                matched = any(tok.startswith(wanted[0]) for tok in tokens if tok)
            if matched:
                rid = await radio.get_attribute("id")
                if rid:
                    linked_label = modal_scope.locator(f"label[for='{rid}']").first
                    if await linked_label.count() > 0 and await linked_label.is_visible():
                        await linked_label.scroll_into_view_if_needed()
                        await linked_label.click(force=True)
                        return True
                await radio.scroll_into_view_if_needed()
                await radio.check(force=True)
                return True
        except Exception:
            continue
    if first_visible:
        try:
            await first_visible.scroll_into_view_if_needed()
            await first_visible.check(force=True)
            return True
        except Exception:
            pass
    return False

async def _resolve_required_dropdown_errors(
    modal_scope,
    app_page,
    profile: dict,
    job_context: dict,
    handled_questions: set,
) -> int:
    resolved = 0
    try:
        error_nodes = await modal_scope.locator(
            ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, "
            ".jobs-easy-apply-form-error, text=/please make a selection/i"
        ).all()
    except Exception:
        return 0

    for err in error_nodes[:10]:
        try:
            if not await err.is_visible():
                continue
        except Exception:
            continue
        try:
            container = err.locator(
                "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
            )
            if await container.count() == 0:
                continue

            # 1) Try native select first, even if hidden.
            select = container.locator("select").first
            if await select.count() > 0:
                question = await _field_question_text(select, modal_scope)
                if not question:
                    question = _compact_text(await container.inner_text())
                selected = await _select_native_dropdown_value(
                    select=select,
                    question=question,
                    profile=profile,
                    job_context=job_context,
                    handled_questions=handled_questions,
                )
                if selected:
                    await asyncio.sleep(0.3)
                    if not await _field_has_error(select):
                        resolved += 1
                        continue

            # 2) Try custom dropdown trigger in this error block.
            trigger_selectors = [
                "[role='combobox']",
                "button[aria-haspopup]",
                "button[class*='dropdown']",
                "div[class*='dropdown']",
                "div[class*='select']",
                "input[readonly]",
                "div[role='button']",
            ]
            trigger = None
            for ts in trigger_selectors:
                cand = container.locator(ts).first
                if await cand.count() > 0:
                    trigger = cand
                    break
            if not trigger:
                continue

            try:
                if not await trigger.is_visible():
                    continue
            except Exception:
                continue

            question = await _field_question_text(trigger, modal_scope)
            if not question:
                question = _compact_text(await container.inner_text())
            if question:
                handled_questions.add(question)

            await trigger.scroll_into_view_if_needed()
            await trigger.click(force=True)
            await asyncio.sleep(0.8)

            option_texts = await _collect_dropdown_options(app_page.locator("body"))
            if not option_texts:
                await app_page.keyboard.press("ArrowDown")
                await app_page.keyboard.press("Enter")
                await asyncio.sleep(0.3)
                if not await _field_has_error(trigger):
                    resolved += 1
                continue

            selection = await llm_form_answer(
                question,
                profile,
                options=option_texts,
                job_context=job_context,
                field_type="dropdown",
                input_type="select",
            )
            clicked = await _click_option_by_text(app_page.locator("body"), selection)
            if not clicked:
                await app_page.keyboard.press("ArrowDown")
                await app_page.keyboard.press("Enter")
            await asyncio.sleep(0.4)
            if not await _field_has_error(trigger):
                resolved += 1
        except Exception:
            continue

    return resolved

async def _resolve_required_numeric_errors(
    modal_scope,
    profile: dict,
    job_context: dict,
    handled_questions: set,
) -> int:
    resolved = 0
    try:
        error_nodes = await modal_scope.locator(
            ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, "
            ".jobs-easy-apply-form-error, text=/whole number|enter a number|valid number/i"
        ).all()
    except Exception:
        return 0

    for err in error_nodes[:14]:
        try:
            if not await err.is_visible():
                continue
            container = err.locator(
                "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
            )
            if await container.count() == 0:
                continue

            fields = await container.locator(
                "input:not([type='hidden']):not([type='checkbox']):not([type='radio']):not([type='file'])"
            ).all()
            if not fields:
                continue

            for field in fields:
                if not await field.is_visible():
                    continue
                question = await _field_question_text(field, modal_scope)
                if not question:
                    question = _compact_text(await container.inner_text())
                handled_questions.add(question)

                input_type = (await field.get_attribute("type") or "text").lower()
                answer = await llm_form_answer(
                    question,
                    profile,
                    job_context=job_context,
                    field_type="text",
                    input_type=input_type,
                )
                if _looks_numeric_field(question, input_type):
                    answer = _coerce_numeric_answer(answer, question, profile)
                if not answer or answer == "N/A":
                    continue

                typed = await _type_field_dynamically(field, answer)
                if not typed:
                    continue
                await asyncio.sleep(0.25)
                if not await _field_has_error(field):
                    resolved += 1
        except Exception:
            continue
    return resolved

async def _resolve_required_radio_errors(
    modal_scope,
    profile: dict,
    job_context: dict,
    handled_questions: set,
) -> int:
    resolved = 0
    try:
        error_nodes = await modal_scope.locator(
            ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, "
            ".jobs-easy-apply-form-error, text=/please make a selection/i"
        ).all()
    except Exception:
        return 0

    for err in error_nodes[:12]:
        try:
            if not await err.is_visible():
                continue
            container = err.locator(
                "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
            )
            if await container.count() == 0:
                continue

            # Native radio inputs
            radios = await container.locator("input[type='radio']").all()
            if radios:
                question = await _field_question_text(radios[0], modal_scope)
                if not question:
                    question = _compact_text(await container.inner_text())
                options_txt = _real_options([await _radio_option_label(r, modal_scope) for r in radios])
                if not options_txt and len(radios) == 2:
                    options_txt = ["Yes", "No"]
                if not options_txt:
                    continue
                handled_questions.add(question)
                selection = await llm_form_answer(
                    question,
                    profile,
                    options=options_txt,
                    job_context=job_context,
                    field_type="radio",
                    input_type="radio",
                )
                clicked = await _click_native_radio_by_label(radios, selection, modal_scope)
                if not clicked:
                    try:
                        await radios[0].check(force=True)
                    except Exception:
                        pass
                await asyncio.sleep(0.2)
                if not await _field_has_error(radios[0]):
                    resolved += 1
                continue

            # Custom label-based radio buttons
            question = _compact_text(await container.inner_text())
            raw_opts = []
            for txt in await container.locator("label, [role='radio'], div[class*='radio'], span").all_inner_texts():
                t = _compact_text(txt)
                if not t:
                    continue
                tl = t.lower()
                if "please make a selection" in tl:
                    continue
                if len(t) > 90:
                    continue
                raw_opts.append(t)
            options_txt = _real_options(raw_opts)
            if 2 <= len(options_txt) <= 8:
                handled_questions.add(question)
                selection = await llm_form_answer(
                    question,
                    profile,
                    options=options_txt,
                    job_context=job_context,
                    field_type="radio",
                    input_type="radio",
                )
                clicked = await _click_option_by_text(container, selection)
                if not clicked:
                    await _click_option_by_text(container, options_txt[0])
                await asyncio.sleep(0.2)
                if await container.locator(
                    ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, .jobs-easy-apply-form-error"
                ).count() == 0:
                    resolved += 1
        except Exception:
            continue
    return resolved

async def _resolve_required_checkbox_errors(
    modal_scope,
    profile: dict,
    job_context: dict,
    handled_questions: set,
) -> int:
    resolved = 0
    try:
        error_nodes = await modal_scope.locator(
            ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, "
            ".jobs-easy-apply-form-error, text=/please check|required|consent|agree/i"
        ).all()
    except Exception:
        return 0

    for err in error_nodes[:12]:
        try:
            if not await err.is_visible():
                continue
            container = err.locator(
                "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
            )
            if await container.count() == 0:
                continue

            boxes = await container.locator("input[type='checkbox'], [role='checkbox']").all()
            if not boxes:
                continue

            unresolved = False
            for cb in boxes:
                role = (await cb.get_attribute("role") or "").lower()
                tag = (await cb.evaluate("el => el.tagName.toLowerCase()")).lower()
                input_type = (await cb.get_attribute("type") or "").lower()
                if await _is_checked_field(cb, tag, input_type, role):
                    continue
                question = await _field_question_text(cb, modal_scope)
                if not question:
                    question = _compact_text(await container.inner_text())
                handled_questions.add(question)

                required_attr = await cb.get_attribute("required")
                aria_required = (await cb.get_attribute("aria-required") or "").lower()
                must_check = bool(required_attr) or aria_required == "true" or _looks_like_legal_ack(question)
                if not must_check:
                    ans = await llm_form_answer(
                        question,
                        profile,
                        options=["Yes", "No"],
                        job_context=job_context,
                        field_type="checkbox",
                        input_type="checkbox",
                    )
                    # Handle both list and string return types
                    if isinstance(ans, list):
                        must_check = any("yes" in str(a).lower() for a in ans)
                    else:
                        must_check = str(ans).lower().startswith("y")
                
                if not must_check:
                    # If LLM says no and it's not strictly required, skip
                    unresolved = True
                    continue


                ok = await _set_checkbox_checked(cb, tag, input_type, role, modal_scope=modal_scope)
                if not ok:
                    unresolved = True

            await asyncio.sleep(0.2)
            if not unresolved and await container.locator(
                ".artdeco-inline-feedback--error, .fb-dash-form-element__error-message, .jobs-easy-apply-form-error"
            ).count() == 0:
                resolved += 1
        except Exception:
            continue
    return resolved

async def llm_form_answer(
    field_hint: str,
    profile: dict,
    options: list = None,
    tailored_context: str = "",
    job_context: dict | None = None,
    field_type: str = "text",
    input_type: str = "",
) -> str | list[str]:
    """
    Consolidated form answering using the Core Engine (BRAIN).
    Returns the raw string answer for text fields, or a list of strings for checkboxes.
    """
    hint = re.sub(r"\s+", " ", str(field_hint or "")).strip().lower()
    if not hint:
        return "N/A"

    job_context = job_context or {}
    field_payload = _build_field_payload(field_hint, field_type=field_type, options=options, input_type=input_type)
    field_options = field_payload["options"]
    
    cache_key = (
        f"{job_context.get('job_id', '')}_"
        f"{hint}_{field_payload.get('type','')}_{field_payload.get('input_type','')}_{','.join(field_options)}"
    )
    if cache_key in FORM_ANSWER_CACHE:
        return FORM_ANSWER_CACHE[cache_key]

    # 1. Map to Engine Dataclasses
    job_input = JobInput.from_dict(job_context)
    user_profile = UserProfile.from_dict(profile)
    form_field = FormField(question=field_hint, field_type=field_type, options=field_options)

    # 2. Prepare RAG Context
    resume_text = profile.get("resume_text", "")
    tailored_text = tailored_context or profile.get("tailored_resume_text", "")
    resume_data = profile.get("resume_data", {})
    job_description = job_context.get("job_description", "") or job_context.get("job_description_clean", "")

    # Retrieve relevant chunks for this specific question
    retrieval_query = f"{field_hint} {job_input.title} {','.join(job_input.description.split()[:30])}"
    rag_chunks = _retrieve_relevant_chunks(
        retrieval_query,
        [resume_text, tailored_text, json.dumps(resume_data, ensure_ascii=False), job_description],
        limit=5
    )
    rag_context = "\n".join(f"- {c}" for c in rag_chunks)

    # 3. Call Brain
    log_info(f"BRAIN Analyzing Form Field: {field_hint[:80]}")
    result = await BRAIN.answer(form_field, job_input, user_profile, resume_context=rag_context)

    # 4. Handle Result Mapping
    if field_type == "checkbox":
        final_answer = result["selected_options"]
    elif field_type in ["radio", "dropdown"] and field_options:
        # Priority: selected_option -> fallback to answer string check
        final_answer = result["selected_option"]
        if not final_answer:
            # Check if answer contains one of the options
            for opt in field_options:
                if opt.lower() in str(result["answer"]).lower():
                    final_answer = opt
                    break
        if not final_answer:
            final_answer = field_options[0]
    else:
        final_answer = result["answer"]

    # Post-process
    if isinstance(final_answer, str):
        final_answer = final_answer.strip()
        if not final_answer:
            final_answer = "N/A"
    
    log_info(f"BRAIN Submitting Answer: {str(final_answer)[:100]}")
    FORM_ANSWER_CACHE[cache_key] = final_answer
    return final_answer


async def _field_question_text(field, modal_scope) -> str:
    parts = []
    for attr in ["aria-label", "placeholder", "name", "id"]:
        try:
            value = await field.get_attribute(attr)
            if value:
                parts.append(value)
        except Exception:
            pass

    try:
        field_id = await field.get_attribute("id")
        if field_id:
            label = modal_scope.locator(f"label[for='{field_id}']").first
            if await label.count() > 0:
                parts.insert(0, await label.inner_text())
    except Exception:
        pass

    try:
        container_text = await field.locator(
            "xpath=ancestor::*[self::div or self::section or self::fieldset][1]"
        ).inner_text(timeout=1000)
        if container_text:
            parts.append(container_text)
    except Exception:
        pass

    return _compact_text(" ".join(parts))

async def linkedin_apply_job(
    page,
    resume_pdf: Path,
    profile: dict,
    job_url: str = None,
    job_context: dict | None = None,
) -> bool:
    """Phase 2: Navigate to job and apply using robust multi-step logic."""
    log_info("Entered Easy Apply function.")
    job_context = job_context or {}
    if not resume_pdf:
        log_warn("No resume PDF provided. Skipping apply phase.")
        return False
        
    if job_url:
        log_info(f"Navigating to job URL: {job_url}")
        try:
            # Use 'commit' for faster/more reliable navigation redirects
            await page.goto(job_url, wait_until="commit", timeout=45000, referer="https://www.linkedin.com/jobs/")
            await asyncio.sleep(random.uniform(5, 8)) # Human-like load wait
            log_info(f"Navigation successful. Current URL: {page.url}")
        except Exception as e:
            log_err(f"Navigation to job failed: {e}")
            return False
        
    log_info(f"Attempting Easy Apply with: {resume_pdf.name}")
    
    # 1. Open Modal (Handle possible popup vs same-tab modal)
    # Target specific apply button selectors
    selectors = [
        "button.jobs-apply-button",
        "button[aria-label*='Easy Apply']:not([role='radio']):not([id*='searchFilter'])",
        ".jobs-apply-button--top-card button"
    ]
    
    easy_apply_btn = None
    for sel in selectors:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            easy_apply_btn = btn
            break

    if not easy_apply_btn:
        log_warn("Easy Apply button not found on this page. Might be a complex form or already applied.")
        return False

    log_info("Found Easy Apply button. Attempting click...")

    # Detection logic for popup vs modal (with stealth)
    app_page = page
    try:
        # Extra stealthy wait
        await easy_apply_btn.hover()
        await asyncio.sleep(random.uniform(1.0, 2.5))
        
        async with page.expect_popup(timeout=3000) as popup_info:
            # Use retry for the click action
            await retry_action(lambda: easy_apply_btn.click(timeout=8000))
        app_page = await popup_info.value
        log_info("Application opened in a NEW TAB.")
    except Exception as e:
        # Fallback check: Did it redirect the main page?
        await asyncio.sleep(1)
        if is_login_wall(page):
            log_err("[ALERT] LinkedIn blocked the application and redirected the main page to login.")
            return False

        # Same-tab modals are common: if modal is already visible after the first click,
        # do not click again (it causes interception by form inputs inside the modal).
        modal = page.locator("div[role='dialog']").last
        try:
            if await modal.count() > 0 and await modal.is_visible():
                log_info("Application opened in a MODAL.")
            else:
                await retry_action(lambda: easy_apply_btn.click(timeout=8000))
                log_info("Application opened in a MODAL.")
        except Exception as e2:
            safe_error = str(e2).encode("ascii", "ignore").decode("ascii")
            log_err(f"[SKIP] Easy Apply click failed. Likely complex form or already applied. Error: {safe_error}")
            return False

    await asyncio.sleep(random.uniform(2.5, 3.5))
    
    # 2. Process Steps (use app_page which is either the main page or the popup)
    max_steps = 20
    phone_digits = re.sub(r"\D", "", profile.get("phone", "")) or "9876543210"

    for step in range(1, max_steps + 1):
        # Session check: Use the new wall detection
        if is_login_wall(app_page):
            log_err("Login wall detected during apply sequence.")
            if not await ensure_session(app_page):
                return False

        log_info(f"Processing application step {step}...")
        # Reduce redundant behavior simulation inside the modal to speed up flow
        if step % 3 == 0: await simulate_human_behavior(app_page)
        await asyncio.sleep(random.uniform(0.5, 1.5)) 
        
        # Modal scope detection
        modal = app_page.locator("div[role='dialog']").last
        modal_scope = modal if await modal.count() > 0 else app_page.locator("body")
        
        # --- Internal Modal Scroll ---
        try:
            await modal_scope.evaluate("el => el.scrollTo(0, 0)")
            await asyncio.sleep(0.5)
        except: pass

        # Check for immediate success
        success_indicators = [
            "text=Application submitted", "text=Your application was sent", 
            "text=Applied", ".artdeco-inline-feedback--success"
        ]
        for indicator in success_indicators:
            try:
                el = modal_scope.locator(indicator).first
                if await el.count() > 0 and await el.is_visible():
                    log_ok("âœ… APPLICATION SUBMITTED SUCCESSFULLY!")
                    close_btn = page.locator("button[aria-label*='Dismiss'], button[aria-label*='Close']").first
                    if await close_btn.count() > 0: await close_btn.click()
                    return True
            except: pass

        # --- Fill Forms ---
        handled_questions = set()

        # 1. Personal Details / Contact / Socials
        # Target: Phone, Email, Name, Social Links
        contact_selectors = [
            "input[id*='phoneNumber'], input[name*='phone'], input[aria-label*='phone']",
            "input[id*='email'], input[name*='email'], input[aria-label*='email']",
            "input[id*='firstName'], input[name*='firstName'], input[aria-label*='first name']",
            "input[id*='lastName'], input[name*='lastName'], input[aria-label*='last name']",
            "input[aria-label*='LinkedIn'], input[name*='linkedin'], input[id*='linkedin']",
            "input[aria-label*='GitHub'], input[name*='github'], input[id*='github']",
            "input[aria-label*='portfolio'], input[name*='portfolio'], input[id*='portfolio']"
        ]
        for cs in contact_selectors:
            field = modal_scope.locator(cs).first
            current_value = await _safe_input_value(field) if await field.count() > 0 else ""
            if await field.count() > 0 and await field.is_visible() and not current_value:
                question = await _field_question_text(field, modal_scope)
                handled_questions.add(question)
                input_type = (await field.get_attribute("type") or "text").lower()
                answer = await llm_form_answer(
                    question,
                    profile,
                    job_context=job_context,
                    field_type="text",
                    input_type=input_type,
                )
                if isinstance(answer, list):
                    answer = ", ".join(map(str, answer))
                
                if "phone" in question.lower() and (not answer or answer == "N/A"):
                    answer = profile.get("phone", "") or phone_digits
                if "email" in question.lower() and (not answer or answer == "N/A"):
                    answer = profile.get("email", "")
                if _looks_numeric_field(question, input_type):
                    answer = _coerce_numeric_answer(answer, question, profile)
                if answer and answer != "N/A":
                    log_info(f"Filling personal detail '{question[:30]}': {answer[:50]}")
                    await _type_field_dynamically(field, answer)


        # 2. Resume Upload (Only if prompted)
        file_inputs = modal_scope.locator("input[type='file']")
        if await file_inputs.count() > 0:
            try:
                await file_inputs.first.set_input_files(str(resume_pdf), timeout=5000)
                # Step 7: Add delay (Human-mimetic registration delay)
                await asyncio.sleep(2)
            except: pass

        # 3. Handle Radio/Single Choice Groups
        # We look for fieldsets (standard) AND standalone radio groups
        choice_selectors = ["fieldset", "[role='radiogroup']"]
        for sel in choice_selectors:
            groups = modal_scope.locator(sel).all()
            for group in await groups:
                try:
                    legend = await group.locator("legend, [role='heading'], label").first.inner_text() if await group.locator("legend, [role='heading'], label").count() > 0 else "Choice"
                    options_loc = group.locator("label, [role='radio']")
                    options_txt = _real_options([o.strip() for o in await options_loc.all_inner_texts() if o.strip()])
                    if options_txt:
                        handled_questions.add(_compact_text(legend))
                        selection = await llm_form_answer(
                            legend,
                            profile,
                            options=options_txt,
                            job_context=job_context,
                            field_type="radio",
                            input_type="radio",
                        )
                        log_info(f"Selecting radio option '{selection}' for: {legend[:40]}")
                        await _click_option_by_text(group, selection)
                        await asyncio.sleep(0.5)
                except: pass

        # 3B. Handle native radio groups even when labels are outside fieldset/radiogroup wrappers
        radio_groups = await _collect_native_radio_groups(modal_scope)
        for _, group_radios in radio_groups.items():
            try:
                if not group_radios:
                    continue
                already_checked = False
                for radio in group_radios:
                    if await _is_checked_field(radio, "input", "radio", "radio"):
                        already_checked = True
                        break
                sample = group_radios[0]
                is_stuck = await _field_has_error(sample)
                if already_checked and not is_stuck:
                    continue

                question = await _field_question_text(sample, modal_scope)
                if not question:
                    question = "Radio choice"
                options_txt = _real_options([
                    await _radio_option_label(r, modal_scope) for r in group_radios
                ])
                if not options_txt and len(group_radios) == 2:
                    options_txt = ["Yes", "No"]
                if not options_txt:
                    continue
                handled_questions.add(question)
                selection = await llm_form_answer(
                    question,
                    profile,
                    options=options_txt,
                    job_context=job_context,
                    field_type="radio",
                    input_type="radio",
                )
                await _click_native_radio_by_label(group_radios, selection, modal_scope)
                await asyncio.sleep(0.3)
            except Exception:
                pass

        # 4. Handle Checkboxes (Mandatory/Legal)
        checkboxes = modal_scope.locator("input[type='checkbox'], [role='checkbox']").all()
        for cb in await checkboxes:
            try:
                role = (await cb.get_attribute("role") or "").lower()
                tag = (await cb.evaluate("el => el.tagName.toLowerCase()")).lower()
                input_type = (await cb.get_attribute("type") or "").lower()
                if await _is_checked_field(cb, tag, input_type, role):
                    continue
                question = await _field_question_text(cb, modal_scope)
                handled_questions.add(question)
                must_check = _looks_like_legal_ack(question)
                if not must_check:
                    required_attr = await cb.get_attribute("required")
                    aria_required = (await cb.get_attribute("aria-required") or "").lower()
                    must_check = bool(required_attr) or aria_required == "true"
                should_check = must_check
                if not should_check:
                    ans = await llm_form_answer(
                        question,
                        profile,
                        options=["Yes", "No"],
                        job_context=job_context,
                        field_type="checkbox",
                        input_type="checkbox",
                    )
                    if isinstance(ans, list):
                        should_check = any("yes" in str(a).lower() for a in ans)
                    else:
                        should_check = str(ans).lower().startswith("y")

                if should_check:
                    await _set_checkbox_checked(cb, tag, input_type, role, modal_scope=modal_scope)
            except: pass

        # 5. Handle Native Selects
        select_fields = modal_scope.locator("select").all()
        for select in await select_fields:
            try:
                selected_label = ""
                try:
                    selected_label = _compact_text(await select.locator("option:checked").first.inner_text())
                except Exception:
                    pass
                current_val = await _safe_input_value(select)
                has_error = await _field_has_error(select)
                if (selected_label and not _is_placeholder_option(selected_label) and not has_error) or (
                    current_val and not _is_placeholder_option(current_val) and not has_error
                ):
                    continue

                question = await _field_question_text(select, modal_scope)
                await _select_native_dropdown_value(
                    select=select,
                    question=question,
                    profile=profile,
                    job_context=job_context,
                    handled_questions=handled_questions,
                )
                await asyncio.sleep(0.5)
            except: pass

        # 6. Handle CUSTOM Dropdowns (ARIA Combobox/Listbox)
        custom_dropdown_selectors = [
            "button[aria-haspopup='listbox']",
            "button[aria-haspopup='true']",
            "div[role='combobox']",
            "div[aria-haspopup='listbox']",
            "button[class*='dropdown']",
            "div[class*='dropdown']",
            "div[class*='select']",
            "input[readonly]"
        ]
        seen_dropdown_keys = set()
        for ds in custom_dropdown_selectors:
            dropdowns = modal_scope.locator(ds).all()
            for dd in await dropdowns:
                try:
                    if not await dd.is_visible():
                        continue
                    dd_key = "|".join(
                        [
                            _compact_text(await dd.get_attribute("id")),
                            _compact_text(await dd.get_attribute("name")),
                            _compact_text(await dd.get_attribute("aria-controls")),
                            _compact_text(await dd.get_attribute("aria-label")),
                        ]
                    )
                    if dd_key and dd_key in seen_dropdown_keys:
                        continue
                    if dd_key:
                        seen_dropdown_keys.add(dd_key)
                    # Skip if already has a value (heuristic)
                    current_text = _compact_text(await dd.inner_text())
                    has_error = await _field_has_error(dd)
                    if current_text and not _is_placeholder_option(current_text) and not has_error:
                        continue
                    
                    question = await _field_question_text(dd, modal_scope)
                    if question:
                        handled_questions.add(question)
                    
                    # STEP 1: EXPAND (Click to open)
                    await dd.click(force=True)
                    await asyncio.sleep(random.uniform(1.0, 2.0)) # Wait for menu to render
                    
                    # STEP 2: READ (Capture options from global page scope)
                    menu_selectors = [".artdeco-dropdown__content", "[role='listbox']", ".fb-dropdown__list", ".artdeco-dropdown__item"]
                    options_txt = []
                    found_menu = None
                    for ms in menu_selectors:
                        menu = app_page.locator(ms).last
                        if await menu.count() > 0 and await menu.is_visible():
                            found_menu = menu
                            options_txt = await _collect_dropdown_options(menu)
                            if options_txt: break
                    if not options_txt:
                        options_txt = await _collect_dropdown_options(app_page.locator("body"))
                    
                    # STEP 3: ANALYZE & SELECT
                    if options_txt:
                        selection = await llm_form_answer(
                            question,
                            profile,
                            options=options_txt,
                            job_context=job_context,
                            field_type="dropdown",
                            input_type="select",
                        )
                        
                        log_info(f"Selecting '{selection}' for: {question[:40]}")
                        
                        clicked = await _click_option_by_text(found_menu, selection) if found_menu else False
                        if not clicked:
                            clicked = await _click_option_by_text(modal_scope, selection)
                        if not clicked:
                            clicked = await _click_option_by_text(app_page.locator("body"), selection)
                        if clicked:
                            await asyncio.sleep(0.5)
                            await _dispatch_value_events(dd)
                        else:
                            await app_page.keyboard.press("ArrowDown")
                            await app_page.keyboard.press("Enter")
                            await app_page.keyboard.press("Escape")
                    else:
                        # If no menu found, close popup safely
                        await app_page.keyboard.press("ArrowDown")
                        await app_page.keyboard.press("Enter")
                        await app_page.keyboard.press("Escape")
                except Exception as e: 
                    pass

        # 6B. Error-driven fallback for unresolved required dropdowns.
        try:
            resolved_count = await _resolve_required_dropdown_errors(
                modal_scope=modal_scope,
                app_page=app_page,
                profile=profile,
                job_context=job_context,
                handled_questions=handled_questions,
            )
            if resolved_count:
                log_info(f"Resolved {resolved_count} pending dropdown validation field(s).")
        except Exception:
            pass

        # 6C. Error-driven fallback for unresolved required numeric fields.
        try:
            numeric_fixed = await _resolve_required_numeric_errors(
                modal_scope=modal_scope,
                profile=profile,
                job_context=job_context,
                handled_questions=handled_questions,
            )
            if numeric_fixed:
                log_info(f"Resolved {numeric_fixed} pending numeric validation field(s).")
        except Exception:
            pass

        # 6D. Error-driven fallback for unresolved required radio/single-choice fields.
        try:
            radio_fixed = await _resolve_required_radio_errors(
                modal_scope=modal_scope,
                profile=profile,
                job_context=job_context,
                handled_questions=handled_questions,
            )
            if radio_fixed:
                log_info(f"Resolved {radio_fixed} pending radio validation field(s).")
        except Exception:
            pass

        # 6E. Error-driven fallback for unresolved required checkboxes.
        try:
            cb_fixed = await _resolve_required_checkbox_errors(
                modal_scope=modal_scope,
                profile=profile,
                job_context=job_context,
                handled_questions=handled_questions,
            )
            if cb_fixed:
                log_info(f"Resolved {cb_fixed} pending checkbox validation field(s).")
        except Exception:
            pass

        # 7. Generic Catch-all Scanner (Role-based discovery)
        # This handles custom labels that are interactive but don't match standard selectors
        generic_interactive = [
            "input:not([type='hidden'])",
            "textarea",
            "select",
            "[role='combobox']",
            "[role='checkbox']",
            "[role='radio']",
            "button[aria-haspopup]"
        ]
        all_inputs = modal_scope.locator(", ".join(generic_interactive)).all()
        for field in await all_inputs:
            try:
                if not await field.is_visible():
                    continue
                # Check for red error messages nearby - priority if stuck
                is_stuck = await _field_has_error(field)
                current_value = await _safe_input_value(field)

                if is_stuck or not current_value:
                    question = await _field_question_text(field, modal_scope)
                    # Deduplicate: if we already handled this question in earlier specific loops, skip
                    if question in handled_questions:
                        continue
                    if question:
                        handled_questions.add(question)
                    
                    # log_info(f"Catch-all scanner handling field: {question[:50]}")
                    # Fill or click based on role
                    role = (await field.get_attribute("role") or "").lower()
                    tag = (await field.evaluate("el => el.tagName.toLowerCase()")).lower()
                    input_type = (await field.get_attribute("type") or "text").lower()
                    
                    if tag in ["input", "textarea"] and input_type not in ["checkbox", "radio", "file"]:
                        inferred_type = "textarea" if tag == "textarea" else "text"
                        answer = await llm_form_answer(
                            question,
                            profile,
                            job_context=job_context,
                            field_type=inferred_type,
                            input_type=input_type,
                        )
                        if input_type in {"email"} and (not answer or answer == "N/A"):
                            answer = profile.get("email", "")
                        if "phone" in question.lower() and (not answer or answer == "N/A"):
                            answer = profile.get("phone", "") or phone_digits
                        if _looks_numeric_field(question, input_type):
                            answer = _coerce_numeric_answer(answer, question, profile)
                        if answer and answer != "N/A":
                            await _type_field_dynamically(field, answer)
                    elif role == "checkbox" or (tag == "input" and input_type == "checkbox"):
                        if not await _is_checked_field(field, tag, input_type, role):
                            ans = await llm_form_answer(
                                question,
                                profile,
                                options=["Yes", "No"],
                                job_context=job_context,
                                field_type="checkbox",
                                input_type="checkbox",
                            )
                            if isinstance(ans, list):
                                is_affirmed = any("yes" in str(a).lower() for a in ans)
                            else:
                                is_affirmed = str(ans).lower().startswith("y")
                            
                            if is_affirmed or _looks_like_legal_ack(question):
                                await _set_checkbox_checked(field, tag, input_type, role, modal_scope=modal_scope)

                    elif role == "radio" or (tag == "input" and input_type == "radio"):
                        if not await _is_checked_field(field, tag, input_type, role):
                            group = field.locator("xpath=ancestor::*[@role='radiogroup' or self::fieldset][1]")
                            group_scope = group if await group.count() > 0 else modal_scope
                            options_txt = _real_options(
                                [o.strip() for o in await group_scope.locator("label, [role='radio']").all_inner_texts() if o.strip()]
                            )
                            if not options_txt:
                                grouped = await _collect_native_radio_groups(group_scope)
                                for radios in grouped.values():
                                    if len(radios) == 2:
                                        options_txt = ["Yes", "No"]
                                        break
                            if options_txt:
                                selection = await llm_form_answer(
                                    question,
                                    profile,
                                    options=options_txt,
                                    job_context=job_context,
                                    field_type="radio",
                                    input_type="radio",
                                )
                                await _click_option_by_text(group_scope, selection)
            except: pass

        # 8. Final Submit/Next
        submit_btn = modal_scope.locator(
            "button:has-text('Submit application'), button:has-text('Next'), "
            "button:has-text('Review'), button:has-text('Continue'), "
            "button:has-text('Continue to next step')"
        ).last
        application_sent = False
        
        if await submit_btn.count() > 0:
            btn_text = await submit_btn.inner_text()
            log_info(f"Stealth clicking '{btn_text}'...")
            # Use retry with force=True for the click action
            try:
                await retry_action(lambda: submit_btn.click(timeout=8000, force=True))
                await asyncio.sleep(random.uniform(5.0, 8.0)) # Increased delay for safety
                if "submit" in btn_text.lower():
                    application_sent = True
            except Exception as e:
                log_err(f"Click failed on '{btn_text}': {e}")
                return False
        else:
            log_warn("[SKIP] No 'Next' or 'Submit' button found. Form might be too complex or unusual.")
            return False
        
        # Check if modal closed (success sign) or if we reached the end
        if application_sent:
            log_ok("Success! Application submitted.")
            return True

    return False



