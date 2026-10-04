from datetime import datetime
from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Index, JSON,
                        SmallInteger, String, Text, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

JsonType = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="user", cascade="all, delete-orphan",
                                                   order_by="Report.created_at.desc()")

Index("uq_users_name_lower", func.lower(User.name), unique=True)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint("age BETWEEN 1 AND 120", name="ck_profiles_age"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    age: Mapped[int | None] = mapped_column(SmallInteger)
    allergies: Mapped[str] = mapped_column(Text, default="")
    food_likes: Mapped[str] = mapped_column(Text, default="")
    food_dislikes: Mapped[str] = mapped_column(Text, default="")
    dietary_restrictions: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="profile")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    pdf_text: Mapped[str] = mapped_column(Text, default="")   
    plan: Mapped[dict] = mapped_column(JsonType)              
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="reports")