from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .api_schemas import ProfileInput, ProfileResponse
from .auth import get_current_user
from .database import get_db
from .models import Profile, User

router = APIRouter(tags=["Profile"])


@router.get("/profile", response_model=ProfileResponse | None)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.get(Profile, current_user.id)


@router.put("/profile", response_model=ProfileResponse)
def save_profile(
    data: ProfileInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, current_user.id)
    if profile is None:
        profile = Profile(user_id=current_user.id)
        db.add(profile)

    for field, value in data.model_dump().items():
        setattr(profile, field, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(profile)
    return profile

