from typing import Any
from .ai.gemma import generate_care_plan_dict


def build_care_plan(report_text: str, user_profile: dict[str, Any]) -> dict[str, Any]:
    """AI Care Plan hand-off function powered by Gemma 3."""
    return generate_care_plan_dict(report_text, user_profile)
