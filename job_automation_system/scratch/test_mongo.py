from pymongo import MongoClient

# SRV URI worked for DNS - just needs more time for primary election
uri = "mongodb+srv://kosurivenky:venkyyamuna@cluster0.uhbfag1.mongodb.net/ai_bot_resumes?appName=Cluster0"

print("Connecting with 15s timeout (cluster may be waking up)...")
client = MongoClient(uri, serverSelectionTimeoutMS=15000)

try:
    result = client.admin.command('ping')
    print(f"SUCCESS! Ping: {result}")
    
    db = client["ai_bot_resumes"]
    student = db.students.find_one({"student_id": "student_2b4359c4"})
    if student:
        print(f"Found student: {student.get('name', 'N/A')}")
    else:
        print("Student not found")
except Exception as e:
    print(f"FAILED: {e}")
finally:
    client.close()
