import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test ID
TEST_STUDENT_ID = "test_warmup_123"

async def test_warmup():
    print(f"\nTESTING WARMUP PIPELINE FOR: {TEST_STUDENT_ID}")
    
    # 1. Run the warmup script (using subprocess or direct import)
    from scripts.warmup_student import warmup_student
    
    try:
        success = await warmup_student(TEST_STUDENT_ID)
        
        if success:
            print(f"\n[OK] PIPELINE COMPLETED SUCCESSFULLY")
            
            # 2. Check MongoDB
            from utils.student_mongodb import get_student_by_id
            student = get_student_by_id(TEST_STUDENT_ID)
            
            if student and (student.get("skills") or student.get("categorized_skills")):
                print(f"[OK] MONGODB SYNC VERIFIED")
                print(f"  - Extracted Role: {student.get('primary_role')}")
                print(f"  - Extracted Email: {student.get('email')}")
            else:
                print("[ERROR] MONGODB SYNC FAILED: Skills not found in record.")

            # 3. Check Files
            from rag_engine.rag_resume_generator import RESUMES_DIR
            dist_dir = RESUMES_DIR / TEST_STUDENT_ID
            files = list(dist_dir.glob("*.pdf"))
            
            if len(files) >= 5:
                print(f"[OK] FILE GENERATION VERIFIED: {len(files)} role PDFs created.")
                for f in files:
                    print(f"  - Generated: {f.name}")
            else:
                print(f"[ERROR] FILE GENERATION FAILED: Only {len(files)} files found.")
                
        else:
            print("\n❌ PIPELINE EXECUTION FAILED.")
            
    except Exception as e:
        print(f"\n❌ ERROR DURING TEST: {e}")

if __name__ == "__main__":
    asyncio.run(test_warmup())
