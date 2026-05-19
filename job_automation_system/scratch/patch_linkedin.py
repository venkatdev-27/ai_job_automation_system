import os

file_path = r'd:\ai-bot-resumes\job_automation_system\scraper_adapter\linkedin.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Fix the wait_for_selector state
    if 'await page.wait_for_selector(selector, state="visible", timeout=10000)' in line:
        line = line.replace('state="visible"', 'state="attached"')
    
    # Fix the fill method to handle hidden fields
    if 'await page.locator(selector).first.fill(email)' in line:
        indent = line[:line.find('await')]
        line = f"{indent}try:\n{indent}    await page.locator(selector).first.fill(email, timeout=5000)\n{indent}except:\n{indent}    await page.locator(selector).first.evaluate('(el, val) => el.value = val', email)\n"
    
    # Fix password visibility check
    if 'await loc.count() > 0 and await loc.first.is_visible():' in line:
        indent = line[:line.find('if')]
        line = f"{indent}if await loc.count() > 0:\n"
    
    # Add JS fallback for password fill
    if 'await loc.first.fill(password)' in line:
        indent = line[:line.find('await')]
        line = f"{indent}try:\n{indent}    await loc.first.fill(password, timeout=5000)\n{indent}except:\n{indent}    await loc.first.evaluate('(el, val) => el.value = val', password)\n"

    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("File updated successfully.")
