"""
Job Generator - Job Automation System
=======================================
Generates dynamic job search URLs from student profile (resume title + filters).
Now uses dynamic_role_generator for intelligent role generation.
"""

from __future__ import annotations
from typing import Optional
from urllib.parse import quote_plus, urlencode
from config.settings import settings
from config.platforms import get_platform_config

from role_manager.dynamic_role_generator import (
    generate_comprehensive_roles,
    get_role_by_top_skills,
)


class JobGenerator:
    """
    Generates job search URLs based on student profile.
    
    Uses resume title + skills to build search queries.
    """
    
    def __init__(self, platform: str):
        self.platform = platform.lower()
        self.config = get_platform_config(platform)
    
    def generate_search_url(
        self,
        student: any,
        page: int = 1,
        location: Optional[str] = None,
    ) -> str:
        """
        Generate job search URL for student.
        
        Args:
            student: Student object with profile
            page: Page number for pagination
            location: Optional location filter
            
        Returns:
            Search URL string
        """
        # Build query from candidate titles
        query = self._build_query(student)
        
        # Build location
        loc = location or self._get_default_location(student)
        
        # Generate platform-specific URL
        if self.platform == "naukri":
            return self._naukri_url(query, loc, page)
        elif self.platform == "linkedin":
            return self._linkedin_url(query, loc, page)
        elif self.platform == "foundit":
            return self._foundit_url(query, loc, page)
        
        return ""
    
    def _build_queries(self, student: any) -> list[str]:
        """Build 6 roles: Full Stack → Frontend → Backend → Other"""
        queries = []
        student_skills = [s.lower().strip() for s in (student.skills or [])]
        
        # Check partial match (e.g., "react.js" contains "react")
        def has_skill(*targets):
            for target in targets:
                for skill in student_skills:
                    if target in skill:
                        return True
            return False
        
        def add_role(role):
            if role not in queries:
                queries.append(role)
        
        # ==== 1. PRIMARY ROLE (HIGHEST PRIORITY) ====
        if getattr(student, 'primary_role', None):
            add_role(student.primary_role)

        # ==== 2. FULL STACK ====
        if has_skill("react") and has_skill("node") and has_skill("mongo") and has_skill("express"):
            add_role("MERN Full Stack Developer")
        elif has_skill("angular") and has_skill("node") and has_skill("mongo") and has_skill("express"):
            add_role("MEAN Full Stack Developer")
        elif has_skill("java", "spring") and has_skill("react", "angular"):
            add_role("Java Full Stack Developer")
        elif has_skill("python") and has_skill("django", "flask"):
            add_role("Python Full Stack Developer")
        elif has_skill("c#", ".net"):
            add_role(".NET Full Stack Developer")
        
        # ==== 2. FRONTEND ====
        if has_skill("react") and "React" not in str(queries):
            add_role("React Developer")
        if has_skill("angular") and "Angular" not in str(queries):
            add_role("Angular Developer")
        if has_skill("vue") and "Vue" not in str(queries):
            add_role("Vue.js Developer")
        if has_skill("typescript") and "TypeScript" not in str(queries):
            add_role("TypeScript Developer")
        if has_skill("javascript") and "JavaScript" not in str(queries):
            add_role("JavaScript Developer")
        if has_skill("nextjs", "next.js") and "Next" not in str(queries):
            add_role("Next.js Developer")
        if has_skill("svelte") and "Svelte" not in str(queries):
            add_role("Svelte Developer")
        if has_skill("tailwind") and "Tailwind" not in str(queries):
            add_role("Tailwind CSS Developer")
        if has_skill("ui", "ux") and "UI" not in str(queries):
            add_role("UI/UX Engineer")
        
        # ==== 3. BACKEND ====
        if (has_skill("spring") or has_skill("springboot")) and "Java" not in str(queries):
            add_role("Java Backend Developer")
        elif has_skill("java") and "Java" not in str(queries):
            add_role("Java Developer")
        
        if has_skill("python") and "Python" not in str(queries):
            add_role("Python Backend Developer")
        if has_skill("node") and has_skill("express") and "Node" not in str(queries):
            add_role("Node.js Backend Developer")
        if has_skill("golang") and "Go" not in str(queries):
            add_role("Go Developer")
        if has_skill("django") and "Django" not in str(queries):
            add_role("Django Developer")
        if has_skill("flask") and "Flask" not in str(queries):
            add_role("Flask Developer")
        if has_skill("nestjs", "nest.js") and "Nest" not in str(queries):
            add_role("NestJS Developer")
        if has_skill("laravel", "php") and "Laravel" not in str(queries):
            add_role("Laravel Developer")
        if has_skill("fastapi") and "FastAPI" not in str(queries):
            add_role("FastAPI Developer")
        if has_skill("c#", ".net") and ".NET" not in str(queries):
            add_role(".NET Core Developer")
        
        # ==== 4. OTHER / DATABASE / DEVOPS ====
        if has_skill("sql", "mysql", "postgres", "mongo") and "Database" not in str(queries):
            add_role("Database Developer")
        if has_skill("docker", "k8s", "kubernetes") and "DevOps" not in str(queries):
            add_role("DevOps Engineer")
        if has_skill("aws", "azure", "gcp") and "Cloud" not in str(queries):
            add_role("Cloud Engineer")
        if has_skill("sre", "reliability") and "SRE" not in str(queries):
            add_role("Site Reliability Engineer (SRE)")
        if has_skill("terraform", "ansible", "infrastructure") and "Infra" not in str(queries):
            add_role("Infrastructure Engineer")
        if has_skill("kubernetes", "k8s") and "K8s" not in str(queries):
            add_role("Kubernetes Administrator")
        
        # ==== 5. AI / ML / DATA SCIENCE ====
        if has_skill("machine learning", "tensorflow", "pytorch", "deep learning") and "ML" not in str(queries):
            add_role("Machine Learning Engineer")
        if has_skill("ai", "artificial intelligence", "genai", "llm") and "AI" not in str(queries):
            add_role("AI Engineer")
        if has_skill("nlp", "language processing") and "NLP" not in str(queries):
            add_role("NLP Engineer")
        if has_skill("computer vision", "opencv") and "Vision" not in str(queries):
            add_role("Computer Vision Engineer")
        if has_skill("deep learning", "neural networks") and "Deep" not in str(queries):
            add_role("Deep Learning Engineer")
        if has_skill("mlops", "deployment") and "MLOps" not in str(queries):
            add_role("MLOps Engineer")
        if has_skill("data science", "data scientist") and "Data Science" not in str(queries):
            add_role("Data Scientist")
        if has_skill("data analyst", "data analysis", "tableau", "power bi") and "Data Analyst" not in str(queries):
            add_role("Data Analyst")
        
        # ==== 6. CYBER SECURITY ====
        if has_skill("cybersecurity", "security", "ethical hacking", "penetration") and "Security" not in str(queries):
            add_role("Cyber Security Engineer")
            add_role("Security Analyst")

        # ==== 7. MOBILE DEVELOPMENT ====
        if has_skill("react native") and "React Native" not in str(queries):
            add_role("React Native Developer")
        if has_skill("flutter") and "Flutter" not in str(queries):
            add_role("Flutter Developer")
        if has_skill("android", "kotlin") and "Android" not in str(queries):
            add_role("Android Developer")
        if has_skill("ios", "swift") and "iOS" not in str(queries):
            add_role("iOS Developer")

        # ==== 8. BLOCKCHAIN / WEB3 ====
        if has_skill("solidity", "blockchain", "web3", "ethereum") and "Blockchain" not in str(queries):
            add_role("Blockchain Developer")
            add_role("Solidity Developer")

        # ==== 9. TESTING / QA ====
        if has_skill("testing", "qa", "selenium", "cypress", "playwright") and "QA" not in str(queries):
            add_role("QA Automation Engineer")
            add_role("Automation Tester")

        # ==== 10. API / MICROSERVICES ====
        if has_skill("graphql", "grpc", "rest", "microservices") and "API" not in str(queries):
            add_role("API Developer")
            add_role("Microservices Engineer")
        
        # ==== 6. FALLBACK (CANDIDATE TITLES) ====
        if getattr(student, 'candidate_titles', None) and len(student.candidate_titles) > 0:
            for title in student.candidate_titles:
                add_role(title)
        
        # ==== 7. DEFAULT ROLES ====
        # Pad to 6
        while len(queries) < 6:
            defaults = ["Software Developer", "Software Engineer"]
            for d in defaults:
                add_role(d)
                if len(queries) >= 6:
                    break
        
        return queries[:6]
    
    def _get_default_location(self, student: any) -> str:
        """Get default location from student."""
        if student.preferred_locations and len(student.preferred_locations) > 0:
            return student.preferred_locations[0]
        
        if student.location:
            return student.location
        
        return "India"
    
    def _naukri_url(self, query: str, location: str, page: int) -> str:
        """Generate Naukri search URL with optimized params for internal apply buttons."""
        # Dynamic query from input
        query_slug = query.lower().replace(" ", "-")
        query_param = quote_plus(query)
        
        # Build URL with query dynamically
        base = f"https://www.naukri.com/{query_slug}-jobs-in-bengaluru"
        
        # Optimized params:
        # - wfhType=0,2,3 (workMode: In-office, WFH, Hybrid)
        # - functionAreaIdGid=5 (IT/Software Engineering) 
        # - jobAge=15 (last 15 days - more volume)
        # - naukriCampus=true (verified companies)
        url = f"{base}?k={query_param}&l=bengaluru,hyderabad,chennai,mumbai,delhi&qproductJobSource=2&naukriCampus=true&nignbevent_src=jobsearchDeskGNB&experience=0&wfhType=0&wfhType=2&wfhType=3&functionAreaIdGid=5&glbl_qcrc=1028&jobPostType=1&jobAge=15"
        
        if page > 1:
            url += f"&start={(page-1)*20}"
        
        return url
    
    def _linkedin_url(self, query: str, location: str, page: int) -> str:
        """Generate LinkedIn search URL."""
        base = "https://www.linkedin.com/jobs/search/"
        
        params = {
            "keywords": query,
            "location": location,
            "f_TPR": "r604800",  # Past week
            "f_WT": "2",  # Full-time
            "f_E": "1",  # Entry level
            "start": (page - 1) * 25,  # LinkedIn uses start parameter
        }
        
        return f"{base}?{urlencode(params)}"
    
    
    def _foundit_url(self, query: str, location: str, page: int) -> str:
        """Generate Foundit search URL."""
        base = "https://www.foundit.in/jobs/"
        
        query_slug = query.lower().replace(" ", "-")
        loc_slug = location.lower().replace(" ", "-")
        
        url = f"{base}?searchId=&keyword={quote_plus(query)}&location={quote_plus(loc_slug)}"
        
        if page > 1:
            url += f"&pageNo={page}"
        
        return url
    
    def generate_job_urls(
        self,
        student: any,
        max_jobs: int = 10,
        locations: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Generate multiple job URLs for a student using TOP 5-6 skills with dynamic roles.
        
        Args:
            student: Student object
            max_jobs: Maximum number of jobs to generate (default 10, uses top 5-6 skills)
            locations: Optional list of locations to search
            
        Returns:
            List of job URL dictionaries
        """
        job_urls = []
        
        # Get TOP 5-6 queries from dynamic roles
        all_queries = self._build_queries(student)
        
        # Use provided locations or default
        search_locations = locations or student.preferred_locations or ["India"]
        if not search_locations:
            search_locations = ["India"]
        
        # Generate URLs for EACH skill/query
        for location in search_locations[:3]:
            for query in all_queries:
                if len(job_urls) >= max_jobs:
                    break
                
                # Generate URL for each query
                url = self._generate_url_for_query(query, location, 1)
                
                if url:
                    job_urls.append({
                        "url": url,
                        "location": location,
                        "page": 1,
                        "resume_variant": self._select_resume_variant(student, location),
                        "query": query,
                    })
        
        return job_urls[:max_jobs]
    
    def _generate_url_for_query(self, query: str, location: str, page: int) -> str:
        """Generate URL for a specific query."""
        if self.platform == "naukri":
            return self._naukri_url(query, location, page)
        elif self.platform == "linkedin":
            return self._linkedin_url(query, location, page)
        elif self.platform == "foundit":
            return self._foundit_url(query, location, page)
        return ""
    
    def _select_resume_variant(self, student: any, location: str) -> str:
        """Select appropriate resume variant based on job."""
        # Simple logic - can be enhanced with LLM
        if student.candidate_titles:
            title = student.candidate_titles[0].lower()
            if "frontend" in title or "react" in title or "ui" in title:
                return "frontend"
            elif "backend" in title or "python" in title or "java" in title:
                return "backend"
            elif "full" in title or "stack" in title:
                return "fullstack"
        
        return "backend"  # Default


def get_job_urls(
    student: any,
    platform: str,
    max_jobs: int = 50,
) -> list[dict]:
    """
    Get job URLs for a student on a platform using ALL skills.
    
    Args:
        student: Student object
        platform: Platform name
        max_jobs: Maximum number of jobs (default 50 for all skills)
        
    Returns:
        List of job URL dicts
    """
    generator = JobGenerator(platform)
    return generator.generate_job_urls(student, max_jobs)