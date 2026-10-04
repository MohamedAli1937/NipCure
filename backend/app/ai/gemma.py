import json
import logging
import os
import re
from typing import Any

import httpx

from .prompts import SYSTEM_PROMPT, build_report_only_prompt, build_user_prompt
from .schemas import CarePlan, PatientProfile

logger = logging.getLogger("nipcure.ai")

# Configuration via environment variables
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "google/gemma-3-4b-it")
GEMMA_API_BASE = os.getenv("GEMMA_API_BASE", "").rstrip("/")
GEMMA_API_KEY = os.getenv("GEMMA_API_KEY") or os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or ""
GEMMA_PROVIDER = os.getenv("GEMMA_PROVIDER", "auto").lower()
GEMMA_TIMEOUT_SECONDS = float(os.getenv("GEMMA_TIMEOUT_SECONDS", "30.0"))


def _clean_json_text(raw_text: str) -> str:
    """Extract valid JSON from raw model output, stripping markdown code fences."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return text


def _extract_and_parse_json(raw_text: str) -> dict[str, Any]:
    """Parse JSON string into a dictionary, handling edge cases."""
    cleaned = _clean_json_text(raw_text)
    return json.loads(cleaned)


def _matches_term(text: str, term: str) -> bool:
    """Check if a term or its singular/plural variant matches within text."""
    text_lower = text.lower()
    term_lower = term.lower()
    if term_lower in text_lower:
        return True
    if term_lower.endswith("s") and len(term_lower) > 3 and term_lower[:-1] in text_lower:
        return True
    if term_lower + "s" in text_lower:
        return True
    return False


def _rule_based_report_extraction(report_text: str) -> CarePlan:
    """Deterministic, grounded clinical extractor extracting ONLY facts present in the report.

    Strictly complies with safety rules:
    - Never invents medications, dosages, diagnoses, or instructions.
    - Preserves exact clinical terminology.
    - Cites source sentences from the report.
    """
    lines = [line.strip() for line in report_text.splitlines() if line.strip()]

    medicines: list[str] = []
    what_to_do: list[str] = []
    what_to_avoid: list[str] = []
    food_guidance: list[str] = []
    warnings: list[str] = []
    follow_up: list[str] = []
    doctor_questions: list[str] = []
    sources: list[str] = []

    current_section = "general"
    med_keywords = ("rx", "prescription", "medication", "medicine", "tablet", "capsule", "mg", "dose", "take ")
    avoid_keywords = ("avoid", "do not", "refrain", "stop", "discontinue", "limit")
    action_keywords = ("exercise", "walk", "monitor", "check", "measure", "keep", "follow", "apply", "rest", "drink")
    diet_keywords = ("diet", "food", "nutrition", "sodium", "salt", "sugar", "water", "fluid", "fiber", "meal")
    warning_keywords = ("warning", "caution", "alert", "danger", "urgent", "emergency", "seek care", "red flag")
    followup_keywords = ("follow-up", "follow up", "appointment", "return in", "visit in", "recheck", "next visit")

    for raw_line in lines:
        line = raw_line.strip()
        lower_line = line.lower()

        # Check for section headers and strip prefixes if followed by content
        for h in ["medications:", "prescriptions:", "current medications:"]:
            if lower_line.startswith(h):
                current_section = "meds"
                line = line[len(h):].strip()
                lower_line = line.lower()
                break
        for h in ["plan:", "recommendations:", "instructions:", "discharge instructions:"]:
            if lower_line.startswith(h):
                current_section = "plan"
                line = line[len(h):].strip()
                lower_line = line.lower()
                break
        for h in ["warnings:", "precautions:"]:
            if lower_line.startswith(h):
                current_section = "warnings"
                line = line[len(h):].strip()
                lower_line = line.lower()
                break
        for h in ["follow up:", "follow-up:"]:
            if lower_line.startswith(h):
                current_section = "followup"
                line = line[len(h):].strip()
                lower_line = line.lower()
                break

        if not line:
            continue

        segments = [s.strip(" -*•\t") for s in re.split(r"(?<=[.;])\s+", line) if s.strip(" -*•\t")]
        if not segments:
            segments = [line.strip("-*• 1234567890.)")]

        for seg in segments:
            seg_clean = seg.strip("-*• 1234567890.)")
            lower_seg = seg_clean.lower()
            if not seg_clean:
                continue

            # Extract medicines
            if (
                current_section == "meds"
                or any(kw in lower_seg for kw in ["tablet", "capsule", " mg", "mcg", "daily", "twice a day", "bid", "tid"])
            ) and any(kw in lower_seg for kw in med_keywords):
                if seg_clean not in medicines and len(seg_clean) < 150:
                    medicines.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

            # Extract things to avoid
            if any(kw in lower_seg for kw in avoid_keywords):
                if seg_clean not in what_to_avoid and len(seg_clean) < 160:
                    what_to_avoid.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

            # Extract actions to do
            elif any(kw in lower_seg for kw in action_keywords) or current_section == "plan":
                if seg_clean not in what_to_do and seg_clean not in medicines and len(seg_clean) < 160:
                    what_to_do.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

            # Extract food guidance
            if any(kw in lower_seg for kw in diet_keywords):
                if seg_clean not in food_guidance and len(seg_clean) < 160:
                    food_guidance.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

            # Extract warnings
            if any(kw in lower_seg for kw in warning_keywords) or current_section == "warnings":
                if seg_clean not in warnings and len(seg_clean) < 160:
                    warnings.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

            # Extract follow up
            if any(kw in lower_seg for kw in followup_keywords) or current_section == "followup":
                if seg_clean not in follow_up and len(seg_clean) < 160:
                    follow_up.append(seg_clean)
                    sources.append(f"Report: '{seg_clean}'")

    if not follow_up:
        follow_up.append("Needs verification with your doctor's office")

    if medicines:
        doctor_questions.append("Can we review my exact medication timing and any possible side effects?")
    if not doctor_questions:
        doctor_questions.append("What specific warning signs should prompt me to call the clinic?")

    if not sources and lines:
        sources.append(f"Report excerpt: {lines[0][:100]}")

    summary_parts = ["Here is the summary of your medical report."]
    if medicines:
        summary_parts.append(f"You have {len(medicines)} prescribed medication(s) listed.")
    if what_to_do:
        summary_parts.append("Your doctor noted specific daily steps to follow.")
    if follow_up and follow_up[0] != "Needs verification with your doctor's office":
        summary_parts.append(f"Follow-up: {follow_up[0]}.")
    summary = " ".join(summary_parts)

    return CarePlan(
        summary=summary,
        medicines=medicines,
        what_to_do=what_to_do,
        what_to_avoid=what_to_avoid,
        food_guidance=food_guidance,
        warnings=warnings,
        follow_up=follow_up,
        doctor_questions=doctor_questions,
        conflicts=[],
        sources=sources[:10],
    )


def _call_gemma_api(user_prompt: str) -> str:
    """Invoke the Gemma 3 model via HTTP endpoint (Ollama, HF Inference, or OpenAI-compatible)."""
    provider = os.getenv("GEMMA_PROVIDER", GEMMA_PROVIDER).lower()
    base_url = os.getenv("GEMMA_API_BASE", GEMMA_API_BASE).rstrip("/")
    model = os.getenv("GEMMA_MODEL", GEMMA_MODEL)
    api_key = os.getenv("GEMMA_API_KEY", "")

    # Auto-detect or configure Ollama
    if provider == "ollama" or (provider == "auto" and not base_url and not api_key):
        if not base_url:
            base_url = "http://127.0.0.1:11434/v1"
        if model == "google/gemma-3-4b-it":
            model = "gemma3:4b"
    elif not base_url:
        base_url = "https://router.huggingface.co/hf-inference/v1"
        if not api_key:
            api_key = os.getenv("HF_TOKEN", "")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    endpoint = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,  # Low temperature for clinical accuracy and groundedness
        "max_tokens": 1500,
    }

    logger.info("Calling Gemma 3 at %s (model: %s)", endpoint, model)

    timeout = float(os.getenv("GEMMA_TIMEOUT_SECONDS", GEMMA_TIMEOUT_SECONDS))
    with httpx.Client(timeout=timeout) as client:
        response = client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _extract_initial_medical_plan(report_text: str) -> CarePlan:
    """Step 1: Generate initial care plan based ONLY on facts explicitly present in the report."""
    user_prompt = build_report_only_prompt(report_text)
    try:
        raw_output = _call_gemma_api(user_prompt)
        parsed_dict = _extract_and_parse_json(raw_output)
        care_plan = CarePlan(**parsed_dict)
        logger.info("Successfully extracted initial medical plan via Gemma 3.")
        return care_plan
    except Exception as exc:
        logger.warning(
            "Gemma 3 endpoint call could not be completed (%s). Using clinical safety report extractor.",
            str(exc),
        )
        return _rule_based_report_extraction(report_text)


def _detect_conflicts(plan: CarePlan, profile: PatientProfile) -> tuple[list[str], list[str]]:
    """Step 2 & 3: Compare medical plan with patient profile and detect conflicts.

    Never silently replaces report information with profile information.
    Explicitly flags conflicts with 'Conflict between report and profile' or 'Needs verification'.
    """
    conflicts: list[str] = []
    warnings_to_add: list[str] = []

    # 1. Allergies vs Prescribed Medications
    if profile.allergies:
        allergies_list = [a.strip().lower() for a in re.split(r"[,;\n]+", profile.allergies) if a.strip()]
        for med in plan.medicines:
            for allergy in allergies_list:
                if allergy and _matches_term(med, allergy):
                    conflict_msg = (
                        f"Conflict between report and profile: Patient profile lists allergy to '{allergy}', "
                        f"but report prescribes '{med}'. Needs verification with doctor before taking."
                    )
                    conflicts.append(conflict_msg)
                    warn_msg = f"ALLERGY ALERT: Prescribed '{med}' conflicts with patient allergy '{allergy}'. Needs verification."
                    if warn_msg not in warnings_to_add:
                        warnings_to_add.append(warn_msg)

        # 2. Allergies vs Food Guidance
        for food in plan.food_guidance:
            for allergy in allergies_list:
                if allergy and _matches_term(food, allergy):
                    conflict_msg = (
                        f"Conflict between report and profile: Patient profile lists allergy to '{allergy}', "
                        f"but report food guidance mentions '{food}'. Needs verification with doctor/nutritionist."
                    )
                    conflicts.append(conflict_msg)
                    warn_msg = f"DIETARY ALLERGY ALERT: Food item '{food}' conflicts with allergy '{allergy}'. Needs verification."
                    if warn_msg not in warnings_to_add:
                        warnings_to_add.append(warn_msg)

    # 3. Dietary Restrictions vs Doctor Guidance
    if profile.dietary_restrictions:
        restrictions = [r.strip().lower() for r in re.split(r"[,;\n]+", profile.dietary_restrictions) if r.strip()]
        for r in restrictions:
            if "low sodium" in r or "low salt" in r:
                for avoid in plan.what_to_avoid:
                    if "low sodium" in avoid.lower() or "salt restriction" in avoid.lower():
                        conflicts.append(
                            f"Conflict between report and profile: Patient profile specifies '{r}', "
                            f"while report contradicts with '{avoid}'. Needs verification."
                        )

    # 4. Check for ambiguous or missing follow-up in the report
    if not plan.follow_up or any("needs verification" in f.lower() for f in plan.follow_up):
        unclear_msg = "Needs verification: Follow-up timeline or appointment details are not clearly specified in report."
        if unclear_msg not in conflicts:
            conflicts.append(unclear_msg)

    return conflicts, warnings_to_add


def _personalize_safely(plan: CarePlan, profile: PatientProfile, conflicts: list[str]) -> CarePlan:
    """Step 4: Use profile information ONLY for safe personalization, clearly labeled as [Patient profile]."""
    personalized_food = list(plan.food_guidance)
    personalized_todo = list(plan.what_to_do)
    questions = list(plan.doctor_questions)

    # Safely incorporate food preferences labeled as [Patient profile]
    if profile.food_likes:
        personalized_food.append(
            f"[Patient profile] Food preference: Patient enjoys {profile.food_likes}. Incorporate within doctor's dietary advice."
        )

    if profile.food_dislikes:
        personalized_food.append(
            f"[Patient profile] Food preference: Patient prefers to avoid {profile.food_dislikes}."
        )

    if profile.dietary_restrictions:
        personalized_food.append(
            f"[Patient profile] Dietary restriction: {profile.dietary_restrictions} (noted from patient profile)."
        )

    if profile.notes:
        personalized_todo.append(
            f"[Patient profile] Note: {profile.notes}"
        )

    # Add questions for any detected conflicts
    if conflicts:
        for c in conflicts:
            if "allergy" in c.lower():
                questions.insert(
                    0,
                    f"Doctor question: Can you verify if prescribed treatment is safe with my allergy to {profile.allergies}?",
                )
            elif "diet" in c.lower() or "restriction" in c.lower():
                questions.append(
                    f"Doctor question: How should my dietary restriction ({profile.dietary_restrictions}) be balanced with the report's recommendations?"
                )

    # Return updated CarePlan
    return CarePlan(
        summary=plan.summary,
        medicines=list(plan.medicines),  # Never modified or replaced
        what_to_do=personalized_todo,
        what_to_avoid=list(plan.what_to_avoid),  # Never modified
        food_guidance=personalized_food,
        warnings=list(plan.warnings),
        follow_up=list(plan.follow_up),
        doctor_questions=questions,
        conflicts=conflicts,
        sources=list(plan.sources),
    )


def generate_care_plan(
    report_text: str,
    patient_profile: dict[str, Any] | PatientProfile | None = None,
) -> CarePlan:
    """Execute the multi-stage NipCure AI workflow:

    1. Report -> Medical plan (strictly from report)
    2. Profile comparison (compare with age, allergies, diet, preferences)
    3. Conflict detection (explicitly reported as 'Conflict between report and profile' or 'Needs verification')
    4. Safe personalization (labeled strictly as [Patient profile])
    5. Final plan (preserves all report facts without hallucination or silent overwrite)
    """
    if isinstance(patient_profile, dict):
        profile = PatientProfile(**patient_profile)
    elif isinstance(patient_profile, PatientProfile):
        profile = patient_profile
    else:
        profile = PatientProfile()

    cleaned_text = (report_text or "").strip()
    if not cleaned_text:
        return CarePlan(
            summary="No medical report text was found to review.",
            warnings=["No text detected in the uploaded report. Please check the document."],
            follow_up=["Needs verification with your clinic."],
            conflicts=["Needs verification: Document contains no readable medical report text."],
        )

    # Step 1: Generate initial care plan based ONLY on facts in the report
    initial_plan = _extract_initial_medical_plan(cleaned_text)

    # Step 2 & 3: Compare with patient profile and detect conflicts
    conflicts, new_warnings = _detect_conflicts(initial_plan, profile)
    for warn in new_warnings:
        if warn not in initial_plan.warnings:
            initial_plan.warnings.insert(0, warn)

    # Step 4: Safely personalize with clearly labeled [Patient profile] annotations
    final_plan = _personalize_safely(initial_plan, profile, conflicts)

    # Enforce safe follow-up
    if not final_plan.follow_up:
        final_plan.follow_up = ["Needs verification with your doctor's office"]

    return final_plan


def generate_care_plan_dict(
    report_text: str,
    patient_profile: dict[str, Any] | PatientProfile | None = None,
) -> dict[str, Any]:
    """Helper returning a frontend-ready dictionary matching both Gemma 3 schema and UI aliases."""
    plan = generate_care_plan(report_text, patient_profile)
    return plan.to_frontend_dict()
