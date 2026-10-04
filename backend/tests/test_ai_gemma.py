import json
import pytest
from app.ai.gemma import (
    _clean_json_text,
    _detect_conflicts,
    _extract_and_parse_json,
    _rule_based_report_extraction,
    generate_care_plan,
    generate_care_plan_dict,
)
from app.ai.prompts import SYSTEM_PROMPT, build_report_only_prompt, build_user_prompt
from app.ai.schemas import CarePlan, PatientProfile
from app.ai_interface import build_care_plan


SAMPLE_REPORT = """
CLINICAL DISCHARGE SUMMARY
Patient: John Doe, 72yo Male
Attending: Dr. Sarah Jenkins, MD

DIAGNOSIS:
Type 2 Diabetes Mellitus, Essential Hypertension.

MEDICATIONS:
- Metformin 500mg tablet, take 1 tablet twice daily with meals.
- Lisinopril 10mg tablet, take 1 tablet every morning with water.
- Amoxicillin 500mg capsule, 1 capsule every 8 hours for 7 days.

RECOMMENDATIONS & PLAN:
- Walk 20 minutes daily after lunch.
- Check and log morning blood pressure daily.
- Avoid heavy lifting and strenuous endurance workouts.
- Limit dietary sodium intake to under 2,000 mg per day.
- Avoid grapefruit and grapefruit juice.

WARNINGS:
- Seek immediate emergency medical care if experiencing chest pressure or severe shortness of breath.

FOLLOW-UP:
- Return to clinic for repeat renal panel in 4 weeks.
"""


def test_care_plan_schema_defaults():
    plan = CarePlan()
    assert plan.summary == ""
    assert plan.medicines == []
    assert plan.what_to_do == []
    assert plan.what_to_avoid == []
    assert plan.food_guidance == []
    assert plan.warnings == []
    assert plan.follow_up == []
    assert plan.doctor_questions == []
    assert plan.conflicts == []
    assert plan.sources == []

    frontend_dict = plan.to_frontend_dict()
    assert "conflicts" in frontend_dict
    assert "todo" in frontend_dict
    assert "avoid" in frontend_dict
    assert "food" in frontend_dict
    assert "followup" in frontend_dict
    assert "questions" in frontend_dict
    assert "resources" in frontend_dict
    assert "voice_text" in frontend_dict


def test_prompt_generation():
    profile = PatientProfile(
        age=72,
        allergies="Penicillin",
        food_likes="Oatmeal, Apples",
        food_dislikes="Fish",
        dietary_restrictions="Low sodium",
        notes="Uses a cane for long walks",
    )
    prompt = build_user_prompt(SAMPLE_REPORT, profile)
    assert "Age: 72" in prompt
    assert "Known Allergies: Penicillin" in prompt
    assert "Dietary Restrictions: Low sodium" in prompt
    assert "Type 2 Diabetes Mellitus" in prompt
    assert "Gemma 3" in SYSTEM_PROMPT
    assert "Needs verification" in SYSTEM_PROMPT

    report_only = build_report_only_prompt(SAMPLE_REPORT)
    assert "MEDICAL REPORT TEXT" in report_only
    assert "PATIENT PROFILE" not in report_only


def test_clean_json_text_markdown_stripping():
    raw_markdown = """```json
    {
      "summary": "Everything looks stable.",
      "medicines": ["Lisinopril 10mg"],
      "what_to_do": [],
      "what_to_avoid": [],
      "food_guidance": [],
      "warnings": [],
      "follow_up": ["In 2 weeks"],
      "doctor_questions": [],
      "conflicts": [],
      "sources": []
    }
    ```"""
    parsed = _extract_and_parse_json(raw_markdown)
    assert parsed["summary"] == "Everything looks stable."
    assert parsed["medicines"] == ["Lisinopril 10mg"]


def test_detect_conflicts_without_silent_replacement():
    profile = PatientProfile(allergies="Amoxicillin, Peanuts")
    base_plan = CarePlan(
        medicines=["Amoxicillin 500mg capsule", "Metformin 500mg"],
        food_guidance=["Eat peanut butter snack daily."],
        follow_up=["Needs verification"],
    )
    conflicts, warnings = _detect_conflicts(base_plan, profile)

    # Must explicitly state Conflict between report and profile or Needs verification
    assert len(conflicts) >= 2
    assert any("Conflict between report and profile" in c and "amoxicillin" in c.lower() for c in conflicts)
    assert any("Conflict between report and profile" in c and "peanut" in c.lower() for c in conflicts)
    assert any("Needs verification" in c for c in conflicts)


def test_care_plan_workflow_and_safe_personalization():
    profile = {
        "age": 72,
        "allergies": "Amoxicillin",
        "food_likes": "Oatmeal",
        "food_dislikes": "Grapefruit",
        "dietary_restrictions": "Low sodium",
        "notes": "Prefers morning appointments",
    }
    plan = generate_care_plan(SAMPLE_REPORT, profile)

    # 1. Structure
    assert isinstance(plan, CarePlan)
    assert len(plan.summary) > 0

    # 2. Medical report is primary: medicines are NEVER removed or replaced
    assert any("Amoxicillin" in m for m in plan.medicines)
    assert any("Metformin" in m for m in plan.medicines)
    assert any("Lisinopril" in m for m in plan.medicines)

    # 3. Conflict explicitly detected
    assert len(plan.conflicts) > 0
    assert any("Conflict between report and profile" in c and "amoxicillin" in c.lower() for c in plan.conflicts)

    # 4. Safe Personalization labeled strictly as [Patient profile]
    assert any("[Patient profile]" in f and "Oatmeal" in f for f in plan.food_guidance)
    assert any("[Patient profile]" in f and "Grapefruit" in f for f in plan.food_guidance)
    assert any("[Patient profile]" in item and "Prefers morning appointments" in item for item in plan.what_to_do)

    # 5. Follow-up & Sources
    assert any("4 weeks" in f.lower() or "renal" in f.lower() for f in plan.follow_up)
    assert len(plan.sources) > 0


def test_care_plan_missing_followup_needs_verification():
    report_no_followup = """
    Patient: Jane Smith
    MEDICATIONS:
    - Aspirin 81mg daily.
    INSTRUCTIONS:
    - Drink plenty of water.
    """
    plan = generate_care_plan(report_no_followup, {"allergies": ""})
    assert any("Needs verification" in f for f in plan.follow_up)
    assert any("Needs verification" in c for c in plan.conflicts)


def test_ai_interface_integration():
    profile = {"age": 80, "allergies": "None"}
    result = build_care_plan(SAMPLE_REPORT, profile)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "medicines" in result
    assert "what_to_do" in result
    assert "what_to_avoid" in result
    assert "food_guidance" in result
    assert "warnings" in result
    assert "follow_up" in result
    assert "doctor_questions" in result
    assert "conflicts" in result
    assert "sources" in result
    # Frontend aliases
    assert "todo" in result
    assert "avoid" in result
    assert "food" in result
    assert "followup" in result
    assert "questions" in result
    assert "resources" in result
    assert "voice_text" in result
