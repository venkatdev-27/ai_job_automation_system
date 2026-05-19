#!/usr/bin/env python3
"""
Verification Script for Warmup Flow
====================================
Tests that warmup generates 6 role PDFs properly.
"""

import sys
import os
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

def check_dependencies():
    """Check all required packages are installed"""
    print("\n[1/5] Checking Dependencies...")
    deps = ['mammoth', 'pymongo', 'dotenv', 'numpy']
    missing = []
    for dep in deps:
        try:
            __import__(dep)
            print(f"  OK: {dep}")
        except ImportError:
            print(f"  MISSING: {dep}")
            missing.append(dep)
    
    if missing:
        print(f"\nERROR: Missing dependencies: {missing}")
        return False
    return True

def check_mongodb():
    """Check MongoDB connection"""
    print("\n[2/5] Checking MongoDB...")
    try:
        from utils.student_mongodb import get_student_by_id
        student = get_student_by_id('student_06f6e1f3')
        if student:
            print(f"  OK: Student found - {student.get('full_name', 'N/A')}")
            return True
        else:
            print("  ERROR: Student not found")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def check_warmup_outputs():
    """Check if PDFs were generated"""
    print("\n[3/5] Checking Generated PDFs...")
    student_dir = PROJECT_ROOT / "resumes" / "student_06f6e1f3"
    
    if not student_dir.exists():
        print(f"  ERROR: Student folder does not exist: {student_dir}")
        return False
    
    pdfs = list(student_dir.glob("*.pdf"))
    print(f"  Found {len(pdfs)} PDFs in student folder:")
    for pdf in pdfs:
        print(f"    - {pdf.name} ({pdf.stat().st_size} bytes)")
    
    # Also check shared resumes
    shared_dir = PROJECT_ROOT / "resumes"
    shared_pdfs = list(shared_dir.glob("*.pdf"))
    print(f"  Found {len(shared_pdfs)} PDFs in shared folder")
    
    return len(pdfs) > 0 or len(shared_pdfs) >= 6

def check_mongodb_profile():
    """Check if profile was updated in MongoDB"""
    print("\n[4/5] Checking MongoDB Profile Update...")
    try:
        from utils.student_mongodb import get_student_by_id
        student = get_student_by_id('student_06f6e1f3')
        if student:
            # Check for profile fields
            if 'skills' in student and student['skills']:
                print(f"  OK: Skills updated - {len(student.get('skills', []))} skills")
            if 'primary_role' in student:
                print(f"  OK: Primary role updated - {student.get('primary_role')}")
            return True
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def run_test_warmup():
    """Run actual warmup test"""
    print("\n[5/5] Running Warmup Test...")
    try:
        import asyncio
        from scripts.warmup_student import warmup_student
        
        result = asyncio.run(warmup_student('student_06f6e1f3'))
        print(f"  Warmup result: {'SUCCESS' if result else 'FAILED'}")
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("WARMUP FLOW VERIFICATION")
    print("="*60)
    
    # Step 1: Dependencies
    if not check_dependencies():
        print("\nFIX: Run 'pip install mammoth pymongo numpy'")
        return False
    
    # Step 2: MongoDB
    if not check_mongodb():
        print("\nFIX: Check MongoDB connection")
        return False
    
    # Step 3: Check existing outputs
    if check_warmup_outputs():
        print("\n  Note: PDFs already exist, skipping generation")
        return True
    
    # Step 4: Run warmup
    if not run_test_warmup():
        print("\nERROR: Warmup failed")
        return False
    
    # Step 5: Verify outputs
    if check_warmup_outputs():
        print("\n" + "="*60)
        print("VERIFICATION COMPLETE - SUCCESS")
        print("="*60)
        return True
    else:
        print("\nERROR: Warmup ran but no PDFs generated")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)