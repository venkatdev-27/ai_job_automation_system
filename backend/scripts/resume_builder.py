import os
import sys
import json
import re
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    try:
        data = json.loads(input_data)
        job_description = data.get("jobDescription")
        retrieved_chunks = data.get("retrievedChunks")
    except Exception as e:
        print(json.dumps({"error": f"Invalid input format: {str(e)}"}))
        sys.exit(1)
        
    if not job_description or not retrieved_chunks:
        print(json.dumps({"error": "Missing job description or retrieved chunks"}))
        sys.exit(1)

    # API Keys are injected via environment variables from Node.js
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        print(json.dumps({"error": "GROQ_API_KEY not found in environment."}))
        sys.exit(1)

    try:
        # Initialize the LLM (Production Level: Llama-3.1-8b-instant as requested)
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2, groq_api_key=groq_api_key)

        # Phase 1: Generate Optimized Resume
        resume_prompt = PromptTemplate.from_template("""
        You are a professional ATS resume writer and recruiter.

        Your task is to generate a ONE-PAGE, ATS-optimized resume tailored to the given job description.

        -------------------------------
        STRICT RULES (MUST FOLLOW)
        -------------------------------
        - Use ONLY the provided resume data (NO fake or assumed information)
        - Do NOT add new experience, projects, or skills
        - Preserve personal details exactly (name, phone, email, LinkedIn)
        - Keep resume strictly ONE PAGE
        - Use simple plain text (NO tables, NO icons, NO special formatting)
        - Use strong action verbs (Developed, Built, Implemented, Optimized)
        - Ensure minimum 3 bullet points per Experience and per Project
        - Prioritize job-relevant content only

        -------------------------------
        STRUCTURE (STRICT ORDER)
        -------------------------------
        Name:
        Contact:

        Summary:
        - 2–3 lines tailored to the job role
        - Include key job keywords naturally

        Skills:
        - Only include relevant skills from job description
        - Avoid unrelated skills

        Education:
        - Degree, institution, year

        Experience / Internships:
        For each role:
        - Minimum 3 bullet points
        - Focus on impact, technologies, and results
        - Align with job description

        Projects:
        For each project:
        - Minimum 3 bullet points
        - Mention technologies used
        - Highlight relevant work

        Achievements:
        - Include measurable or relevant achievements (if available)

        Extra-Curricular Activities:
        - Include only relevant activities

        -------------------------------
        INPUT DATA
        -------------------------------
        Resume Data:
        {retrieved_chunks}

        Job Description:
        {job_description}
        """)

        resume_chain = resume_prompt | llm
        resume_result = resume_chain.invoke({
            "retrieved_chunks": retrieved_chunks,
            "job_description": job_description
        })
        generated_resume = resume_result.content

        # Phase 2: Keyword Extraction from JD
        keyword_prompt = PromptTemplate.from_template("""
        You are an expert ATS engineer. 
        Extract a list of the most important technical keywords (skills, tools, platforms, technologies) from the following Job Description.
        - Ignore common stopwords (the, and, for, etc.).
        - Focus on industry-specific nouns and phrases (e.g., 'React', 'Python', 'AWS', 'TensorFlow', 'CI/CD').
        - Limit the output to a maximum of 15 unique keywords.
        - Output strictly in JSON format.

        Job Description:
        {job_description}

        Format:
        {{ "keywords": ["keyword1", "keyword2", ...] }}
        """)
        
        keyword_chain = keyword_prompt | llm | JsonOutputParser()
        keyword_result = keyword_chain.invoke({"job_description": job_description})
        extracted_keywords = keyword_result.get("keywords", [])

        # Phase 3: Matching & Scoring (Local Logic)
        matched_skills = []
        missing_skills = []
        
        # Use simple regex for case-insensitive keyword matching
        for kw in extracted_keywords:
            pattern = re.compile(re.escape(kw), re.IGNORECASE)
            if pattern.search(generated_resume):
                matched_skills.append(kw)
            else:
                missing_skills.append(kw)

        # Calculate Score
        total_count = len(extracted_keywords)
        if total_count > 0:
            score = int((len(matched_skills) / total_count) * 100)
        else:
            score = 0
            
        # Decision Logic
        decision = "APPLY" if score >= 80 else "SKIP"

        # Final Strict JSON Output
        output = {
            "resumeText": generated_resume,
            "score": score,
            "matchedSkills": matched_skills[:10],
            "missingSkills": missing_skills[:10],
            "decision": decision
        }

        print(json.dumps(output))

    except Exception as e:
        print(json.dumps({"error": f"Evaluation pipeline failed: {str(e)}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
