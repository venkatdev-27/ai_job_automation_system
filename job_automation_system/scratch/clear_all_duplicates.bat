@echo off
REM Clear all idempotency keys via Python
cd /d D:\ai-bot-resumes\job_automation_system
python -c "from services.idempotency_v2 import clear_all_duplicates; print(f'Cleared: {clear_all_duplicates()} keys')"
echo.
echo Done!