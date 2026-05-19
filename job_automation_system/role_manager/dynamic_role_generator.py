"""
Expanded Role Generator - 200+ Roles
==========================
Comprehensive rule-based role generation with 100+ skills and 200+ roles.
Now with LLM-powered intelligent role suggestions using Groq.
"""

from typing import Any, Optional
import re
import os

from dotenv import load_dotenv
from config.settings import settings

# Use Groq API key from settings
GROQ_API_KEY = settings.groq_api_key


# ==================== COMPREHENSIVE SKILL LIST ====================

COMPREHENSIVE_SKILLS = {
    # Programming Languages
    "programming": [
        "javascript", "typescript", "python", "java", "c", "c++", "c#", "csharp",
        "go", "golang", "ruby", "rust", "swift", "kotlin", "scala", "php", "perl",
        "r", "matlab", "julia", "dart", "elixir", "haskell", "lua", "powershell"
    ],
    
    # Frontend/Web
    "frontend": [
        "html", "html5", "css", "css3", "sass", "less", "bootstrap", "tailwind",
        "javascript", "typescript", "react", "reactjs", "angular", "angularjs", "vue",
        "vuejs", "vue.js", "jquery", "redux", "reduxjs", "nextjs", "nuxtjs",
        "gatsby", "webpack", "vite", "babel", "sass", "less", "materialui",
        "antd", "chakraui", "framer motion", "web components", "pwa", "spa"
    ],
    
    # Backend/Server
    "backend": [
        "nodejs", "node.js", "express", "expressjs", "django", "flask", "fastapi",
        "spring", "spring boot", "springboot", "ruby on rails", "ror", "laravel", "codeigniter",
        "asp.net", ".net", "dotnet", "php", "python", "java", "go", "gin",
        "nestjs", "nest.js", "koa", "hapi", "fastify", "falcon", "bottle"
    ],
    
    # Databases
    "database": [
        "sql", "mysql", "postgresql", "mongodb", "mongo", "redis", "oracle",
        "sqlite", "cassandra", "dynamodb", "firebase", "firestore", "mariadb",
        "plsql", "tsql", "neo4j", "couchdb", "elasticsearch", "memcached",
        "amazon rds", "azure sql", "google cloud sql", "realm", "cockroachdb"
    ],
    
    # Cloud/DevOps
    "cloud": [
        "aws", "amazon web services", "azure", "google cloud", "gcp", "heroku", "digitalocean",
        "docker", "kubernetes", "k8s", "jenkins", "ci/cd", "terraform", "ansible",
        "puppet", "chef", "circleci", "travis ci", "gitlab ci", "github actions",
        "cloudformation", "helm", "prometheus", "grafana", "Nagios", "vagrant",
        "vault", "consul", "nomad", "openshift", "elastic beanstalk"
    ],
    
    # Mobile
    "mobile": [
        "react native", "flutter", "android", "android development", "ios",
        "swift", "kotlin", "xamarin", "ionic", "cordova", "phonegap",
        "native script", "mobile eng", "ipad", "iphone"
    ],
    
    # Data/Analytics
    "data": [
        "pandas", "numpy", "pyspark", "spark", "hadoop", "hive", "pig",
        "airflow", "etl", "kafka", "streams", "flink", "storm", "tableau",
        "power bi", "looker", "dbt", "glue", "databricks", "snowflake"
    ],
    
    # ML/AI
    "ml": [
        "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
        "scikit-learn", "sklearn", "opencv", "computer vision", "nlp", "natural language processing",
        "neural networks", "ai", "artificial intelligence", "llm", "gpt",
        "bert", "transformers", "huggingface", "mlflow", "weights & biases",
        "langchain", "llama-index", "vector database", "chromadb", "pinecone",
        "reinforcement learning", "generative ai", "genai", "prompt engineering"
    ],
    
    # API/Integration
    "api": [
        "rest", "restful", "graphql", "grpc", "json", "xml", "oauth",
        "jwt", "saml", "openid", "webhook", "api gateway", "kong", "apigee",
        "aws api gateway", "azure api management", "mulesoft", "postman"
    ],
    
    # Testing
    "testing": [
        "selenium", "pytest", "unittest", "jest", "mocha", "jasmine",
        "cypress", "playwright", "testng", "junit", "mockito", "robot framework",
        "postman", "soapui", "loadrunner", "jmeter", "katalon", "appium"
    ],
    
    # Security
    "security": [
        "owasp", "penetration testing", "security audit", "vulnerability assessment",
        "encryption", "ssl", "tls", "https", "firewall", "waf", "soc",
        "cybersecurity", "ethical hacking", "kali linux", "burp suite",
        "siem", "splunk", "crowdstrike", "incident response", "iam"
    ],
    
    # Tools/Other
    "tools": [
        "git", "github", "gitlab", "bitbucket", "svn", "jira", "confluence",
        "agile", "scrum", "kanban", "docker compose", "kubectl", "linux",
        "unix", "bash", "zsh", "vim", "vscode", "intellij", "eclipse"
    ],
    
    # Blockchain (new)
    "blockchain": [
        "solidity", "web3", "ethereum", "blockchain", "smart contracts",
        "nft", "defi", "crypto", "bitcoin", "polygon", "solana"
    ],
    
    # ERP/Enterprise
    "erp": [
        "sap", "salesforce", "salesforce crm", "dynamics crm", "oracle crm",
        "workday", "peoplesoft", "netsuite", "sage"
    ],
    
    # QA
    "qa": [
        "quality assurance", "qa engineering", "manual testing", "automation testing",
        "regression testing", "smoke testing", "integration testing", "unit testing"
    ],
    
    # Data Science
    "datascience": [
        "data science", "data analysis", "data engineering", "statistics",
        "a/b testing", "hypothesis testing", "experimentation"
    ],
    
    # IoT
    "iot": [
        "internet of things", "embedded systems", "arduino", "raspberry pi",
        "mqtt", "sensor networks", "edge computing"
    ],
}


# ==================== COMPREHENSIVE ROLE MAPPINGS (200+) ==================== 

SKILL_TO_ROLE = {
    # JavaScript/Frontend Roles (40+)
    "javascript": "JavaScript Developer",
    "typescript": "TypeScript Developer",
    "react": "React Developer",
    "reactjs": "React.js Developer",
    "angular": "Angular Developer",
    "angularjs": "AngularJS Developer",
    "vue": "Vue.js Developer",
    "vuejs": "Vue.js Developer",
    "jquery": "jQuery Developer",
    "redux": "Redux Developer",
    "nextjs": "Next.js Developer",
    "gatsby": "Gatsby Developer",
    "svelte": "Svelte Developer",
    "tailwind": "Tailwind CSS Developer",
    "bootstrap": "Bootstrap Developer",
    "sass": "Sass Developer",
    "less": "Less Developer",
    "webpack": "Webpack Engineer",
    "vite": "Vite Developer",
    "babel": "Babel Specialist",
    "materialui": "Material UI Developer",
    "chakraui": "Chakra UI Developer",
    "frontend": "Frontend Engineer",
    "ui": "UI Developer",
    "ux": "UX Engineer",
    "web": "Web Developer",
    "pwa": "PWA Developer",
    "spa": "SPA Developer",
    "d3js": "Data Visualization Developer",
    "threejs": "WebGL Developer",
    "canvas": "Canvas API Developer",
    "animation": "Frontend Animation Developer",
    "accessibility": "Accessibility Specialist",
    "performance": "Frontend Performance Engineer",
    "security": "Frontend Security Engineer",
    "testing": "Frontend QA Engineer",
    "devops": "Frontend DevOps Engineer",
    "architecture": "Frontend Architect",
    "microfrontends": "Micro-frontend Architect",
    
    # Full Stack Roles (12+)
    "mern": "MERN Stack Developer",
    "mean": "MEAN Stack Developer",
    "mevn": "MEVN Stack Developer",
    "lamp": "LAMP Stack Developer",
    "jamstack": "JAMstack Developer",
    "serverless": "Serverless Full Stack Developer",
    "django": "Python Full Stack Developer",
    "flask": "Python Full Stack Developer",
    "spring": "Java Full Stack Developer",
    "laravel": "PHP Full Stack Developer",
    "dotnet": ".NET Full Stack Developer",
    "flutter": "Full Stack Mobile Developer",
    "golang": "Go Full Stack Developer",
    
    # Backend Roles (45+)
    "java": "Java Backend Developer",
    "springboot": "Spring Boot Developer",
    "spring": "Spring Developer",
    "microservices": "Microservices Developer",
    "nodejs": "Node.js Backend Developer",
    "node": "Node.js Developer",
    "express": "Express.js Developer",
    "python": "Python Backend Developer",
    "django": "Django Developer",
    "flask": "Flask Developer",
    "fastapi": "FastAPI Developer",
    "go": "Go Backend Developer",
    "golang": "Golang Developer",
    "ruby": "Ruby on Rails Developer",
    "php": "PHP Backend Developer",
    "laravel": "Laravel Developer",
    "csharp": "C# Developer",
    "dotnet": ".NET Core Developer",
    "nestjs": "NestJS Developer",
    "graphql": "GraphQL Backend Developer",
    "grpc": "gRPC Specialist",
    "rest": "REST API Developer",
    "sql": "Database Developer",
    "nosql": "NoSQL Developer",
    "postgresql": "PostgreSQL Expert",
    "mysql": "MySQL Specialist",
    "mongodb": "MongoDB Specialist",
    "redis": "Redis Specialist",
    "elasticsearch": "Search Engineer",
    "kafka": "Event Streaming Engineer",
    "rabbitmq": "Message Queue Specialist",
    "docker": "Backend Infrastructure Engineer",
    "kubernetes": "Cloud Native Developer",
    "serverless": "Serverless Specialist",
    "aws": "AWS Backend Developer",
    "gcp": "GCP Backend Developer",
    "azure": "Azure Backend Developer",
    "security": "Backend Security Engineer",
    "testing": "Backend QA Engineer",
    "architecture": "Backend Architect",
    "optimization": "Performance Engineer",
    "legacy": "Legacy System Specialist",
    "refactoring": "Code Quality Specialist",
    "documentation": "Technical Documentation Specialist",
    "api": "API Architect",
    
    # Database Roles (20+)
    "mysql": "MySQL Developer",
    "postgresql": "PostgreSQL Developer",
    "mongodb": "MongoDB Developer",
    "mongo": "MongoDB Developer",
    "redis": "Redis Developer",
    "oracle": "Oracle Developer",
    "sql": "SQL Developer",
    "sqlite": "SQLite Developer",
    "cassandra": "Cassandra Developer",
    "dynamodb": "DynamoDB Developer",
    
    # Cloud/DevOps Roles (50+)
    "aws": "AWS Solutions Architect",
    "azure": "Azure Cloud Engineer",
    "gcp": "Google Cloud Architect",
    "docker": "Containerization Specialist",
    "kubernetes": "Kubernetes Administrator",
    "k8s": "K8s Engineer",
    "jenkins": "Jenkins CI/CD Expert",
    "terraform": "IaC Engineer",
    "ansible": "Automation Engineer",
    "puppet": "Configuration Manager",
    "chef": "DevOps Specialist",
    "linux": "Linux Systems Administrator",
    "unix": "Unix Administrator",
    "bash": "Shell Scripting Specialist",
    "powershell": "Automation Specialist",
    "monitoring": "Observability Engineer",
    "prometheus": "Monitoring Specialist",
    "grafana": "Visualization Engineer",
    "logging": "ELK Stack Specialist",
    "splunk": "SIEM Engineer",
    "security": "DevSecOps Engineer",
    "networking": "Cloud Networking Engineer",
    "vpc": "Network Architect",
    "loadbalancer": "Traffic Management Specialist",
    "cdn": "Content Delivery Specialist",
    "storage": "Cloud Storage Specialist",
    "database": "Cloud Database Administrator",
    "serverless": "Lambda Specialist",
    "git": "Version Control Specialist",
    "github": "GitHub Actions Specialist",
    "gitlab": "GitLab CI Expert",
    "bitbucket": "Bitbucket Specialist",
    "jira": "Agile Tools Specialist",
    "confluence": "Documentation Lead",
    "slack": "Collaboration Tools Specialist",
    "deployment": "Release Manager",
    "migration": "Cloud Migration Specialist",
    "cost": "Cloud Cost Optimizer",
    "finops": "FinOps Analyst",
    "sre": "Site Reliability Engineer",
    "reliability": "Availability Engineer",
    "scaling": "Scalability Specialist",
    "disaster": "DR Specialist",
    "backup": "Backup Administrator",
    "compliance": "Cloud Compliance Officer",
    "governance": "Cloud Governance Lead",
    "hybrid": "Hybrid Cloud Architect",
    "multi": "Multi-Cloud Strategist",
    "edge": "Edge Computing Specialist",
    "iot": "Cloud IoT Engineer",
    "pyspark": "PySpark Developer",
    "spark": "Spark Developer",
    "hadoop": "Hadoop Developer",
    "hive": "Hive Developer",
    "airflow": "Airflow Developer",
    "etl": "ETL Developer",
    "kafka": "Kafka Developer",
    "pandas": "Pandas Developer",
    "tableau": "Tableau Developer",
    "power bi": "Power BI Developer",
    "snowflake": "Snowflake Developer",
    
    # ML/AI Roles (50+)
    "machine learning": "Machine Learning Engineer",
    "tensorflow": "TensorFlow Specialist",
    "pytorch": "PyTorch Specialist",
    "deep learning": "Deep Learning Scientist",
    "computer vision": "CV Engineer",
    "nlp": "NLP Scientist",
    "ai": "Artificial Intelligence Specialist",
    "scikit-learn": "ML Developer",
    "pandas": "Data Manipulation Specialist",
    "numpy": "Numerical Computing Specialist",
    "spark": "Big Data ML Engineer",
    "hadoop": "Distributed Systems Engineer",
    "reinforcement": "RL Specialist",
    "generative": "GenAI Specialist",
    "genai": "Generative AI Architect",
    "prompt": "Prompt Engineer",
    "llm": "LLM Researcher",
    "gpt": "GPT Model Specialist",
    "bert": "Transformer Architect",
    "huggingface": "ML Model Specialist",
    "langchain": "AI Orchestration Specialist",
    "llama": "LLM Integration Engineer",
    "vector": "Vector Database Specialist",
    "chromadb": "Embedding Specialist",
    "pinecone": "Search AI Engineer",
    "opencv": "Image Processing Engineer",
    "statistics": "Statistical Modeler",
    "probability": "Algorithm Engineer",
    "optimization": "Model Optimization Specialist",
    "deployment": "MLOps Engineer",
    "scaling": "ML Scaling Specialist",
    "inference": "Inference Optimization Engineer",
    "training": "Model Training Specialist",
    "data": "Data Science Specialist",
    "visualization": "ML Data Visualizer",
    "ethics": "AI Ethics Officer",
    "safety": "AI Safety Researcher",
    "research": "AI Research Scientist",
    "science": "Data Scientist",
    "analytics": "AI Analyst",
    "bi": "Business Intelligence AI Developer",
    "chatbot": "Conversational AI Developer",
    "voice": "Speech Recognition Engineer",
    "recommendation": "Recommender Systems Engineer",
    "ranking": "Search & Ranking Engineer",
    "graph": "Graph Neural Network Specialist",
    "edge": "Edge AI Engineer",
    "hardware": "AI Hardware Accelerator Specialist",
    "cloud": "Cloud ML Architect",
    "platform": "AI Platform Engineer",
    
    # Mobile Roles (20+)
    "react native": "React Native Developer",
    "flutter": "Flutter Developer",
    "android": "Android Developer",
    "android development": "Android App Developer",
    "ios": "iOS Developer",
    "swift": "Swift Developer",
    "kotlin": "Kotlin Developer",
    "xamarin": "Xamarin Developer",
    "ionic": "Ionic Developer",
    "mobile": "Mobile Developer",
    
    # API Roles (15+)
    "rest": "REST API Developer",
    "restful": "RESTful API Developer",
    "graphql": "GraphQL Developer",
    "grpc": "gRPC Developer",
    "api": "API Developer",
    "webhook": "Webhook Developer",
    "oauth": "OAuth Developer",
    "jwt": "JWT Developer",
    
    # Testing/QA Roles (20+)
    "selenium": "Selenium Developer",
    "pytest": "Pytest Developer",
    "jest": "Jest Developer",
    "cypress": "Cypress Developer",
    "playwright": "Playwright Developer",
    "testing": "QA Automation Engineer",
    "automation testing": "Test Automation Engineer",
    "quality assurance": "QA Engineer",
    
    # Security Roles (15+)
    "security": "Security Engineer",
    "cybersecurity": "Cybersecurity Engineer",
    "penetration testing": "Penetration Tester",
    "ethical hacking": "Ethical Hacker",
    "encryption": "Security Analyst",
    
    # Blockchain Roles (15+)
    "solidity": "Solidity Developer",
    "web3": "Web3 Developer",
    "ethereum": "Ethereum Developer",
    "blockchain": "Blockchain Developer",
    "smart contracts": "Smart Contract Developer",
    
    # Data Science Roles (20+)
    "data science": "Data Scientist",
    "data analysis": "Data Analyst",
    "data engineering": "Data Engineer",
    "statistics": "Statistician",
    "a/b testing": "Experimentation Engineer",
    
    # IoT Roles (10+)
    "iot": "IoT Developer",
    "embedded systems": "Embedded Systems Developer",
    "arduino": "Arduino Developer",
    "raspberry pi": "Raspberry Pi Developer",
    
    # ERP/Enterprise Roles (10+)
    "sap": "SAP Developer",
    "salesforce": "Salesforce Developer",
    "salesforce crm": "Salesforce CRM Developer",
    "dynamics crm": "Dynamics 365 Developer",
    
    # General/Other Roles (25+)
    "git": "Git Developer",
    "linux": "Linux Developer",
    "unix": "Unix Developer",
    "bash": "Shell Script Developer",
    "agile": "Agile Developer",
    "scrum": "Scrum Developer",
    "software": "Software Developer",
    "software development": "Software Development Engineer",
    "web": "Web Developer",
    "web development": "Web Application Developer",
    "app": "Application Developer",
    "desktop": "Desktop Application Developer",
    "game": "Game Developer",
    "ui": "UI Developer",
    "ux": "UX Developer",
    "full stack": "Full Stack Developer",
    "frontend": "Frontend Developer",
    "backend": "Backend Developer",
}


# Additional variations for same skills - Standardized Buckets
ROLE_VARIATIONS = {
    "Software Developer": [
        "Software Engineer", "Software Programmer", "Application Developer",
        "Software Development Engineer", "SDE", "App Developer", "Software Prof"
    ],
    "JavaScript Developer": [
        "JavaScript Engineer", "JS Developer", "JavaScript Programmer", "Web Developer"
    ],
    "React Developer": [
        "React.js Engineer", "React JS Developer", "React Engineer", "Front-end Developer", "Frontend Engineer"
    ],
    "Node.js Developer": [
        "NodeJS Engineer", "Node Developer", "Node.js Engineer", "Back-end Developer", "Backend Engineer"
    ],
    "Full Stack Developer": [
        "Full Stack Engineer", "Full Stack Programmer", "Web Stack Developer", "MERN Developer"
    ],
    "Python Developer": [
        "Python Engineer", "Python Programmer", "Django Developer", "Backend Developer"
    ],
    "Java Developer": [
        "Java Engineer", "Java Programmer", "Backend Developer"
    ],
    "Java Backend Developer": [
        "Java Backend Engineer", "Java API Developer", "Java REST API Developer", "Backend Java Developer"
    ],
    "Spring Boot Developer": [
        "Spring Developer", "Spring Boot Engineer", "Spring Boot API Developer"
    ],
    "Microservices Developer": [
        "Microservices Engineer", "API Microservices Developer", "Cloud Microservices Developer"
    ],
    "Node.js Backend Developer": [
        "NodeJS Backend Engineer", "Node.js API Developer", "Node Backend Engineer",
        "Express Backend Developer", "Node REST API Developer"
    ],
    "Express.js Backend Developer": [
        "Express Backend Engineer", "Express API Developer", "Node REST API Developer",
        "Express Microservices Developer"
    ],
    "Python Backend Developer": [
        "Python Backend Engineer", "Python API Developer", "Django Developer",
        "Flask Developer", "Python REST API Developer"
    ],
    "Machine Learning Engineer": [
        "ML Engineer", "ML Developer", "Machine Learning Developer", "AI Engineer"
    ],
    "Data Engineer": [
        "Data Systems Engineer", "Big Data Engineer", "Data Platform Engineer"
    ],
    "DevOps Engineer": [
        "Site Reliability Engineer", "SRE", "Infrastructure Engineer", "Cloud Engineer"
    ],
    "Cloud Engineer": [
        "Cloud Developer", "Cloud Solutions Engineer", "Cloud Architect", "AWS Developer"
    ],
}


def generate_comprehensive_roles(user_skills: list[str], max_roles: int = 50) -> list[dict]:
    """
    Generate 50-200+ roles from user skills.
    Fully comprehensive rule-based.
    """
    if not user_skills:
        return get_comprehensive_defaults()
    
    # Normalize skills
    normalized = set(s.lower().strip() for s in user_skills)
    
    role_candidates = []
    seen_roles = set()
    
    # Phase 1: Direct skill-to-role mapping
    for skill in normalized:
        if skill in SKILL_TO_ROLE:
            role = SKILL_TO_ROLE[skill]
            if role not in seen_roles:
                role_candidates.append({
                    "title": role,
                    "skill": skill,
                    "match_type": "direct"
                })
                seen_roles.add(role)
    
    # Phase 2: Category-based roles
    for category, cat_skills in COMPREHENSIVE_SKILLS.items():
        for skill in normalized:
            if skill in cat_skills:
                category_role = get_category_role(category)
                if category_role and category_role not in seen_roles:
                    role_candidates.append({
                        "title": category_role,
                        "skill": category,
                        "match_type": "category"
                    })
                    seen_roles.add(category_role)
                break
    
    # Phase 3: Add role variations
    for role_data in list(role_candidates):
        if role_data["title"] in ROLE_VARIATIONS:
            for variation in ROLE_VARIATIONS[role_data["title"]]:
                if variation not in seen_roles:
                    role_candidates.append({
                        "title": variation,
                        "skill": role_data["skill"],
                        "match_type": "variation"
                    })
                    seen_roles.add(variation)
    
    # Phase 4: Stack-based roles
    skill_set = normalized
    if {"react", "node", "mongodb"}.issubset(skill_set):
        add_stack_role("MERN Full Stack Developer", role_candidates, seen_roles)
    if {"angular", "node", "mongodb"}.issubset(skill_set):
        add_stack_role("MEAN Full Stack Developer", role_candidates, seen_roles)
    if {"python", "django"}.issubset(skill_set):
        add_stack_role("Python Django Developer", role_candidates, seen_roles)
    if {"python", "flask"}.issubset(skill_set):
        add_stack_role("Python Flask Developer", role_candidates, seen_roles)
    if {"python", "machine learning"}.issubset(skill_set):
        add_stack_role("Python ML Engineer", role_candidates, seen_roles)
    if {"java", "spring"}.issubset(skill_set):
        add_stack_role("Java Spring Developer", role_candidates, seen_roles)
    
    # Phase 5: General fallback roles
    if len(role_candidates) < 10:
        for role in get_comprehensive_defaults()[:15]:
            if role["title"] not in seen_roles:
                role_candidates.append(role)
                seen_roles.add(role["title"])
    
    return role_candidates[:max_roles]


def add_stack_role(role: str, role_list: list, seen: set):
    """Helper to add stack role"""
    if role not in seen:
        role_list.append({"title": role, "skill": "stack", "match_type": "stack"})
        seen.add(role)


def get_category_role(category: str) -> str:
    """Get role from category"""
    category_roles = {
        "programming": "Software Developer",
        "frontend": "Frontend Developer",
        "backend": "Backend Developer",
        "database": "Database Developer",
        "cloud": "Cloud Engineer",
        "devops": "DevOps Engineer",
        "mobile": "Mobile Developer",
        "data": "Data Engineer",
        "ml": "Machine Learning Engineer",
        "api": "API Developer",
        "testing": "QA Automation Engineer",
        "security": "Security Engineer",
        "blockchain": "Blockchain Developer",
        "erp": "Enterprise Developer",
        "qa": "QA Engineer",
        "datascience": "Data Scientist",
        "iot": "IoT Developer",
    }
    return category_roles.get(category, "")


def get_comprehensive_defaults() -> list[dict]:
    """Default roles if no skills match"""
    return [
        {"title": "Software Developer", "skill": "default"},
        {"title": "Full Stack Developer", "skill": "default"},
        {"title": "Web Developer", "skill": "default"},
        {"title": "Application Developer", "skill": "default"},
        {"title": "Programmer", "skill": "default"},
        {"title": "Engineer", "skill": "default"},
        {"title": "Technical Developer", "skill": "default"},
        {"title": "System Developer", "skill": "default"},
    ]


def generate_search_roles_expanded(user_skills: list[str], platform: str = "naukri") -> list[dict]:
    """
    Generate search roles for platform - limited to 5-6 best roles only.
    LLM generates best roles first, rule-based fills gaps if needed.
    """
    # Get LLM search roles (more intelligent, better job titles)
    llm_search = generate_llm_roles(user_skills, max_roles=10)
    
    # Get rule-based roles for fallback
    rule_roles = generate_comprehensive_roles(user_skills, max_roles=20)
    
    search_roles = []
    seen_roles = set()
    order = 1
    max_search_roles = 6  # Only 5-6 search roles
    
    # First add LLM roles (higher quality) - up to 6
    for role in llm_search:
        if order > max_search_roles:
            break
        title = role["title"]
        title_lower = title.lower()
        if title_lower not in seen_roles:
            search_roles.append({
                "role": title,
                "query_order": order,
                "platform": platform,
                "generated_by": "llm"
            })
            seen_roles.add(title_lower)
            order += 1
    
    # Add best rule-based roles if needed to fill to 5-6
    if order <= max_search_roles:
        # Prioitize core roles the user specifically wants
        priority_keywords = [
            'java developer', 'python developer', 'full stack developer', 
            'mern developer', 'backend developer', 'frontend developer',
            'mern', 'node', 'react', 'spring', 'django'
        ]
        
        for role in rule_roles:
            if order > max_search_roles:
                break
            title = role["title"]
            title_lower = title.lower()
            if title_lower not in seen_roles:
                # High priority if it matches one of our top-6 target keywords
                if any(kw in title_lower for kw in priority_keywords):
                    search_roles.append({
                        "role": title,
                        "query_order": order,
                        "platform": platform,
                        "generated_by": "rule"
                    })
                    seen_roles.add(title_lower)
                    order += 1
    
    return search_roles


# Demo
if __name__ == "__main__":
    print("=== Expanded Role Generator (200+ Roles) ===\n")
    
    test_skills = [
        "React", "Node.js", "MongoDB", "Express", "JavaScript",
        "Python", "Django", "AWS", "Docker", "Kubernetes",
        "Machine Learning", "TensorFlow", "SQL", "PostgreSQL"
    ]
    
    print(f"Input skills: {test_skills}\n")
    
    # Generate 50 roles
    roles = generate_comprehensive_roles(test_skills, max_roles=50)
    print(f"Generated roles: {len(roles)}\n")
    
    for i, r in enumerate(roles[:20], 1):
        print(f"  {i}. {r['title']}")
    
    print(f"\n... and {len(roles) - 20} more roles\n")
    
    # Search roles
    print("=== Search Roles (30) ===")
    search = generate_search_roles_expanded(test_skills, "naukri")
    print(f"Search roles: {len(search)}")
    for s in search[:10]:
        print(f"  - {s['role']}")


# ==================== BACKWARD COMPATIBILITY ====================

# Old function names for scraper compatibility

def generate_roles_from_skills(user_skills: list[str], max_roles: int = 6) -> list[dict]:
    """Legacy function - use generate_comprehensive_roles instead"""
    return generate_comprehensive_roles(user_skills, max_roles=max_roles)


def get_role_by_top_skills(user_skills: list[str], top_n: int = 5) -> list[dict]:
    """Legacy function - returns top N roles"""
    roles = generate_comprehensive_roles(user_skills, max_roles=top_n)
    # Convert to old format
    return [{"title": r["title"], "skill": r.get("skill", ""), "category": r.get("match_type", "")} for r in roles]


def extract_role_from_skills(user_skills: list[str]) -> dict:
    """Legacy function - returns primary role"""
    roles = generate_comprehensive_roles(user_skills, max_roles=1)
    return roles[0] if roles else {"title": "Software Developer", "category": "default"}


def generate_dynamic_resumes_from_skills(user_skills: list[str]) -> list[dict]:
    """Legacy function - returns resume configs"""
    roles = generate_comprehensive_roles(user_skills, max_roles=6)
    return [
        {
            "role_key": r["title"].lower().replace(" ", "_").replace(".", ""),
            "title": r["title"],
            "keywords": [r.get("skill", "")],
            "summary": f"Experienced {r['title']} with technical expertise.",
            "generated_by": "rule"
        }
        for r in roles
    ]


def generate_search_roles_hybrid(user_skills: list[str], platform: str = "naukri") -> list[dict]:
    """Legacy function - generates search roles"""
    return generate_search_roles_expanded(user_skills, platform)


# ==================== GROQ POWERED ROLE GENERATION ====================

def generate_llm_roles(user_skills: list[str], max_roles: int = 10) -> list[dict]:
    """
    Generate intelligent roles using Groq LLM (Llama).
    This creates more accurate job titles based on skill combinations.
    
    Example: Node.js + React + MongoDB -> MERN Full Stack Developer
    """
    if not GROQ_API_KEY or not user_skills:
        print("[GROQ] No API key or skills, using rule-based fallback")
        return generate_comprehensive_roles(user_skills, max_roles=max_roles)
    
    try:
        import requests
        
        skills_str = ", ".join(user_skills[:15])
        
        prompt = f"""You are a job title expert. Based on the following skills, generate exactly {max_roles} job titles that recruiters would search for.

Skills: {skills_str}

Return ONLY a JSON array of job titles (strings), no other text. Example:
["React Developer", "Node.js Backend Developer", "MERN Full Stack Developer"]"""

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You are a helpful job title expert. Return only JSON array."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[GROQ] API error: {response.status_code}, falling back to rules")
            return generate_comprehensive_roles(user_skills, max_roles=max_roles)
        
        result_data = response.json()
        text = result_data['choices'][0]['message']['content'].strip()
        
        # Clean response
        if '```json' in text:
            text = text.replace('```json', '').replace('```', '').strip()
        elif '```' in text:
            text = text.replace('```', '').strip()
        
        import json
        llm_roles = json.loads(text)
        
        # Convert to our format
        result = []
        for title in llm_roles:
            result.append({
                "title": title,
                "skill": user_skills[0] if user_skills else "",
                "match_type": "llm"
            })
        
        print(f"[GROQ] Generated {len(result)} intelligent roles")
        return result
        
    except Exception as e:
        print(f"[GROQ] Error: {e}, falling back to rule-based")
        return generate_comprehensive_roles(user_skills, max_roles=max_roles)


def generate_combined_roles(user_skills: list[str], max_roles: int = 20) -> list[dict]:
    """
    Combine LLM roles with rule-based for best coverage.
    LLM provides intelligent stack-based roles, rules fill gaps.
    """
    # Get LLM roles first (more intelligent)
    llm_roles = generate_llm_roles(user_skills, max_roles=max_roles // 2)
    
    # Get rule-based roles
    rule_roles = generate_comprehensive_roles(user_skills, max_roles=max_roles)
    
    # Combine and dedupe - prioritize LLM roles (more intelligent)
    # Also add some best rule-based roles that LLM might have missed
    seen_titles = set()
    combined = []
    
    # Priority order: LLM roles first, then add best rule roles
    # For resume roles: limit to 5-6 best
    max_resume = 6
    
    # Add LLM roles first (these are more intelligent)
    for role in llm_roles:
        if len(combined) >= max_resume:
            break
        title_lower = role["title"].lower()
        if title_lower not in seen_titles:
            combined.append(role)
            seen_titles.add(title_lower)
    
    # Add best rule-based roles to fill remaining slots
    # Prefer: stack-based, full stack, combined roles
    priority_keywords = ['full stack', 'mern', 'mean', 'stack', 'backend', 'frontend', 'developer', 'engineer']
    
    for role in rule_roles:
        if len(combined) >= max_resume:
            break
        title_lower = role["title"].lower()
        if title_lower not in seen_titles:
            # Check if it has priority keywords or is different from LLM
            is_priority = any(kw in title_lower for kw in priority_keywords)
            if is_priority:
                combined.append(role)
                seen_titles.add(title_lower)
    
    return combined[:max_resume]


def generate_fresher_centric_roles(user_skills: list[str], experience_years: int = 0) -> list[str]:
    """
    Generate highly relevant job search roles for Freshers/Entry-level.
    Logic:
    1. Skill-based roles (Frontend, Backend, Full Stack)
    2. Tech-specific roles
    3. Universal fresher titles
    """
    normalized_skills = [s.lower().strip() for s in user_skills]
    
    TECH_MAPPINGS = {
        'react': 'React', 'react.js': 'React', 'angular': 'Angular', 'vue': 'Vue', 'vue.js': 'Vue',
        'javascript': 'JavaScript', 'typescript': 'TypeScript', 'nextjs': 'Next.js', 'next.js': 'Next.js',
        'html': 'HTML', 'html5': 'HTML', 'css': 'CSS', 'css3': 'CSS', 'tailwind': 'Tailwind',
        'java': 'Java', 'spring': 'Spring', 'springboot': 'Spring Boot', 'node': 'Node.js',
        'nodejs': 'Node.js', 'node.js': 'Node.js', 'python': 'Python', 'django': 'Django',
        'flask': 'Flask', 'fastapi': 'FastAPI', 'php': 'PHP', 'laravel': 'Laravel',
        'csharp': 'C#', '.net': '.NET', 'dotnet': '.NET', 'golang': 'Go', 'go': 'Go',
        'mongodb': 'MongoDB', 'express': 'Express', 'sql': 'SQL'
    }
    
    FRONTEND_SKILLS = {'react', 'angular', 'vue', 'javascript', 'typescript', 'nextjs', 'html', 'css', 'tailwind', 'html5', 'css3', 'vue.js', 'react.js'}
    BACKEND_SKILLS = {'java', 'python', 'node', 'php', 'golang', 'csharp', 'django', 'spring', 'flask', 'express', 'nodejs', 'node.js'}
    FULLSTACK_SKILLS = {'react', 'angular', 'vue', 'node', 'python', 'mongodb', 'express', 'javascript', 'typescript'}
    
    roles = []
    
    has_frontend = any(s in FRONTEND_SKILLS for s in normalized_skills)
    has_backend = any(s in BACKEND_SKILLS for s in normalized_skills)
    has_fullstack = any(s in FULLSTACK_SKILLS for s in normalized_skills)
    
    matched_techs = set()
    for skill in normalized_skills:
        if skill in TECH_MAPPINGS:
            matched_techs.add(TECH_MAPPINGS[skill])
    
    if has_frontend:
        for tech in ['React', 'Angular', 'Vue', 'JavaScript']:
            if tech in matched_techs:
                roles.append(f"{tech} Frontend Developer")
                roles.append(f"Frontend Developer")
        if 'JavaScript' in matched_techs or 'TypeScript' in matched_techs:
            roles.append("JavaScript Developer")
            roles.append("Frontend Developer")
    
    if has_backend:
        for tech in ['Java', 'Python', 'Node.js', 'PHP', 'Go']:
            if tech in matched_techs:
                roles.append(f"{tech} Backend Developer")
                roles.append(f"Backend Developer")
        if 'Java' in matched_techs:
            roles.append("Java Developer")
        if 'Python' in matched_techs:
            roles.append("Python Developer")
    
    if has_fullstack:
        roles.append("Full Stack Developer")
        if all(t in matched_techs for t in ['React', 'Node.js', 'MongoDB']):
            roles.append("MERN Stack Developer")
        if all(t in matched_techs for t in ['Angular', 'Node.js', 'MongoDB']):
            roles.append("MEAN Stack Developer")
    
    if not roles:
        roles.extend(["Associate Software Engineer", "Web Developer", "Graduate Engineer Trainee", "Software Developer"])
    
    BLACKLIST = {'git', 'jenkins', 'sql', 'jira', 'maven', 'gradle', 'svn', 'bitbucket', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'rest', 'rest api'}
    
    filtered = [r for r in roles if not any(b in r.lower() for b in BLACKLIST)]
    unique_roles = list(dict.fromkeys(filtered))
    
    final_roles = []
    for i, r in enumerate(unique_roles):
        if experience_years == 0 and i < 4:
            final_roles.append(f"{r} Fresher")
        else:
            final_roles.append(r)
            
    return final_roles[:10]