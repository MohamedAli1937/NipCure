from typing import Any
from .schemas import PatientProfile


SYSTEM_PROMPT = """You are Gemma 3, a clinical healthcare assistant supporting elderly patients.

PRIMARY SOURCE RULE:
The MEDICAL REPORT is the primary and sole source for all clinical facts.
Extract only facts explicitly present in the report: diagnoses, medicines, dosages, frequencies, warnings, follow-up, and doctor instructions.

CRITICAL SAFETY RULES:
1. NEVER INVENT MEDICAL FACTS: Do not invent or fabricate diagnoses, medicines, dosages, or instructions.
2. DO NOT OVERRIDE DOCTOR INSTRUCTIONS: The doctor's orders are strictly authoritative.
3. IF UNCLEAR OR MISSING: If any instruction, follow-up, or dosage is unclear or missing in the report, return "Needs verification".
4. SHORT AND CLEAR: Keep all language simple, respectful, and easy for an older adult to understand.
5. GROUNDING & SOURCES: Every recommendation must cite the exact text or section from the report in the "sources" list.

OUTPUT FORMAT:
Respond with ONLY a valid JSON object matching this exact schema:
{
  "summary": "Short 2-3 sentence overview written warmly for an older adult.",
  "medicines": ["Medicine Name + Dosage + Timing (strictly as stated in report)"],
  "what_to_do": ["Clear daily actions prescribed by the doctor in the report"],
  "what_to_avoid": ["Actions, foods, or habits the doctor explicitly advised avoiding"],
  "food_guidance": ["Dietary instructions explicitly stated by the doctor in the report"],
  "warnings": ["Urgent red-flags or critical precautions from the report"],
  "follow_up": ["Follow-up appointments or 'Needs verification' if date is unclear"],
  "doctor_questions": ["Helpful questions to ask the doctor at the next visit"],
  "sources": ["Quotes or sections from the report supporting these recommendations"]
}
"""


def build_report_only_prompt(report_text: str) -> str:
    """Build the primary extraction prompt containing strictly the medical report text."""
    cleaned_report = report_text.strip() if report_text else "No report text provided."
    return f"""MEDICAL REPORT TEXT:
\"\"\"
{cleaned_report}
\"\"\"

INSTRUCTIONS:
Extract the medical care plan based ONLY on the facts explicitly present in the medical report above.
Do not invent or assume any medications, dosages, or diagnoses.
If any critical instruction or follow-up is unclear, output "Needs verification".
Return ONLY valid JSON matching the specified schema.
"""


def build_user_prompt(report_text: str, profile: PatientProfile | dict[str, Any] | None) -> str:
    """Legacy/dual prompt builder for medical report and patient profile."""
    if isinstance(profile, dict):
        profile_obj = PatientProfile(**profile)
    elif isinstance(profile, PatientProfile):
        profile_obj = profile
    else:
        profile_obj = PatientProfile()

    profile_lines = []
    if profile_obj.age:
        profile_lines.append(f"- Age: {profile_obj.age}")
    if profile_obj.allergies:
        profile_lines.append(f"- Known Allergies: {profile_obj.allergies}")
    if profile_obj.dietary_restrictions:
        profile_lines.append(f"- Dietary Restrictions: {profile_obj.dietary_restrictions}")
    if profile_obj.food_likes:
        profile_lines.append(f"- Foods They Like: {profile_obj.food_likes}")
    if profile_obj.food_dislikes:
        profile_lines.append(f"- Foods They Dislike: {profile_obj.food_dislikes}")
    if profile_obj.notes:
        profile_lines.append(f"- Other Patient Notes: {profile_obj.notes}")

    profile_text = "\n".join(profile_lines) if profile_lines else "None recorded."
    cleaned_report = report_text.strip() if report_text else "No report text provided."

    return f"""PATIENT PROFILE (Secondary context):
{profile_text}

MEDICAL REPORT TEXT (Primary source of truth):
\"\"\"
{cleaned_report}
\"\"\"

INSTRUCTIONS:
Extract the primary care plan strictly from the medical report.
Return ONLY valid JSON matching the specified schema.
"""
