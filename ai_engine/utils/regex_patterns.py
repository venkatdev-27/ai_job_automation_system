import re

# EMAIL & PHONE
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[\s\-()]*)?(?:\d[\s\-()]*){9,14}\d")

# PROFILE URLS
PROFILE_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s|,]+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?github\.com/[^\s|,]+", re.IGNORECASE),
    re.compile(r"https?://[^\s|,]+", re.IGNORECASE),
]

# SECTION IDENTIFICATION
SECTION_LABEL_HINTS = {
    "summary", "objective", "education", "skills", "technical skills", "experience",
    "projects", "project", "certifications", "internships", "contact", "profile"
}

# ATS KEYWORD PATTERNS (Precompiled for performance)
_ATS_RAW_PATTERNS = [
    (".NET", r"\b(?:dotnet|\.net)\b"),
    ("ASP.NET Core", r"\basp\.net\s+core\b"),
    ("ASP.NET", r"\basp\.net\b"),
    ("C#", r"\bc#\b|\bc\s+sharp\b"),
    ("Web APIs", r"\bweb\s+apis?\b"),
    ("REST APIs", r"\brest(?:ful)?\s+apis?\b"),
    ("Entity Framework", r"\bentity\s+framework\b"),
    ("SQL Server", r"\bsql\s+server\b"),
    ("React", r"\breact(?:\.js|js)?\b"),
    ("Angular", r"\bangular\b"),
    ("Vue", r"\bvue(?:\.js|js)?\b"),
    ("Next.js", r"\bnext(?:\.js|js)?\b"),
    ("Node.js", r"\bnode(?:\.js|js)?\b"),
    ("Express.js", r"\bexpress(?:\.js|js)?\b"),
    ("JavaScript", r"\bjavascript\b"),
    ("TypeScript", r"\btypescript\b"),
    ("Python", r"\bpython\b"),
    ("Django", r"\bdjango\b"),
    ("Flask", r"\bflask\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Java", r"\bjava\b"),
    ("Spring Boot", r"\bspring\s+boot\b"),
    ("PHP", r"\bphp\b"),
    ("Laravel", r"\blaravel\b"),
    ("Ruby on Rails", r"\bruby\s+on\s+rails\b"),
    ("Golang", r"\bgolang\b"),
    ("Microservices", r"\bmicroservices?\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
    ("AWS", r"\baws\b|\bamazon web services\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\bgcp\b|\bgoogle cloud\b"),
    ("CI/CD", r"\bci\s*/\s*cd\b"),
    ("Jenkins", r"\bjenkins\b"),
    ("Terraform", r"\bterraform\b"),
    ("Ansible", r"\bansible\b"),
    ("Git", r"\bgit\b"),
    ("GitHub", r"\bgithub\b"),
    ("Jira", r"\bjira\b"),
    ("MongoDB", r"\bmongodb\b"),
    ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
    ("MySQL", r"\bmysql\b"),
    ("SQL", r"\bsql\b"),
    ("Redis", r"\bredis\b"),
    ("HTML", r"\bhtml5?\b"),
    ("CSS", r"\bcss3?\b"),
    ("Redux", r"\bredux\b"),
    ("WebSocket", r"\bwebsockets?\b"),
    ("Full Stack", r"\bfull\s*stack\b"),
]

ATS_KEYWORD_REGEXES = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in _ATS_RAW_PATTERNS]

# SKILL BUCKETS
SKILL_BUCKET_PATTERNS = {
    "dotnet": [re.compile(r"\b(?:dotnet|\.net|aspnet|asp\.net|entity framework|blazor|wpf|wcf)\b", re.IGNORECASE)],
    "frontend": [re.compile(r"\b(?:react|angular|vue|nextjs|redux|html|css|bootstrap|tailwind|jquery|frontend|ui|ux)\b", re.IGNORECASE)],
    "backend": [re.compile(r"\b(?:nodejs|express|django|flask|fastapi|spring boot|laravel|rails|rest apis|web apis|graphql|microservices|backend)\b", re.IGNORECASE)],
    "databases": [re.compile(r"\b(?:sqlserver|sql|mysql|postgres|mongodb|mongo|sqlite|redis|oracle|cassandra)\b", re.IGNORECASE)],
    "cloud": [re.compile(r"\b(?:aws|azure|gcp|cloud|serverless|lambda|ec2|s3)\b", re.IGNORECASE)],
    "devops": [re.compile(r"\b(?:docker|kubernetes|jenkins|terraform|ansible|ci/cd|prometheus|grafana)\b", re.IGNORECASE)],
    "tools": [re.compile(r"\b(?:git|github|jira|linux|visual studio|vscode|postman|figma)\b", re.IGNORECASE)],
    "languages": [re.compile(r"\b(?:c#|c\+\+|java|python|javascript|typescript|php|ruby|go|golang|kotlin|swift|sql|html|css|dart)\b", re.IGNORECASE)],
}

# HTML PARSING
EMPTY_HTML_P = re.compile(r"<(div|p|li|span)[^>]*>\s*</\1>", re.IGNORECASE)
EXTRACT_HTML_TAG = re.compile(r"(<html.*?>.*?</html>)", re.IGNORECASE | re.DOTALL)
EXTRACT_BODY_FALLBACK = re.compile(r"(<!DOCTYPE html>.*|<!doctype html>.*|<body.*?>.*?</body>|<div.*?>.*?</div>)", re.IGNORECASE | re.DOTALL)

def get_section_pattern(heading):
    return re.compile(
        rf"<h2[^>]*>\s*{re.escape(heading)}\s*</h2>\s*(?:<hr[^>]*>)?\s*(.*?)(?=<h2[^>]*>|</body>|</html>)",
        re.IGNORECASE | re.DOTALL,
    )
