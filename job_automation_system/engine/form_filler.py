from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from utils.humanize import Humanizer

# Convenience aliases matching the original ai_job_auto_apply interface
human_type = Humanizer.human_type

async def random_delay(min_ms: int = 220, max_ms: int = 700) -> None:
    import random
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

from utils.job_retrieval import retrieve_field_relevant_chunks

class FormFiller:
    def __init__(self, logger: Any) -> None:
        self.logger = logger

    async def fill_application_form(
        self,
        page: Any,
        profile: Any,
        job: dict[str, Any],
        answers: dict[str, str],
        llm_answers: Any,
        analysis: dict[str, Any] | None = None,
        resume_path: str = ""
    ) -> dict[str, Any]:
        form_fields = page.locator(
            "input:not([type='hidden']):not([type='submit']), "
            "textarea, select, [role='combobox'], [role='radiogroup'], .jobs-easy-apply-form-section__grouping"
        )
        
        # v3 Universal Context strike: Fetch ALL resume facts once for accurate form filling
        from rag_engine.rag_engine import RAGEngine
        rag = RAGEngine()
        total_context = ""
        try:
            resume_p = resume_path or os.getenv("STUDENT_RESUME_PATH")
            if resume_p and os.path.exists(resume_p):
                from utils.pdf_reader import extract_text_from_pdf
                resume_text = extract_text_from_pdf(resume_p)
                rag.index_resume(resume_text)
                total_context_chunks = await rag.retrieve_all_chunks_async()
                total_context = "\n\n".join(total_context_chunks)
        except Exception: pass

        total = await form_fields.count()
        filled = 0

        for index in range(total):
            field = form_fields.nth(index)
            try:
                if not await field.is_visible(): continue
                if await field.is_disabled(): continue
            except Exception: continue

            try:
                tag = await field.evaluate("el => el.tagName.toLowerCase()")
                role = await field.get_attribute("role") or ""
                field_type = (await field.get_attribute("type") or "").lower()
            except Exception: tag = ""; role = ""; field_type = ""
            
            if field_type == "password": continue

            # Infer question text with climbing logic (v2 Precision)
            field_text = await self._infer_field_text(page, field)
            if not field_text: continue

            # Persistence Check (v3 Sensor): Do not overwrite existing details (Except for Resume Uploads)
            if "resume" not in field_text.lower() and "cv" not in field_text.lower():
                existing_val = await field.evaluate("el => el.value || el.innerText || ''")
                if existing_val.strip() and field_type != "file":
                    self.logger.log_info(f"Preserving pre-filled data in field: {existing_val.strip()[:20]}...")
                    filled += 1
                    continue

            # v3 Precision skip: Hand off all file/resume uploads to the specialized ResumeUploader
            # Only log if not already handled in this session to avoid redundant logging
            if field_type == "file" or "resume" in field_text.lower() or "cv" in field_text.lower():
                # Check if this field was already handled (avoid duplicate logging)
                already_handled = getattr(self, '_resume_fields_handled', set())
                if field_text[:30] not in already_handled:
                    self.logger.log_info(f"Skipping resume/file field in FormFiller for specialized Uploader strike: {field_text[:20]}...")
                    self._resume_fields_handled = already_handled | {field_text[:30]}
                continue

            # Capture options for Dropdowns and Radios
            options = []
            if tag == "select" or role == "combobox":
                if tag == "select":
                    options = await field.locator("option").all_inner_texts()
                else:
                    options = [] 

            elif field_type == "radio" or role == "radiogroup":
                options = await field.locator("label, .fb-radio__label").all_inner_texts()

            value = await self._value_for_field(
                field_text=field_text,
                field_type=field_type or role or tag,
                tag=tag,
                profile=profile,
                job=job,
                answers=answers,
                llm_answers=llm_answers,
            analysis=analysis,
            options=[o.strip() for o in options if o.strip()],
            context=total_context or getattr(profile, "raw_resume_context", "")
        )
            
            if value is None: continue

            try:
                await field.scroll_into_view_if_needed()
                await random_delay(150, 400)

                # HANDLE RADIOS
                if field_type == "radio" or role == "radiogroup":
                    labels = field.locator("label, .fb-radio__label")
                    l_count = await labels.count()
                    for l_idx in range(l_count):
                        lbl = labels.nth(l_idx)
                        txt = (await lbl.inner_text()).strip().lower()
                        target = value.lower().strip()
                        if target == txt or target in txt or txt in target or \
                           (target == "yes" and any(w in txt for w in ["yes", "agree", "true", "confirm"])) or \
                           (target == "no" and any(w in txt for w in ["no", "disagree", "false", "decline"])):
                            await lbl.click()
                            filled += 1; break
                    continue

                # HANDLE CHECKBOXES
                if field_type == "checkbox":
                    desired = value.strip().lower() in {"yes", "true", "1", "check"}
                    if desired != await field.is_checked():
                        await field.click()
                    filled += 1; continue

                # HANDLE DROPDOWNS (Select & Combobox)
                if tag == "select" or role == "combobox" or "select" in field_text.lower():
                    # v3 Forced-Click Strike: Click to reveal options for custom LinkedIn dropdowns
                    try:
                        await field.click(force=True)
                        await asyncio.sleep(0.8) # Wait for Artdeco animations
                    except Exception: pass
                    
                    if await self._select_option(page, field, value):
                        filled += 1
                    continue

                # HANDLE INPUTS & TEXTAREAS
                await human_type(field, value)
                
                # v3 SELF-CORRECTION STRIKE: Detect and fix LinkedIn/Naukri validation errors
                # If the platform shows a red error like "Enter a decimal number", we force a numeric retry.
                await asyncio.sleep(2.5) 
                
                # Check for error message in the immediate container of this field
                try:
                    container = field.locator("xpath=ancestor::div[contains(@class, 'fb-dash-form-element') or contains(@class, 'artdeco-text-input') or contains(@class, 'jobs-easy-apply-form-section__grouping')][1]")
                    if await container.count() > 0:
                        error_msg_loc = container.locator(".artdeco-inline-feedback--error, .artdeco-inline-feedback__message, .fb-dash-form-element__error-field")
                        if await error_msg_loc.count() > 0 and await error_msg_loc.first.is_visible():
                            e_text = (await error_msg_loc.first.inner_text()).lower()
                            if any(w in e_text for w in ["number", "decimal", "digit", "larger than", "valid value", "numeric"]):
                                self.logger.log_warn(f"[SELF-CORRECTION] Numeric error on '{field_text[:20]}': {e_text}. Retrying with digits.")
                                
                                # Extract digits from the original value or default to 1
                                import re
                                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str(value))
                                numeric_fix = numbers[-1] if numbers else "1"
                                
                                # Clear and re-type
                                await field.click(click_count=3)
                                await field.press("Control+A")
                                await field.press("Backspace")
                                await human_type(field, numeric_fix)
                                await asyncio.sleep(1)
                except Exception: pass
                
                filled += 1
            except Exception as e:
                self.logger.log_warn(f"Field fill error: {e}")
                continue

        return {"fields_detected": total, "fields_filled": filled}

    async def _infer_field_text(self, page: Any, field: Any) -> str:
        """Precision deep-climbing logic to find the question associated with a field."""
        try:
            for attr in ["aria-label", "placeholder", "data-testid", "name"]:
                val = await field.get_attribute(attr)
                if val: return val.strip()

            identifier = await field.get_attribute("id")
            if identifier:
                lbl = page.locator(f"label[for='{identifier}']")
                if await lbl.count() > 0:
                    return (await lbl.first.inner_text()).strip()

            # v3 Deep Climb: Move up multiple layers to find the grouping header or legend
            question = await field.evaluate("""el => {
                const group = el.closest('.jobs-easy-apply-form-section__grouping, .fb-dash-form-element, .fb-form-element');
                if (!group) return el.placeholder || '';
                // v3: Prioritize legends and titles for multi-option groups
                const header = group.querySelector('legend, .fb-dash-form-element__label, .fb-dash-form-element__title, .jobs-easy-apply-form-element__label');
                const label = group.querySelector('label');
                return (header ? header.innerText : (label ? label.innerText : '')) + (el.placeholder ? ' ' + el.placeholder : '');
            }""")
            return question.strip()
        except Exception:
            return ""

    async def _value_for_field(self, **kwargs) -> str | None:
        """Logic to decide the value for a field (HyDE RAG + Profile Identifiers)."""
        field = kwargs['field_text'].lower()
        profile = kwargs['profile']
        total_context = kwargs.get('context', "")
        
        # --- ABSOLUTE RESUME IDENTITY (No .env / No Hardcoding) ---
        real_name = profile.name
        real_phone = profile.phone

        if "name" in field and "company" not in field:
            # If still 'Candidate' (default), perform a targeted RAG strike
            if not real_name or real_name == "Candidate":
                res = await self._value_for_field(field_text="What is the full name of the candidate in the resume?", **kwargs)
                if res and "N/A" not in res: real_name = res
            return real_name or "Candidate"
        
        if ("phone" in field or "mobile" in field or "contact" in field) and not any(x in field for x in ["emergency", "reference", "relativ"]):
            # If still default or missing, perform a targeted RAG strike
            if not real_phone or "000000" in real_phone:
                res = await self._value_for_field(field_text="What is the phone number of the candidate in the resume?", **kwargs)
                if res and "N/A" not in res: real_phone = res
            return real_phone or ""
        if "email" in field:
            # Targeted RAG Strike if missing or generic
            if not profile.email or "Unknown" in profile.email or "placeholder" in profile.email:
                res = await self._value_for_field(field_text="What is the email address of the candidate in the resume?", **kwargs)
                if res and "@" in res: profile.email = res
            return profile.email
        if ("phone" in field or "mobile" in field or "contact" in field) and not any(x in field for x in ["emergency", "reference", "relativ"]):
            return real_phone
        if ("location" in field or "city" in field or "reside" in field) and "relocat" not in field:
            return profile.location
        if "linkedin" in field:
             return str(profile.extra.get("linkedin", ""))
        if "github" in field:
            return str(profile.extra.get("github", ""))
        if "portfolio" in field or "website" in field:
            return str(profile.extra.get("portfolio", ""))

        # --- DYNAMIC AI PATH (HyDE RAG) ---
        # v3 ENHANCEMENT: Use total_context as the primary base for zero-hallucination
        field_context = total_context or profile.raw_resume_context
        if not field_context:
            try:
                from rag_engine.rag_engine import RAGEngine
                rag = RAGEngine()
                chunks = await rag.retrieve_with_hyde_async(kwargs['field_text'])
                field_context = "\n".join(chunks) if chunks else profile.raw_resume_context
            except Exception:
                field_context = profile.raw_resume_context

        res_dict = await kwargs['llm_answers'].answer_question(
            question=kwargs['field_text'],
            profile=profile,
            job=kwargs['job'],
            analysis=kwargs['analysis'],
            context=field_context,
            field_type=kwargs['field_type'],
            options=kwargs['options']
        )
        
        # Extract plain string answer for compatibility
        res = res_dict.get("answer", "0") if isinstance(res_dict, dict) else str(res_dict)
        
        # v3 Numeric/Decimal Sanitizer Strike: Force return only numbers for specific LinkedIn requirements
        num_keywords = ["how many", "years", "months", "additional", "total", "ctc", "salary", "notice", "expectation", "decimal", "number"]
        if any(x in kwargs['field_text'].lower() for x in num_keywords):
            import re
            # Precision: Find decimals (8.5) and integers (12)
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str(res))
            if numbers:
                # v3 Preference: If a range is given (e.g. 8-12), pick the most professional answer (usually max)
                return numbers[-1]
            
            # v3 Last-Mile Fallback: If no number found but field is IMPORTANT (salary/ctc), return reasonable default in rupees
            if any(x in kwargs['field_text'].lower() for x in ["ctc", "salary", "expected"]):
                # Check expected vs current based on field name
                field_lower = kwargs['field_text'].lower()
                if "current" in field_lower or "present" in field_lower:
                    return "180000"
                else:
                    return "350000"
            
            # v3 Fallback Strike: If no number found but answer is 'immediate' or 'no', return '0'
            if any(x in str(res).lower() for x in ["immediate", "no", "n/a", "none"]):
                return "0"

        # v3 Commuting Force: Map location responses or comfort statements to 'Yes'
        if any(x in kwargs['field_text'].lower() for x in ["commuting", "location", "travel", "comfort"]):
            lowered_res = str(res).lower()
            if any(x in lowered_res for x in ["yes", "comfortable", "available", "agree", "willing"]) or \
               (profile.location.lower() in lowered_res):
                return "Yes"

        return res

    async def _select_option(self, page: Any, field: Any, value: str) -> bool:
        """Handles both standard selects and modern LinkedIn custom dropdowns."""
        try:
            tag = await field.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                await field.select_option(label=value)
                return True
            
            # v3 Precision Search: Look for the newly opened menu options
            desired = value.lower().strip()
            # Common LinkedIn dropdown item selectors
            selectors = [
                "[role='listbox'] [role='option']",
                ".artdeco-dropdown__item",
                "[role='menuitem']",
                ".fb-dash-form-element__dropdown-item"
            ]

            for selector in selectors:
                options = page.locator(selector)
                count = await options.count()
                for i in range(count):
                    opt = options.nth(i)
                    if await opt.is_visible():
                        txt = (await opt.inner_text()).lower().strip()
                        if desired == txt or desired in txt or txt in desired:
                            await opt.click(force=True)
                            return True
            
            # Fallback: search by text globally if modal is stubborn
            fallback = page.get_by_text(value).last
            if await fallback.count() > 0 and await fallback.is_visible():
                await fallback.click(force=True)
                return True

        except Exception as e:
            self.logger.log_warn(f"Select option failed: {e}")
        return False
