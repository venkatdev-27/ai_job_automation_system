import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.credentials import get_student_credentials

def reveal_creds():
    student_id = "student_4443c80f"
    creds = get_student_credentials(student_id)
    print(f"Credentials for {student_id}: {creds}")

if __name__ == "__main__":
    reveal_creds()
