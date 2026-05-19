import os
import json
import re
import asyncio
from pathlib import Path
import sys

# Add project root for ai_job_auto_apply imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from ai_job_auto_apply.job_application_engine import ResumeTailor, UserProfile, JobInput
except ImportError:
    # Fallback if pathing is weird
    sys.path.append(str(PROJECT_ROOT / "ai_job_auto_apply"))
    from job_application_engine import ResumeTailor, UserProfile, JobInput

from pipeline.pdf_service import pdf_service
from pipeline.llm import openrouter_call, parse_json_from_llm
from pipeline.config import OPENROUTER_MODEL, GROQ_API_KEY, GOOGLE_API_KEY, OPENROUTER_API_KEY, C, ATS_THRESHOLD
from pipeline.resume import detect_role_from_resume

## Initialize the Production-Grade Engine Singleton
ENGINE = ResumeTailor(
    minimax_api_key=OPENROUTER_API_KEY, 
    gemini_api_key=GOOGLE_API_KEY,
    ats_threshold=ATS_THRESHOLD
)

# High-impact verbs requested by the user (Full 400+ Optimized Set)
ACTION_VERBS = [
    "accelerated", "achieved", "acquired", "adapted", "addressed", "administered", "advanced", "advised", "advocated",
    "aligned", "allocated", "analyzed", "answered", "anticipated", "applied", "appointed", "appraised", "approached",
    "appropriated", "approved", "arbitrated", "architected", "arranged", "ascertained", "assembled", "assessed", "assigned",
    "assisted", "attained", "audited", "authored", "authorized", "automated", "awarded", "balanced", "bargained",
    "benchmarked", "benefited", "budgeted", "built", "calculated", "captured", "cataloged", "categorized", "centralized",
    "certified", "chaired", "charted", "checked", "classified", "cleared", "closed", "coached", "collaborated",
    "collected", "combined", "commanded", "commended", "communicated", "compared", "compiled", "completed", "composed",
    "computed", "conceptualized", "concluded", "conducted", "conferred", "conserved", "consolidated", "constructed",
    "consulted", "contacted", "continued", "contracted", "contributed", "controlled", "converted", "conveyed", "convinced",
    "coordinated", "corresponded", "counseled", "created", "critiqued", "cultivated", "customized", "debugged", "deciphered",
    "dedicated", "defined", "delegated", "delivered", "demonstrated", "deployed", "designed", "detailed", "detected",
    "determined", "developed", "devised", "diagnosed", "directed", "discovered", "dispatched", "displayed", "dissected",
    "distinguished", "distributed", "diversified", "documented", "drafted", "drove", "earned", "edited", "educated",
    "effected", "elaborated", "elicited", "eliminated", "emphasized", "enabled", "enacted", "encouraged", "endured",
    "enforced", "engineered", "enhanced", "enlarged", "enlisted", "ensured", "entered", "established", "estimated",
    "evaluated", "examined", "exceeded", "executed", "exercised", "expanded", "expedited", "experimented", "explained",
    "explored", "expressed", "extended", "extracted", "fabricated", "facilitated", "familiarized", "fashioned", "fielded",
    "finalized", "financed", "fitted", "focused", "forecasted", "formalized", "formed", "formulated", "fortified",
    "forwarded", "fostered", "found", "founded", "framed", "fulfilled", "functioned", "furnished", "gained", "gathered",
    "generated", "governed", "graded", "granted", "grew", "guaranteed", "guided", "handled", "headed", "helped",
    "identified", "illustrated", "implemented", "imported", "improved", "improvised", "inaugurated", "incorporated",
    "increased", "indexed", "indicated", "indoctrinated", "induced", "influenced", "informed", "initiated", "injected",
    "innovated", "inspected", "inspired", "installed", "instigated", "instilled", "instituted", "instructed", "insured",
    "integrated", "intensified", "interpreted", "interrogated", "interviewed", "introduced", "invented", "inventoried",
    "investigated", "invested", "involved", "isolated", "issued", "itemized", "joined", "judged", "justified", "kept",
    "kindled", "launched", "learned", "lectured", "led", "licensed", "lightened", "linked", "liquidated", "listed",
    "listened", "litigated", "located", "logged", "maintained", "managed", "manipulated", "mapped", "marketed",
    "mastered", "maximized", "measured", "mediated", "mentored", "merged", "met", "minimized", "modeled", "moderated",
    "modernized", "modified", "monitored", "motivated", "moved", "multiplied", "named", "narrated", "navigated",
    "negotiated", "noted", "notified", "nurtured", "observed", "obtained", "offered", "offset", "opened", "operated",
    "orchestrated", "ordered", "organized", "oriented", "originated", "outlined", "overcame", "overhauled", "oversaw",
    "paced", "packaged", "participated", "passed", "penned", "perceived", "performed", "persuaded", "photographed",
    "piloted", "pioneered", "placed", "planned", "played", "policed", "polished", "prepared", "prescribed", "presented",
    "preserved", "presided", "prevented", "priced", "primed", "printed", "prioritized", "processed", "procured",
    "produced", "profiled", "programmed", "projected", "promoted", "prompted", "proofread", "proposed", "proved",
    "provided", "publicized", "published", "purchased", "pursued", "qualified", "quantified", "queried", "questioned",
    "raised", "ran", "reached", "realized", "reasoned", "received", "recognized", "recommended", "reconciled", "recorded",
    "recruited", "rectified", "redesigned", "reduced", "referred", "refined", "refocused", "reformed", "registered",
    "regulated", "rehabilitated", "reinforced", "reinstated", "rejected", "related", "remanufactured", "remedied",
    "remodeled", "renegotiated", "renovated", "reorganized", "repaired", "replaced", "replied", "reported", "represented",
    "requested", "rescued", "researched", "resolved", "responded", "restored", "restructured", "retrieved", "revamp",
    "revealed", "reviewed", "revised", "revitalized", "rewarded", "routed", "safeguarded", "salvaged", "satisfied",
    "saved", "scheduled", "schooled", "screened", "scripted", "scanned", "searched", "secured", "segmented", "selected",
    "served", "serviced", "settled", "shaped", "shared", "showed", "simplified", "simulated", "sketched", "slashed",
    "smoothed", "solicited", "solved", "sorted", "spearheaded", "specialized", "specified", "spoke", "sponsored",
    "staffed", "standardized", "started", "stated", "steered", "stimulated", "strategized", "streamlined", "strengthened",
    "stressed", "stretched", "structured", "studied", "submitted", "substituted", "succeeded", "suggested", "summarized",
    "superseded", "supervised", "supplied", "supported", "surpassed", "surveyed", "synthesized", "systematized",
    "tabulated", "tailored", "targeted", "taught", "teamed", "tested", "testified", "thwarted", "tightened", "tolerated",
    "totaled", "tracked", "traded", "trained", "transcribed", "transferred", "transformed", "translated", "transmitted",
    "transported", "traveled", "treated", "triggered", "trimmed", "troubleshot", "tutored", "uncovered", "undertook",
    "unified", "united", "updated", "upgraded", "used", "utilized", "validated", "valued", "verified", "viewed",
    "visited", "visualized", "voiced", "volunteered", "witnessed", "worked", "wrote", "yielded"
]

def _openrouter_json(prompt: str, system: str, retries: int = 2, max_tokens: int = 2400) -> dict:
    for _ in range(max(1, retries)):
        raw = openrouter_call(prompt, system=system, max_retries=2, max_tokens=max_tokens)
        parsed = parse_json_from_llm(raw)
        if isinstance(parsed, dict) and parsed:
            return parsed
    return {}

async def audit_resume(job_description, original_resume_text, tailored_json):
    """
    Audits the tailored resume JSON against the JD and original resume text.
    Uses OpenRouter (MiniMax M2.5 configured in pipeline.config).
    """
    audit_prompt = f"""
You are an ATS Quality Auditor. Compare the following:

JOB DESCRIPTION: {job_description[:9000]}
ORIGINAL RESUME DATA (Source of Truth): {original_resume_text[:9000]}
TAILORED RESUME DRAFT (To be audited): {json.dumps(tailored_json)[:9000]}

TASK:
1. Score the draft (0-100) based on:
   - KEYWORDS (40%)
   - VERBS (30%)
   - IMPACT (30%)
2. Identify critical keywords from JD that are in source data but missing in draft.
3. Identify weak bullets that lack impact.
RULE: NO FAKE SKILLS.

OUTPUT JSON ONLY:
{{
  "score": 0,
  "missing_verified_keywords": [],
  "weak_bullet_feedback": [],
  "improvement_plan": ""
}}
"""
    parsed = _openrouter_json(
        prompt=audit_prompt,
        system="You are a strict ATS Quality Auditor and return valid JSON only.",
        retries=2,
        max_tokens=1800,
    )
    if not parsed:
        return {
            "score": 80,
            "missing_verified_keywords": [],
            "weak_bullet_feedback": [],
            "improvement_plan": "No audit feedback returned.",
        }
    return parsed

def _get_static_template(data: dict) -> str:
    """
    Returns a professional, single-column ATS-friendly HTML template
    as a high-fidelity fallback when the LLM fails to generate HTML.
    """
    skills_html = ""
    skills_data = data.get("skills", {})
    if isinstance(skills_data, dict):
        for category, skill_list in skills_data.items():
            if not skill_list: continue
            skills_html += f"""
            <div class="skill-row">
                <strong style="min-width: 100px; display: inline-block;">{category}:</strong>
                {", ".join(skill_list)}
            </div>"""
    elif isinstance(skills_data, list):
        # Fallback for simple list
        skills_html = f"<div>{', '.join(skills_data)}</div>"

    exp_html = ""
    for item in data.get("experience", []):
        if isinstance(item, str):
            exp_html += f'<div class="entry"><p>{item}</p></div>'
            continue
        bullets = "".join([f"<li>{b}</li>" for b in item.get("bullets", [])])
        exp_html += f"""
        <div class="entry">
            <div class="entry-header">
                <strong>{item.get('role')}</strong> | {item.get('company', '')}
                <span class="date">{item.get('duration', '')}</span>
            </div>
            <ul>{bullets}</ul>
        </div>
        """

    proj_html = ""
    for item in data.get("projects", []):
        if isinstance(item, str):
            proj_html += f'<div class="entry"><p>{item}</p></div>'
            continue
        bullets = "".join([f"<li>{b}</li>" for b in item.get("bullets", [])])
        proj_html += f"""
        <div class="entry">
            <div class="entry-header">
                <span class="project-title">{item.get('name')}</span>
            </div>
            <ul>{bullets}</ul>
        </div>
        """

    # Generate dynamic contact line without empty fields and dangling pipes
    contact_dict = data.get('contact_info', {})
    contact_parts = [
        contact_dict.get('email'),
        contact_dict.get('phone'),
        contact_dict.get('location'),
        contact_dict.get('linkedin'),
        contact_dict.get('github')
    ]
    contact_line = " | ".join([str(p).strip() for p in contact_parts if p and str(p).strip()])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Times New Roman', Times, serif; line-height: 1.4; color: #333; margin: 40px; font-size: 11.5px; }}
            h1 {{ text-align: center; margin-bottom: 2px; font-size: 22px; text-transform: uppercase; color: #1a365d; }}
            .contact {{ text-align: center; margin-bottom: 10px; font-size: 10px; color: #4a5568; }}
            .ats-badge {{ text-align: center; margin-bottom: 20px; font-size: 9px; color: #718096; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }}
            h2 {{ border-bottom: 2px solid #e2e8f0; margin-top: 18px; margin-bottom: 8px; font-size: 14px; text-transform: uppercase; color: #000; }}
            .entry {{ margin-bottom: 12px; }}
            .entry-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; color: #000; }}
            .project-title {{ font-size: 13px; font-weight: bold; color: #000; }}
            .date {{ font-style: italic; color: #4a5568; }}
            ul {{ margin-top: 4px; padding-left: 18px; list-style-type: disc; color: #000; }}
            li {{ margin-bottom: 4px; text-align: justify; line-height: 1.5; color: #000; }}
            .skills-section {{ margin-top: 8px; }}
            .skill-row {{ margin-bottom: 4px; font-size: 11px; }}
            .skill-row strong {{ color: #000; }}
        </style>
    </head>
    <body>
        <h1>{data.get('full_name', 'Candidate')}</h1>
        <div class="contact">
            {contact_line}
        </div>
        <div class="ats-badge">ATS MATCH SCORE: {data.get('rag_metadata', {}).get('match_score', 85)}% | AI TAILORED FOR {data.get('target_role', 'Software Role')}</div>
        
        <h2>Professional Summary</h2>
        <p style="text-align: justify;">{data.get('summary')}</p>
        
        <h2>Education</h2>
        <p>{data.get('education')}</p>
        
        <h2>Technical Skills</h2>
        <div class="skills-section">{skills_html}</div>
        
        <h2>Key Projects</h2>
        {proj_html}
        
        <h2>Professional Experience</h2>
        {exp_html}
    </body>
    </html>
    """

async def tailor_resume(job_description, resume_text, output_path: Path):
    """
    Tailors resume using the PRODUCTION RAG-Core engine.
    Unified flow: run_pipeline_v2.py and venkat_live_pipeline.py.
    """
    # 1. Prepare Inputs
    profile_data = detect_role_from_resume(resume_text)
    
    job = JobInput(
        title="Target Role", 
        description=job_description
    )
    user = UserProfile.from_dict(profile_data)
    
    # 2. Execute RAG-Core Tailoring
    tailored_core = await ENGINE.tailor(job, user)
    
    if not tailored_core.get("success", True):
        return None, tailored_core
    
    # 3. Merge Core Content with Personal Identity
    resume_content = tailored_core.get("resume", {})
    final_json = {
        "full_name": profile_data.get("full_name", "Candidate"),
        "contact_info": {
            "email": profile_data.get("email", ""),
            "phone": profile_data.get("phone", ""),
            "location": profile_data.get("location", ""),
            "linkedin": profile_data.get("linkedin", ""),
            "github": profile_data.get("github", "")
        },
        "summary": resume_content.get("summary", ""),
        "skills": resume_content.get("skills", []),
        "experience": resume_content.get("experience", []),
        "projects": resume_content.get("projects", []),
        "education": resume_content.get("education", profile_data.get("education", "")),
        "rag_metadata": resume_content.get("rag_metadata", {})
    }

    # 4. Generate Professional HTML via Groq LLM (Attempt 1)
    html_prompt = f"""
    Convert this JSON resume into a professional, single-column ATS HTML document.
    JSON: {json.dumps(final_json)}
    
    STRICT DESIGN:
    - Single column, Times New Roman, 11.5px.
    - Centered header with name, contact, and DYNAMIC ATS MATCH SCORE.
    - Section Headers (h2): Use a light-grey horizontal line (border-bottom: 2px solid #e2e8f0).
    - Professional Summary: Craft a unique 3-4 sentence objective for THIS JD.
    - Education: Include education details IMMEDIATELY AFTER the Professional Summary.
    - Key Projects (PRIORITY): Bold black titles (font-size: 13px). Section comes before Experience.
    - Professional Experience: Use elite polishing. 
    - Bullet points (li): Use line-height: 1.5 for readability. Use standard BLACK bullet marks (•), NEVER use dashes (-).
    - Use <h2> for section headers.
    - Dates right-aligned.
    - Valid, clean HTML only. No Intro/Outro text.
    """
    
    ai_response = await ENGINE.core_generator.llm.async_generate(
        html_prompt,
        system="You are a strict HTML generator. Output only the <html>...</html> code.",
        max_tokens=2500,
    )

    # 5. Robust Extraction & Fallback
    html_content = ""
    if ai_response:
        # Try to find content between <html> tags
        match = re.search(r"<html[\s\S]*?</html>", ai_response, re.IGNORECASE)
        if match:
            html_content = match.group(0)
        else:
            # Fallback to cleaning backticks
            html_content = re.sub(r"```html\n?|```", "", str(ai_response)).strip()

    # Final Safety Check: If AI failed or returned garbage, use Static Template
    if not html_content or "<html" not in html_content.lower() or len(html_content) < 500:
        print(f"{C.YELLOW}[WARN] AI HTML generation failed or too short. Using Professional Static Template Fallback.{C.RESET}")
        html_content = _get_static_template(final_json)

    # 6. Generate PDF
    output_path = Path(output_path).absolute()
    output_path.parent.mkdir(exist_ok=True, parents=True)
    await pdf_service.generate_pdf(html_content, output_path)
    
    return str(output_path), final_json
