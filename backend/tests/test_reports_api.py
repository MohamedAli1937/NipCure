import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# In-memory SQLite engine for testing
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

SAMPLE_PDF_BYTES = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 210 >> stream
BT
/F1 12 Tf
72 712 Td
(CLINICAL REPORT) Tj
0 -20 Td
(Medications: Lisinopril 10mg tablet once daily in morning. Amoxicillin 500mg capsule.) Tj
0 -20 Td
(Instructions: Walk 20 minutes daily. Avoid high sodium foods.) Tj
0 -20 Td
(Follow-up in 2 weeks.) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000505 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
582
%%EOF"""


def test_full_pipeline_upload_report_and_generate_gemma_care_plan():
    # 1. Register a test user
    reg_res = client.post("/api/auth/register", json={"name": "AliceSmith", "password": "password123"})
    assert reg_res.status_code == 200
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Update patient profile with allergies
    prof_res = client.put(
        "/profile",
        headers=headers,
        json={
            "age": 75,
            "allergies": "Amoxicillin",
            "food_likes": "Oatmeal, Apples",
            "food_dislikes": "Grapefruit",
            "dietary_restrictions": "Low sodium",
            "notes": "Prefers large print",
        },
    )
    assert prof_res.status_code == 200

    # 3. Upload medical PDF report
    files = {"file": ("discharge_summary.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")}
    upload_res = client.post("/reports", headers=headers, files=files)
    assert upload_res.status_code == 201

    report_data = upload_res.json()
    assert report_data["filename"] == "discharge_summary.pdf"
    plan = report_data["plan"]

    # Verify all expected Gemma 3 structured care plan fields exist
    assert "summary" in plan
    assert "medicines" in plan
    assert "what_to_do" in plan
    assert "what_to_avoid" in plan
    assert "food_guidance" in plan
    assert "warnings" in plan
    assert "follow_up" in plan
    assert "doctor_questions" in plan
    assert "conflicts" in plan
    assert "sources" in plan

    # Verify medications, safety allergy warnings, and explicit conflict detection
    assert any("Lisinopril" in m for m in plan["medicines"])
    assert any("Amoxicillin" in m for m in plan["medicines"])
    assert any("allergy" in w.lower() and "amoxicillin" in w.lower() for w in plan["warnings"])
    assert any("Conflict between report and profile" in c and "amoxicillin" in c.lower() for c in plan["conflicts"])

    # 4. Fetch the report by ID
    report_id = report_data["id"]
    get_res = client.get(f"/reports/{report_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == report_id
    assert get_res.json()["plan"]["summary"] == plan["summary"]

    # 5. Test Voice Generation endpoint (graceful 503 if unconfigured, 200 if configured)
    from unittest.mock import patch, AsyncMock
    with patch("app.services.elevenlabs_service.get_elevenlabs_api_key", return_value=None):
        voice_unconf_res = client.post(f"/reports/{report_id}/voice", headers=headers)
        assert voice_unconf_res.status_code == 503

    with patch("app.reports.generate_speech", new=AsyncMock(return_value=b"AUDIO_MP3_DATA")):
        voice_success_res = client.post(f"/reports/{report_id}/voice", headers=headers)
        assert voice_success_res.status_code == 200
        assert voice_success_res.content == b"AUDIO_MP3_DATA"
        assert "audio/mpeg" in voice_success_res.headers.get("content-type", "")

    # 6. Test Research endpoint
    research_res = client.get(f"/reports/{report_id}/research", headers=headers)
    assert research_res.status_code == 200
    research_data = research_res.json()
    assert "topics" in research_data
    assert "resources" in research_data
    assert any("Lisinopril" in t for t in research_data["topics"])

    # 7. Re-examine report after updating patient profile
    client.put(
        "/profile",
        headers=headers,
        json={
            "age": 76,
            "allergies": "Amoxicillin, Penicillin",
            "food_likes": "Blueberries, Oatmeal",
            "food_dislikes": "Grapefruit",
            "dietary_restrictions": "Low sodium",
            "notes": "Prefers large print",
        },
    )
    reexamine_res = client.post(f"/reports/{report_id}/reexamine", headers=headers)
    assert reexamine_res.status_code == 200
    reexamined_plan = reexamine_res.json()["plan"]
    assert "summary" in reexamined_plan
    assert any("Amoxicillin" in m for m in reexamined_plan["medicines"])

    # 8. Delete the report
    del_res = client.delete(f"/reports/{report_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ok"

    # Verify report is gone
    not_found_res = client.get(f"/reports/{report_id}", headers=headers)
    assert not_found_res.status_code == 404

    list_res = client.get("/reports", headers=headers)
    assert list_res.status_code == 200
    assert not any(r["id"] == report_id for r in list_res.json())

