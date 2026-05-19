import os
import sys
import json
import re
import traceback

# 0. Global Startup Diagnostic
print("DIAGNOSTIC: Python Process Started", file=sys.stderr)

try:
    from crewai import Agent, Task, Crew, Process
    from langchain_groq import ChatGroq
    print("DIAGNOSTIC: Imports Successful", file=sys.stderr)
except Exception as e:
    print(f"DIAGNOSTIC: IMPORT ERROR: {str(e)}\n{traceback.format_exc()}", file=sys.stderr)
    sys.exit(1)

def main():
    print("DIAGNOSTIC: Entering main()", file=sys.stderr)
    
    # 1. Read input from stdin
    try:
        input_data = sys.stdin.read()
        print(f"DIAGNOSTIC: Stdin received length {len(input_data)}", file=sys.stderr)
        
        data = json.loads(input_data if input_data else "{}")
        job_description = data.get("jobDescription", "TEST JD")
        retrieved_chunks = data.get("retrievedChunks", "TEST CHUNKS")
    except Exception as e:
        print(f"DIAGNOSTIC: STDIN ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # 2. API Key setup
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("DIAGNOSTIC: ERROR: GROQ_API_KEY is missing", file=sys.stderr)
        sys.exit(1)

    try:
        # Initialize LLM
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, groq_api_key=api_key)
        
        # Define Agents
        bot = Agent(
            role='Tailored Resume Specialist',
            goal='Generate a resume and compute an ATS score.',
            backstory='Professional recruiter.',
            verbose=True,
            llm=llm
        )

        task = Task(
            description=f"Generate a tailored resume and score for: {job_description}\n\nUsing chunks: {retrieved_chunks}\n\nOutput ONLY a JSON block with decision, score, resumeText, matchedSkills, missingSkills.",
            expected_output="JSON data pack.",
            agent=bot
        )

        crew = Crew(agents=[bot], tasks=[task], verbose=True)
        
        print("DIAGNOSTIC: Kicking off Crew...", file=sys.stderr)
        result = crew.kickoff()
        print("DIAGNOSTIC: Kickoff Complete", file=sys.stderr)

        # Manual Extraction
        raw = str(result.raw)
        data_block = re.search(r'\{.*\}', raw, re.DOTALL)
        if data_block:
            # Output to STDOUT for Node.js
            print(data_block.group(0))
        else:
            print(json.dumps({"success": False, "error": "No JSON found in response"}))

    except Exception as e:
        print(f"DIAGNOSTIC: RUNTIME ERROR: {str(e)}\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
