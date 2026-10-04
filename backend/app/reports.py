from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai_interface import build_care_plan
from .api_schemas import ReportResponse, ReportSummary
from .auth import get_current_user
from .database import get_db
from .models import Profile, Report, User
from .services.elevenlabs_service import (
    ElevenLabsError,
    ElevenLabsNotConfiguredError,
    build_spoken_script,
    generate_speech,
)
from .services.serpapi_service import (
    extract_explicit_medical_topics,
    search_medical_resources,
)

router = APIRouter(prefix="/reports", tags=["Reports"])
MAX_PDF_BYTES = 10 * 1024 * 1024


@router.get("", response_model=list[ReportSummary])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Report)
            .where(Report.user_id == current_user.id)
            .order_by(Report.created_at.desc())
        )
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == current_user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pdf") or file.content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=415, detail="Please upload a PDF file")

    contents = await file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller")

    try:
        reader = PdfReader(BytesIO(contents))
        report_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except PdfReadError as exc:
        raise HTTPException(status_code=422, detail="This PDF could not be read") from exc

    if not report_text:
        raise HTTPException(status_code=422, detail="This PDF has no readable text")

    profile = db.get(Profile, current_user.id)
    profile_data = {
        field: getattr(profile, field, None)
        for field in (
            "age",
            "allergies",
            "food_likes",
            "food_dislikes",
            "dietary_restrictions",
            "notes",
        )
    }
    report = Report(
        user_id=current_user.id,
        filename=filename[:255],
        pdf_text=report_text,
        plan=build_care_plan(report_text, profile_data),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=status.HTTP_200_OK)
def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == current_user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    db.delete(report)
    db.commit()
    return {"status": "ok", "message": "Report deleted successfully", "id": report_id}


@router.post("/{report_id}/reexamine", response_model=ReportResponse)
def reexamine_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == current_user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    profile = db.get(Profile, current_user.id)
    profile_data = {
        field: getattr(profile, field, None)
        for field in (
            "age",
            "allergies",
            "food_likes",
            "food_dislikes",
            "dietary_restrictions",
            "notes",
        )
    }

    report.plan = build_care_plan(report.pdf_text, profile_data)
    db.commit()
    db.refresh(report)
    return report


class VoiceRequest(BaseModel):
    text: str | None = None
    section: str | None = None


@router.post("/{report_id}/voice")
async def generate_report_voice(
    report_id: int,
    payload: VoiceRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == current_user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    plan = report.plan or {}

    if payload and payload.text and payload.text.strip():
        spoken_text = payload.text.strip()
    elif payload and payload.section and payload.section in plan:
        sec_val = plan[payload.section]
        if isinstance(sec_val, list):
            spoken_text = f"{payload.section.replace('_', ' ').title()}: " + ". ".join(str(item) for item in sec_val)
        else:
            spoken_text = str(sec_val)
    else:
        spoken_text = build_spoken_script(plan)

    if not spoken_text.strip():
        spoken_text = "No care plan content is available to read."

    try:
        audio_bytes = await generate_speech(spoken_text)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except ElevenLabsNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ElevenLabsError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/{report_id}/research")
async def get_report_research(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.user_id == current_user.id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    plan = report.plan or {}
    topics = extract_explicit_medical_topics(report.pdf_text, plan)
    resources = await search_medical_resources(topics)

    return {
        "report_id": report_id,
        "topics": topics,
        "resources": resources,
    }

