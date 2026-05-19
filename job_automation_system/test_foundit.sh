curl -X POST 'http://localhost:5001/api/automation/run' \
  -H 'Content-Type: application/json' \
  -d '{"platforms": ["foundit"], "jobs_per_student": 2, "student_ids": ["student_4443c80f"]}'