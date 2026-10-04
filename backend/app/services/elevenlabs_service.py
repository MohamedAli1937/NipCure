import os
import re
import httpx
from typing import Any

from pathlib import Path
from dotenv import load_dotenv

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah
FALLBACK_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George


class ElevenLabsError(Exception):
    """Base exception for ElevenLabs API errors."""
    pass


class ElevenLabsNotConfiguredError(ElevenLabsError):
    """Raised when ELEVENLABS_API_KEY is not configured."""
    pass


def _reload_env_if_needed():
    for candidate in (
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=True)


def get_elevenlabs_api_key() -> str | None:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        _reload_env_if_needed()
        key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    return key if key else None


def get_elevenlabs_voice_id() -> str:
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not voice_id:
        _reload_env_if_needed()
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    return voice_id if voice_id else DEFAULT_VOICE_ID


def clean_text_for_speech(text: str) -> str:
    """Removes markdown symbols and bracket tags so text sounds natural when spoken."""
    if not text:
        return ""
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[Patient profile\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[Needs verification\]", "Needs verification.", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_spoken_script(plan: dict[str, Any]) -> str:
    """Builds a warm, respectful, senior-friendly spoken script from a CarePlan dictionary."""
    sections = []

    summary = clean_text_for_speech(plan.get("summary", ""))
    if summary:
        sections.append(f"Hello. Here is your care plan summary. {summary}")

    warnings = plan.get("warnings") or []
    if warnings:
        warn_text = ". ".join(clean_text_for_speech(w) for w in warnings if w)
        if warn_text:
            sections.append(f"Important safety reminders: {warn_text}.")

    medicines = plan.get("medicines") or []
    if medicines:
        med_text = ". ".join(clean_text_for_speech(m) for m in medicines if m)
        if med_text:
            sections.append(f"Your medications: {med_text}.")

    what_to_do = plan.get("what_to_do") or plan.get("todo") or []
    if what_to_do:
        todo_text = ". ".join(clean_text_for_speech(t) for t in what_to_do if t)
        if todo_text:
            sections.append(f"Recommended daily activities: {todo_text}.")

    what_to_avoid = plan.get("what_to_avoid") or plan.get("avoid") or []
    if what_to_avoid:
        avoid_text = ". ".join(clean_text_for_speech(a) for a in what_to_avoid if a)
        if avoid_text:
            sections.append(f"Things to avoid: {avoid_text}.")

    food_guidance = plan.get("food_guidance") or plan.get("food") or []
    if food_guidance:
        food_text = ". ".join(clean_text_for_speech(f) for f in food_guidance if f)
        if food_text:
            sections.append(f"Food guidance: {food_text}.")

    follow_up = plan.get("follow_up") or plan.get("followup") or []
    if follow_up:
        follow_text = ". ".join(clean_text_for_speech(fl) for fl in follow_up if fl)
        if follow_text:
            sections.append(f"Follow up instructions: {follow_text}.")

    sections.append("If you have any questions or feel unwell, please contact your doctor or healthcare provider right away.")
    return "\n\n".join(sections)


async def generate_speech(text: str, voice_id: str | None = None) -> bytes:
    """Calls the ElevenLabs Text-to-Speech API and returns the MP3 audio bytes.

    Raises:
        ElevenLabsNotConfiguredError: If ELEVENLABS_API_KEY is not set.
        ElevenLabsError: If the API request fails or returns an error.
    """
    api_key = get_elevenlabs_api_key()
    if not api_key:
        raise ElevenLabsNotConfiguredError("ElevenLabs API key is not configured. Please set ELEVENLABS_API_KEY in .env")

    selected_voice = voice_id or get_elevenlabs_voice_id()
    url = f"{ELEVENLABS_API_URL}/{selected_voice}"

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 402 and selected_voice != DEFAULT_VOICE_ID:
                url_fallback = f"{ELEVENLABS_API_URL}/{DEFAULT_VOICE_ID}"
                response = await client.post(url_fallback, json=payload, headers=headers)

            if response.status_code == 401:
                raise ElevenLabsError("Authentication failed: Invalid ElevenLabs API key.")
            elif response.status_code == 429:
                raise ElevenLabsError("ElevenLabs quota exceeded or rate limit reached.")
            elif response.is_error:
                error_msg = response.text[:200]
                raise ElevenLabsError(f"ElevenLabs API error ({response.status_code}): {error_msg}")

            return response.content
    except httpx.RequestError as exc:
        raise ElevenLabsError(f"Network error contacting ElevenLabs: {str(exc)}") from exc
