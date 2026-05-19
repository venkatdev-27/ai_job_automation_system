import os
import re
from pathlib import Path

ENGINE_ROOT = Path(__file__).parent.resolve()
RESUME_OUTPUT_DIR = ENGINE_ROOT / "resumes"

# Ensure directories exist
RESUME_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(ENGINE_ROOT / "cache").mkdir(parents=True, exist_ok=True)


def get_student_resume_path(student_id: str, filename: str) -> Path:
    """Get output path for a student's resume file."""
    student_folder = RESUME_OUTPUT_DIR / student_id
    student_folder.mkdir(parents=True, exist_ok=True)
    return student_folder / filename

# Load environment from root
from dotenv import load_dotenv
root_env = ENGINE_ROOT.parent / ".env"
if root_env.exists():
    load_dotenv(root_env)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "if",
    "in", "into", "is", "it", "of", "on", "or", "role", "the", "to", "with",
    "required", "preferred", "must", "should", "experience", "responsibilities",
    "knowledge", "skills", "skill", "using", "work", "working", "strong"
}

# LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
DEFAULT_PRIMARY_MODEL = "llama-3.1-8b-instant"
DEFAULT_FALLBACK_MODELS = ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"]

ACTION_VERBS = {
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
}

# Word counts for precision polishing
SUMMARY_WORD_MIN = 48
SUMMARY_WORD_MAX = 65
BULLET_WORD_MIN = 12
BULLET_WORD_MAX = 22

# Common skill equivalents for harmonization
COMMON_EQUIVALENTS = {
    ".net": "dotnet",
    "asp.net": "aspnet",
    "asp.net core": "aspnet core",
    "node.js": "nodejs",
    "reactjs": "react",
    "react.js": "react",
    "nodejs": "node",
    "next.js": "nextjs",
    "express.js": "expressjs",
    "expressjs": "express",
    "vue.js": "vue",
    "postgresql": "postgres",
    "mongodb": "mongo",
    "javascript": "js",
    "typescript": "ts",
    "c sharp": "c#",
    "web api": "web apis",
    "rest api": "rest apis",
    "sql server": "sqlserver",
    "power bi": "powerbi",
    "scikit-learn": "sklearn",
    "tensorflow": "tf"
}

# Role Branding Overrides
ROLE_BRAND_OVERRIDES = {
    "general": "Software Developer",
    "dotnet": ".NET Developer",
    "qa": "QA Engineer",
    "frontend": "Frontend Developer",
    "backend": "Backend Developer",
    "fullstack": "Full Stack Developer",
    "data_science": "Data Scientist",
    "ai_ml": "AI/ML Engineer",
    "mobile": "Mobile Developer",
    "devops": "DevOps Engineer",
    "cloud": "Cloud Engineer",
    "security": "Security Engineer",
}

# Skill Label Overrides for standardizing output
SKILL_LABEL_OVERRIDES = {
    "dotnet": ".NET",
    "aspnet": "ASP.NET",
    "aspnet core": "ASP.NET Core",
    "nodejs": "Node.js",
    "expressjs": "Express.js",
    "reactjs": "React",
    "react": "React",
    "vuejs": "Vue",
    "vue": "Vue",
    "nextjs": "Next.js",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "js": "JavaScript",
    "ts": "TypeScript",
}

# Company names/terms to ignore during extraction
COMPANY_IGNORE_TERMS = {
    "company", "organization", "employer", "client", "our company", "the company",
    "job description", "requirements", "responsibilities", "candidate", "role"
}

# V2 Original Styling Constants (Legacy Template)
LEGACY_FONT_FAMILY = "Calibri, 'Segoe UI', Arial, sans-serif"
LEGACY_BODY_FONT_SIZE_PT = 11
LEGACY_NAME_FONT_SIZE_PT = 24
LEGACY_SECTION_FONT_SIZE_PT = 14
LEGACY_MARGIN_IN = "0.55in"
LEGACY_LINE_HEIGHT = "1.45"

# Role Profiles for matching JD to ATS categories
ROLE_PROFILES = {
    "fullstack": {
        "family": "fullstack",
        "priority": "frontend, backend, apis, databases, end-to-end delivery",
        "categories": ["Languages", "Frontend", "Backend", "Databases", "Tools"],
        "regex": r"\b(full stack|fullstack|software engineer|software developer|mern|mean|lamp)\b"
    },
    "frontend": {
        "family": "frontend",
        "priority": "ui development, react, responsiveness, user interaction",
        "categories": ["Languages", "Frontend", "UI/UX", "Frameworks", "Tools"],
        "regex": r"\b(frontend|front end|react|ui|ux|css|html|javascript developer|web developer|angular|vue|svelte|nextjs)\b"
    },
    "backend": {
        "family": "backend",
        "priority": "apis, backend logic, databases, server-side workflows",
        "categories": ["Languages", "Backend", "APIs", "Databases", "Tools"],
        "regex": r"\b(backend|back end|api|server|database|node|python|django|flask|spring boot|golang|ruby on rails|microservices)\b"
    },
    "qa": {
        "family": "qa",
        "priority": "testing, debugging, automation, validation",
        "categories": ["Languages", "Testing Tools", "Automation", "Frameworks", "Tools"],
        "regex": r"\b(sdet|qa|quality assurance|testing|tester|automation engineer|test engineer)\b"
    },
    "dotnet": {
        "family": "backend",
        "priority": "asp.net core, c#, web apis, database design, enterprise software",
        "categories": ["Languages", ".NET Framework", "Backend", "Databases", "Tools"],
        "regex": r"\b(dotnet|\.net|c#|asp\.net|entity framework|wcf|wpf)\b"
    }
}
