from __future__ import annotations
import re
import json
import httpx
import os
import random
import asyncio
from typing import Any


class LLMAnswers:
    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger
        self._client = None

    async def build_default_answers(
        self,
        profile: Any,
        job: dict[str, Any],
        analysis: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        summary_skills = (analysis or {}).get("priority_skills") or profile.skills
        role = job.get("title", "Software Engineer")
        company = job.get("company", "the company")
        skill_phrase = ", ".join(summary_skills) or "software development"

        base = {
            "about_me": self._limit_lines(
                f"I am a fresher software developer with hands-on projects in {skill_phrase}. "
                f"I enjoy building reliable web features, APIs, and clean user experiences. "
                f"I am excited to contribute quickly and grow in the {role} role."
            ),
            "why_hire": self._limit_lines(
                f"I match this role through practical work in {skill_phrase}. "
                "I can onboard fast, take ownership of tasks, and deliver maintainable code. "
                "I also bring strong learning agility and a collaborative mindset."
            ),
            "why_this_role": self._limit_lines(
                f"This {role} opportunity at {company} aligns with my fresher goals and technical strengths. "
                f"The role focus on {skill_phrase} matches my project experience and growth direction."
            ),
            "relocate": "Yes, I am open to relocate based on role requirements.",
            "notice_period": "Immediate",
            "current_ctc": "180000",
            "expected_salary": "340000",
            "cover_letter": await self.generate_cover_letter(profile, job, analysis=analysis),
        }
        return base

    async def generate_cover_letter(
        self,
        profile: Any,
        job: dict[str, Any],
        analysis: dict[str, Any] | None = None,
    ) -> str:
        prompt = (
            "Write a concise cover letter in 120-150 words. Keep it human, specific, and fresher-friendly.\n"
            f"Candidate: {profile.name}\n"
            f"Role: {job.get('title', '')}\n"
            f"Company: {job.get('company', '')}\n"
            f"Top skills: {', '.join((analysis or {}).get('top_skills', profile.skills)[:6])}\n"
            f"JD summary: {job.get('description', '')[:1200]}"
        )
        llm_response = await self._ask_llm(prompt, max_tokens=230)
        if llm_response:
            return llm_response

        role = job.get("title", "Software Engineer")
        company = job.get("company", "your company")
        skills = ", ".join(((analysis or {}).get("priority_skills") or profile.skills)) or "software development"
        return (
            f"Dear Hiring Team,\n\n"
            f"I am excited to apply for the {role} role at {company}. As a fresher, I have built practical "
            f"projects using {skills}, with a focus on reliable APIs, clean code, and collaborative delivery.\n\n"
            "I am comfortable learning quickly, adapting to team workflows, and contributing to production-ready "
            "features. I would value the opportunity to support your team and grow through real engineering challenges.\n\n"
            "Thank you for your consideration."
        )

    async def answer_question(
        self,
        question: str,
        profile: Any,
        job: dict[str, Any],
        analysis: dict[str, Any] | None = None,
        context: str = "",
        field_type: str = "text",
        options: list[str] | None = None,
    ) -> dict[str, str]:
        """
        AI Job Application Assistant: Answers bot questions with strict JSON output.
        Returns: {"type": "option" | "text", "answer": "..."}
        """
        question_clean = (question or "").strip().lower()
        
        # Parse question type and generate smart answer
        q_type, q_skill = self._parse_question_type(question_clean, profile)
        
        # Build smart answer based on question type
        smart_answer = self._get_smart_answer(q_type, q_skill, profile, options, question_clean)
        
        if smart_answer:
            if options:
                # Match to available options
                from utils.job_retrieval import fuzzy_match_option
                matched = fuzzy_match_option(smart_answer, options)
                return {"type": "option", "answer": matched or options[0]}
            return {"type": "text", "answer": smart_answer}
        
        # Build resume/project context if smart answer failed
        if not context:
            context = self._build_candidate_context(profile)
        
        options_str = f"\nAVAILABLE OPTIONS: {', '.join(options)}" if options else "\nNO OPTIONS PROVIDED"
        
        prompt = (
            f"SYSTEM: You are an AI job application assistant. Answer the exact question using the candidate resume context.\n"
            f"RULES:\n"
            f"1. Relocation -> Always 'Yes'\n"
            f"2. Work from office -> Always 'Yes' or 'Willing to work'\n"
            f"3. Notice period -> 'Immediate' or '0 days'\n"
            f"4. Current salary/current CTC -> '180000'. Expected salary -> 'As per company standards' unless a number is required.\n"
            f"5. For Experience, Skills, and Personal Details -> ALWAYS use the provided CONTEXT. If the exact detail is NOT found, use fresher-related answers (e.g., '0', 'Fresher', 'Academic Projects only', 'Not applicable as I am a fresher').\n"
            f"6. Technical questions -> Give a concise definition or major points based on the CONTEXT.\n"
            f"7. For 'how much', 'how many', 'how long', 'how years' experience questions -> ALWAYS return NUMBER (like 1, 2, 0). If not found in CONTEXT, return '0'!\n"
            f"8. Return EXACTLY a JSON object with 'type' ('option' or 'text') and 'answer'.\n\n"
            f"QUESTION: {question_clean}\n"
            f"FIELD_TYPE: {field_type}\n"
            f"CONTEXT: {context}\n"
            f"{options_str}\n\n"
            f"STRICT JSON OUTPUT:"
        )
        
        raw_response = await self._ask_llm(prompt, max_tokens=150)
        
        if raw_response:
            try:
                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    if "type" in result and "answer" in result:
                        if options and result["type"] == "option":
                            from utils.job_retrieval import fuzzy_match_option
                            matched = fuzzy_match_option(result["answer"], options)
                            if matched:
                                result["answer"] = matched
                            else:
                                result["answer"] = options[0]
                        return result
            except Exception as e:
                self.logger.warning(f"JSON parse failed for LLM answer: {e}")

        # Fallback
        fallback = {"type": "text", "answer": "0"}
        if options:
            fallback = {"type": "option", "answer": options[0]}
        
        if raw_response:
            ans = raw_response.strip().strip("'\"")
            if options:
                from utils.job_retrieval import fuzzy_match_option
                matched = fuzzy_match_option(ans, options)
                return {"type": "option", "answer": matched or options[0]}
            return {"type": "text", "answer": ans}
            
        return fallback
    
    def _parse_question_type(self, question: str, profile: Any | None = None) -> tuple[str, str]:
        """Parse question to understand what it's asking"""
        q = question.lower()
        profile_skill = self._find_profile_skill_in_question(q, profile)
        
        # ===== ALWAYS RETURN NUMBER FOR "how much/many/long" questions =====
        number_patterns = ['how much', 'how many', 'how long', 'how years', 'how experience', 'years of', 'how skilled', 'how good', 'how familiar']
        if any(pat in q for pat in number_patterns):
            # Extract skill if mentioned
            asked_skill = self._extract_skill_candidate_from_question(q)
            return 'experience_number', asked_skill or 'general'
        
        # Salary questions must run before experience parsing because "expected"
        # contains the substring "exp".
        if 'salary' in q or 'ctc' in q or 'package' in q or 'expected' in q:
            return 'salary', ''

        # Project questions should use resume/project context.
        if 'project' in q or 'projects' in q:
            return 'project', ''

        # Experience questions
        if 'experience' in q or re.search(r'\bexp\b', q) or 'years' in q:
            if profile_skill: return 'experience', profile_skill
            if 'api' in q or 'rest' in q: return 'experience', 'api'
            if 'project' in q: return 'project', ''
            if 'full stack' in q or 'fullstack' in q: return 'experience', 'fullstack'
            asked_skill = self._extract_skill_candidate_from_question(q)
            return 'experience', asked_skill or 'general'

        # Technical concept questions should be answered directly, not as "Fresher".
        technical_starters = [
            'what is', 'what are', 'explain', 'define', 'describe',
            'difference between', 'how do', 'how would', 'tell me about'
        ]
        generic_technical_terms = [
            'api', 'rest', 'http', 'database', 'query', 'programming',
            'oops', 'object oriented', 'authentication', 'authorization',
            'token', 'frontend', 'backend'
        ]
        if any(q.startswith(x) for x in technical_starters) and (
            any(t in q for t in generic_technical_terms) or bool(profile_skill)
        ):
            return 'technical', ''
        
        # Notice period
        if 'notice' in q or 'joining' in q or 'available' in q:
            return 'notice', ''
        
        # Relocation
        if 'relocat' in q or 'shift' in q or 'move' in q:
            return 'relocation', ''
        
        # Work from office
        if 'work from' in q or 'office' in q or 'remote' in q or 'wfh' in q:
            return 'work_mode', ''
        
        # Fresher
        if 'fresher' in q or 'new grad' in q or 'graduate' in q:
            return 'fresher', ''
        
        # Skills
        if 'skills' in q or 'technology' in q or 'tech' in q:
            return 'skills', ''
        
        # Location
        if 'location' in q or 'city' in q or 'place' in q:
            return 'location', ''
        
        return 'general', ''
    
    def _get_smart_answer(
        self,
        q_type: str,
        q_skill: str,
        profile: Any,
        options: list | None,
        question: str = "",
    ) -> str:
        """Generate smart answer based on question type"""
        question_context = self._build_candidate_context(profile)
        
        # ===== ALWAYS RETURN NUMBER for "how much/many/long" questions =====
        if q_type == 'experience_number':
            return '' # Let AI handle it using RAG context
        
        # Experience answers (also return number)
        if q_type == 'experience':
            return '' # Let AI handle it using RAG context
        
        # Salary
        if q_type == 'salary':
            return self._salary_answer(question) if not options else ''
        
        # Notice period
        if q_type == 'notice':
            return 'Immediate' if not options else ''
        
        # Relocation
        if q_type == 'relocation':
            return 'Yes' if not options else ''
        
        # Work mode
        if q_type == 'work_mode':
            return 'Yes' if not options else ''
        
        # Fresher
        if q_type == 'fresher':
            return 'Yes' if not options else ''
        
        # Skills
        if q_type == 'skills':
            return '' # Let AI handle it using RAG context

        if q_type == 'project':
            return self._project_answer(profile) if not options else ''

        if q_type == 'technical':
            return self._technical_answer_from_question(question) if not options else ''
        
        # Location
        if q_type == 'location':
            loc = getattr(profile, 'location', '')
            if loc:
                return loc
            return 'India' if not options else ''
        
        return ''

    def _profile_skill_terms(self, profile: Any | None) -> list[str]:
        skills = getattr(profile, "skills", []) if profile else []
        terms = []
        for skill in skills or []:
            text = str(skill or "").strip().lower()
            if not text:
                continue
            terms.append(text)
            compact = re.sub(r"[^a-z0-9]+", "", text)
            if compact and compact != text:
                terms.append(compact)
        return list(dict.fromkeys(terms))

    def _find_profile_skill_in_question(self, question: str, profile: Any | None) -> str:
        q = str(question or "").lower()
        q_compact = re.sub(r"[^a-z0-9]+", "", q)
        skills = getattr(profile, "skills", []) if profile else []
        for skill in skills or []:
            skill_text = str(skill or "").strip()
            skill_lower = skill_text.lower()
            skill_compact = re.sub(r"[^a-z0-9]+", "", skill_lower)
            if not skill_lower:
                continue
            if re.search(rf"\b{re.escape(skill_lower)}\b", q) or (skill_compact and skill_compact in q_compact):
                return skill_text
        return ""

    def _profile_has_skill(self, profile: Any, skill: str) -> bool:
        if not skill or skill == "general":
            return False
        wanted = str(skill).strip().lower()
        wanted_compact = re.sub(r"[^a-z0-9]+", "", wanted)
        for term in self._profile_skill_terms(profile):
            term_compact = re.sub(r"[^a-z0-9]+", "", term)
            if wanted == term or wanted_compact == term_compact:
                return True
            if wanted in {"api", "rest"} and ("api" in term or "rest" in term):
                return True
        return False

    def _extract_skill_candidate_from_question(self, question: str) -> str:
        """Extract the named skill from simple forms like 'experience in X'."""
        q = str(question or "").lower()
        patterns = [
            r"(?:experience|exp)\s+(?:in|with|on)\s+([a-z0-9+#. -]{2,40})",
            r"(?:knowledge|proficiency|expertise)\s+(?:in|with|on)\s+([a-z0-9+#. -]{2,40})",
            r"rate\s+your\s+([a-z0-9+#. -]{2,40})\s+(?:experience|skill|knowledge)",
        ]
        stop_phrases = {
            "years", "total", "relevant", "professional", "work",
            "it", "this", "the above", "software development"
        }
        for pattern in patterns:
            match = re.search(pattern, q)
            if not match:
                continue
            value = re.split(r"[?.,;:]", match.group(1).strip())[0].strip()
            value = re.sub(r"\b(years?|months?|please|required|mandatory)\b", "", value).strip()
            if value and value not in stop_phrases:
                return value
        return ""

    def _limit_lines(self, text: str, max_lines: int = 4) -> str:
        raw = (text or "").replace("\r", "\n").strip()
        if not raw:
            return ""
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        if not lines:
            lines = [raw]
        return "\n".join(lines[:max_lines])
    
    def _salary_answer(self, question: str) -> str:
        """Return salary answers that match fresher application expectations."""
        q = (question or "").lower()
        if any(x in q for x in ["current", "present", "last", "existing"]):
            return "180000"
        if any(x in q for x in ["expected", "expectation", "desired"]):
            return "As per company standards"
        return "As per company standards"

    def _project_answer(self, profile: Any) -> str:
        projects = getattr(profile, "projects", []) or []
        if projects:
            p = projects[0]
            name = p.get("name", "my main project")
            tech = ", ".join(p.get("tech", [])[:5])
            bullets = "; ".join(p.get("bullets", [])[:2])
            parts = [f"I worked on {name}"]
            if tech:
                parts.append(f"using {tech}")
            if bullets:
                parts.append(f"where I focused on {bullets}")
            return self._limit_lines(" ".join(parts) + ".", max_lines=3)

        raw_context = getattr(profile, "raw_resume_context", "")
        if raw_context:
            return self._limit_lines(raw_context, max_lines=3)

        skills = ", ".join(getattr(profile, "skills", [])[:5])
        return f"I have built academic and personal projects using {skills}, focusing on clean code, APIs, and practical problem solving."

    def _technical_answer_from_question(self, question: str) -> str:
        q = (question or "").lower()
        if "rest" in q and "api" in q:
            return (
                "A REST API is an HTTP-based interface where clients access resources through endpoints. "
                "It commonly uses methods like GET, POST, PUT, and DELETE, keeps requests stateless, "
                "and usually sends data as JSON."
            )
        if "api" in q:
            return (
                "An API is a contract that lets two software systems communicate. "
                "It defines available operations, inputs, outputs, and expected responses."
            )
        if "oops" in q or "object oriented" in q:
            return "OOP organizes code around objects and classes. The main concepts are encapsulation, inheritance, polymorphism, and abstraction."
        if "database" in q or "sql" in q or "mongodb" in q:
            return "A database stores and manages application data. SQL databases use structured tables, while MongoDB stores flexible JSON-like documents."
        return ""

    def _build_candidate_context(self, profile: Any) -> str:
        """Build fresher-specific context for LLM with full RAG-based resume details"""
        skills = ", ".join(profile.skills) if hasattr(profile, "skills") else "N/A"
        education = getattr(profile, "education", "B.Sc Computer Science")
        
        # Add experience details from raw_resume_context if available
        experience_details = ""
        raw_context = getattr(profile, "raw_resume_context", "")
        projects_text = ""
        
        # Get projects from profile
        projects = getattr(profile, "projects", [])
        if projects and len(projects) > 0:
            project_parts = []
            for p in projects[:3]:  # Limit to 3 projects
                proj_name = p.get('name', 'Project')
                proj_tech = ', '.join(p.get('tech', []))
                proj_bullets = p.get('bullets', [])[:2]  # Limit bullets
                project_parts.append(f"{proj_name} ({proj_tech}): {'; '.join(proj_bullets)}")
            projects_text = " | Projects: " + " | ".join(project_parts)
        
        if raw_context:
            lines = raw_context.split('\n')
            exp_lines = [l for l in lines if 'Experience:' in l or 'Intern' in l or 'Developer' in l]
            edu_lines = [l for l in lines if 'Education:' in l]
            if exp_lines:
                experience_details = " | ".join(exp_lines[:2])
            if edu_lines:
                education = " | ".join(edu_lines)
        
        base = (
            f"Fresher: Yes | "
            f"Current Salary: 180000 | "
            f"Notice Period: Immediate / 0 days | "
            f"Total Experience: 0 years | "
        )
        
        if experience_details:
            base += f"{experience_details} | "
        
        base += f"Skills: {skills} | Education: {education}"
        
        if projects_text:
            base += projects_text
        
        return base

    async def answer_questions_batch(
        self,
        questions_metadata: list[dict[str, Any]],
        profile: Any,
        job: dict[str, Any],
        context: str = ""
    ) -> dict[str, str]:
        """
        v3 Optimization: Process entire form page in a single LLM call.
        questions_metadata: [{"id": "...", "text": "...", "type": "...", "options": [...]}, ...]
        """
        if not questions_metadata:
            return {}

        self.logger.info(f"Turbo-Processing {len(questions_metadata)} questions in a single batch...")
        
        # Build Batch Prompt
        q_blocks = []
        for i, m in enumerate(questions_metadata):
            opt_str = f" | Options: {', '.join(m.get('options', []))}" if m.get('options') else ""
            q_blocks.append(f"Q{i}: {m['text']} (Type: {m['type']}{opt_str})")
        
        batch_text = "\n".join(q_blocks)
        
        prompt = (
            f"SYSTEM: You are a high-speed job application batch processor. Map Resume facts to the following questions.\n"
            f"STRICT RULES:\n"
            f"1. Return ONLY a valid JSON object where keys are the Qids (Q0, Q1, etc.) and values are the concise answers.\n"
            f"2. For radio/select types, the value MUST exactly match one of the provided Options.\n"
            f"3. Do NOT provide explanations. JSON ONLY.\n\n"
            f"QUESTIONS:\n{batch_text}\n\n"
            f"RESUME CONTEXT: {context[:4000]}\n"
            f"Candidate profile: {profile.name}, {', '.join(profile.skills)}\n"
        )
        
        raw_res = await self._ask_llm(prompt, max_tokens=1000)
        
        # Parse JSON Batch
        answers_map = {}
        try:
            # Simple extractor for json block
            match = re.search(r'\{.*\}', raw_res, re.DOTALL)
            if match:
                batch_res = json.loads(match.group(0))
                for i, m in enumerate(questions_metadata):
                    val = batch_res.get(f"Q{i}")
                    if val:
                        # Fuzzy match for options (safety)
                        if m.get('options') and m.get('type') in ("radio", "select", "dropdown"):
                            from utils.job_retrieval import fuzzy_match_option
                            val = fuzzy_match_option(val, m['options']) or m['options'][0]
                        answers_map[m['text']] = str(val)
        except Exception as e:
            self.logger.warning(f"Batch parse failed, falling back to serial: {e}")

        return answers_map

    async def _ask_llm(self, prompt: str, max_tokens: int) -> str | None:
        """Direct Groq API call using httpx to avoid openai dependency."""
        groq_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_LLM_ANSWERS")
        if not groq_key:
            self.logger.warning("No Groq API key found for chatbot answers")
            return None

        base_url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.1-8b-instant"
        
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You write concise, human-sounding, job-specific application answers for fresher candidates."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }

        try:
            async with httpx.AsyncClient() as client:
                for attempt in range(2):
                    try:
                        response = await client.post(base_url, headers=headers, json=payload, timeout=30.0)
                        if response.status_code == 200:
                            result = response.json()
                            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                            return content or None
                        elif response.status_code == 429:
                            await asyncio.sleep(2 * (attempt + 1))
                            continue
                        else:
                            self.logger.warning(f"Groq API Error: {response.status_code} - {response.text}")
                            break
                    except Exception as e:
                        if attempt == 0:
                            await asyncio.sleep(1)
                            continue
                        self.logger.warning(f"LLM request attempt {attempt+1} failed: {e}")
        except Exception as exc:
            self.logger.warning(f"Groq connection failed: {exc}")
        
        return None
