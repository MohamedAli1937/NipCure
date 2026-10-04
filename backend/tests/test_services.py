import asyncio
from unittest.mock import patch, MagicMock
from app.services.elevenlabs_service import (
    build_spoken_script,
    clean_text_for_speech,
    generate_speech,
    ElevenLabsNotConfiguredError,
)
from app.services.serpapi_service import (
    extract_explicit_medical_topics,
    search_medical_resources,
    identify_source_name,
)


def test_clean_text_for_speech():
    raw = "**Take Lisinopril** 10mg daily. [Patient profile] Prefers morning. Avoid [grapefruit](http://example.com)."
    cleaned = clean_text_for_speech(raw)
    assert "**" not in cleaned
    assert "[Patient profile]" not in cleaned
    assert "Take Lisinopril" in cleaned
    assert "Avoid grapefruit" in cleaned


def test_build_spoken_script():
    plan = {
        "summary": "You are recovering well from your infection.",
        "medicines": ["Amoxicillin 500mg three times daily"],
        "what_to_do": ["Drink plenty of water and rest"],
        "what_to_avoid": ["Heavy exercise"],
        "warnings": ["Call doctor if rash appears"],
        "food_guidance": ["Take with food"],
        "follow_up": ["Follow-up in 7 days"],
    }
    script = build_spoken_script(plan)
    assert "Here is your care plan summary" in script
    assert "Amoxicillin" in script
    assert "Important safety reminders" in script
    assert "Drink plenty of water" in script
    assert "contact your doctor" in script


def test_elevenlabs_not_configured_raises_error():
    with patch("app.services.elevenlabs_service.get_elevenlabs_api_key", return_value=None):
        try:
            asyncio.run(generate_speech("Test speech"))
            assert False, "Should have raised ElevenLabsNotConfiguredError"
        except ElevenLabsNotConfiguredError:
            pass


def test_elevenlabs_generate_speech_success():
    with patch("app.services.elevenlabs_service.get_elevenlabs_api_key", return_value="dummy_key"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_error = False
        mock_response.content = b"FAKE_MP3_AUDIO_DATA"

        async def mock_post(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            audio = asyncio.run(generate_speech("Take your pills daily."))
            assert audio == b"FAKE_MP3_AUDIO_DATA"


def test_extract_explicit_medical_topics():
    report_text = "Patient was diagnosed with Hypertension. Prescribed Lisinopril 10mg and Metformin 500mg for Type 2 Diabetes."
    plan = {
        "medicines": ["Lisinopril 10mg tablet once daily", "Metformin 500mg twice daily"]
    }
    topics = extract_explicit_medical_topics(report_text, plan)
    assert "Lisinopril" in topics
    assert "Metformin" in topics
    assert "Hypertension" in topics or "Type 2 Diabetes" in topics


def test_identify_source_name():
    assert "Mayo Clinic" in identify_source_name("https://www.mayoclinic.org/drugs-supplements/lisinopril")
    assert "MedlinePlus" in identify_source_name("https://medlineplus.gov/druginfo/meds/a692051.html")
    assert "CDC" in identify_source_name("https://www.cdc.gov/bloodpressure/index.htm")


def test_serpapi_not_configured_returns_empty():
    with patch("app.services.serpapi_service.get_serpapi_key", return_value=None):
        res = asyncio.run(search_medical_resources(["Lisinopril"]))
        assert res == []


def test_serpapi_search_success():
    with patch("app.services.serpapi_service.get_serpapi_key", return_value="dummy_serp_key"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_error = False
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": "Lisinopril: Guide and Instructions",
                    "link": "https://www.mayoclinic.org/drugs/lisinopril",
                    "snippet": "Learn how to use Lisinopril safely.",
                    "source": "mayoclinic.org",
                }
            ]
        }

        async def mock_get(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            results = asyncio.run(search_medical_resources(["Lisinopril"]))
            assert len(results) == 1
            assert results[0]["title"] == "Lisinopril: Guide and Instructions"
            assert "Mayo Clinic" in results[0]["source"]
            assert results[0]["link"] == "https://www.mayoclinic.org/drugs/lisinopril"
