import sys
import os
import json
import fitz
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

# Ensure UTF-8 output for Windows console stability
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Pass GROQ_API_KEY and GOOGLE_API_KEY (for embeddings) from env
_groq_key = os.environ.get("GROQ_API_KEY", "")
_google_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
if _google_key:
    os.environ["GOOGLE_API_KEY"] = _google_key

def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join([page.get_text("text") for page in doc])
        doc.close()
        return text
    except Exception as e:
        raise Exception(f"Failed to read PDF {pdf_path}: {str(e)}")

def main():
    # Read from Stdin
    input_data = sys.stdin.read()
    try:
        data = json.loads(input_data)
        job_description = data.get("jobDescription")
        resume_source = data.get("resumePath")
        resume_text = data.get("resumeText")
    except Exception as e:
        print(f"===JSON_START==={json.dumps({'success': False, 'error': f'Invalid input format: {str(e)}'})}===JSON_END===")
        sys.exit(1)
        
    if not job_description:
        print(f"===JSON_START==={json.dumps({'success': False, 'error': 'Missing job description'})}===JSON_END===")
        sys.exit(1)

    if resume_source:
        try:
            resume_text = extract_text_from_pdf(resume_source)
        except Exception as e:
            print(f"===JSON_START==={json.dumps({'success': False, 'error': str(e)})}===JSON_END===")
            sys.exit(1)
            
    if not resume_text:
        print(f"===JSON_START==={json.dumps({'success': False, 'error': 'Missing resume text or resume path'})}===JSON_END===")
        sys.exit(1)

    try:
        # 1. Chunk resume text
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(resume_text)
        
        # 2. Embed chunks into vector DB
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vectorstore = FAISS.from_texts(chunks, embeddings)
        
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, groq_api_key=_groq_key)

        # 3. Generate HYDE text
        hyde_prompt = PromptTemplate.from_template(
            "You are an expert HR recruiter. Write a short hypothetical candidate resume "
            "that would be the perfect fit for the following job description. "
            "Focus strictly on skills and experience.\n\n"
            "Job Description:\n{job_description}"
        )
        hyde_chain = hyde_prompt | llm
        hyde_result = hyde_chain.invoke({"job_description": job_description})
        hypothetical_candidate_text = hyde_result.content

        # 4. Fetch relevant chunks using HYDE text
        retrieved_docs = retriever.invoke(hypothetical_candidate_text)
        retrieved_text = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])

        # 5 & 6. Evaluate context against Job Description
        class MatchResult(BaseModel):
            match_score: int = Field(description="Match score from 0 to 100")
            matched_skills: list[str] = Field(description="List of skills that matched")
            missing_skills: list[str] = Field(description="List of skills missing from resume context")
            reason: str = Field(description="Short reason for the score limit (max 2 sentences)")

        parser = JsonOutputParser(pydantic_object=MatchResult)
        eval_prompt = PromptTemplate(
            template="Compare the candidate's resume data against the job description.\n"
                     "Use ONLY the retrieved chunks as context.\n"
                     "Must exactly return the requested JSON format.\n\n"
                     "Job Description:\n{job_description}\n\n"
                     "Retrieved Resume Context:\n{resume_context}\n\n{format_instructions}",
            input_variables=["job_description", "resume_context"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        
        eval_chain = eval_prompt | llm | parser
        final_result = eval_chain.invoke({
            "job_description": job_description,
            "resume_context": retrieved_text
        })
        
        # DEFINITIVE MARKERS: Wrap JSON in unique markers to bypass stdout noise
        print(f"===JSON_START==={json.dumps({'success': True, 'data': final_result})}===JSON_END===")

    except Exception as e:
        import traceback
        err_msg = f"Evaluation pipeline failed: {str(e)}\n{traceback.format_exc()}"
        print(f"===JSON_START==={json.dumps({'success': False, 'error': err_msg})}===JSON_END===")
        sys.exit(1)

if __name__ == "__main__":
    main()
