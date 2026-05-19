import os
import re

path = r'd:\ai-bot-resumes\job_automation_system\scraper_adapter\naukri.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match the platform="naukri" and add student_id
pattern = r'(platform="naukri")(\s*\n\s*)(\))'
replacement = r'\1, student_id=self._get_candidate_id(profile)\2\3'

new_content = re.sub(pattern, replacement, content)

if new_content != content:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print("Successfully patched naukri.py")
else:
    print("Could not find pattern in naukri.py")
