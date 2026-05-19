import os
import sys
from dotenv import load_dotenv

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), '../../.env')
load_dotenv(env_path)

# Keys from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_groq import ChatGroq
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    from pydantic import BaseModel, Field
    import json

    job_description = "Looking for a Senior Python Developer with 5 years of experience in Django and REST APIs."

    resume_text = """
    John Doe - Senior Python Developer
    Experience: 6 years in web development using Python, Django, and Flask.
    Built multiple REST APIs and integrated PostgreSQL databases.
    Skills: Python, Django, Flask, REST API, PostgreSQL, Git, Docker
    Education: BSc Computer Science, 2017
    """

    print("Step 1: Chunking resume text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(resume_text)
    print(f"  -> {len(chunks)} chunk(s) created")

    print("Step 2: Creating Gemini embeddings + FAISS store...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = FAISS.from_texts(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    print("  -> FAISS vector store ready")

    print("Step 3: [HYDE] Generating hypothetical candidate with Groq llama-3.1-8b-instant...")
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)
    hyde_prompt = PromptTemplate.from_template(
        "You are an expert HR recruiter. Write a detailed hypothetical candidate resume "
        "that would be the perfect fit for the following job description. "
        "Keep it realistic, concise and focused on skills, experiences, and qualifications.\n\n"
        "Job Description:\n{job_description}"
    )
    hyde_chain = hyde_prompt | llm
    hyde_result = hyde_chain.invoke({"job_description": job_description})
    hypothetical_candidate_text = hyde_result.content
    print(f"  -> HYDE text generated ({len(hypothetical_candidate_text)} chars)")

    print("Step 4: Retrieving relevant resume chunks using HYDE embedding...")
    retrieved_docs = retriever.invoke(hypothetical_candidate_text)
    retrieved_text = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
    print(f"  -> Retrieved {len(retrieved_docs)} chunk(s)")

    print("Step 5: Evaluating match with Groq llama-3.1-8b-instant (ONLY from context)...")

    class MatchResult(BaseModel):
        match_score: int = Field(description="Match score from 0 to 100")
        matched_skills: list[str] = Field(description="List of skills that matched")
        missing_skills: list[str] = Field(description="List of skills missing from resume context")
        reason: str = Field(description="Short reason for the score (max 2 sentences)")

    parser = JsonOutputParser(pydantic_object=MatchResult)
    eval_prompt = PromptTemplate(
        template="You are an expert recruiter evaluating a resume for a job description.\n"
                 "Compare ONLY against the retrieved resume context chunks below.\n"
                 "RULES:\n"
                 "- Use ONLY the retrieved chunks as context for the candidate's resume data.\n"
                 "- DO NOT use outside knowledge about the candidate.\n"
                 "- Keep the output concise and strictly formatted.\n\n"
                 "Job Description:\n{job_description}\n\n"
                 "Retrieved Resume Context (Use ONLY this):\n{resume_context}\n\n{format_instructions}",
        input_variables=["job_description", "resume_context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    eval_chain = eval_prompt | llm | parser
    final_result = eval_chain.invoke({
        "job_description": job_description,
        "resume_context": retrieved_text
    })

    print("\n✅ Pipeline COMPLETE! Final Result:")
    print(json.dumps(final_result, indent=2))

except Exception as e:
    import traceback
    print(f"\n❌ Error: {e}")
    traceback.print_exc()
