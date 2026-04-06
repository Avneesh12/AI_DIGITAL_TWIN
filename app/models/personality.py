"""app/models/personality.py — PersonalityProfile ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PersonalityProfile(Base):
    __tablename__ = "personality_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── Core Traits ───────────────────────────────────────────────────────
    tone: Mapped[str | None] = mapped_column(String(100))          # "formal" | "casual" | "witty"
    communication_style: Mapped[str | None] = mapped_column(Text)  # "concise" | "verbose"
    values: Mapped[list] = mapped_column(JSONB, default=list)      # ["honesty", "efficiency"]
    interests: Mapped[list] = mapped_column(JSONB, default=list)   # ["technology", "philosophy"]
    decision_style: Mapped[str | None] = mapped_column(String(100)) # "analytical" | "intuitive"

    # ── Big Five (0.0 – 1.0) ─────────────────────────────────────────────
    openness: Mapped[float] = mapped_column(Float, default=0.5)
    conscientiousness: Mapped[float] = mapped_column(Float, default=0.5)
    extraversion: Mapped[float] = mapped_column(Float, default=0.5)
    agreeableness: Mapped[float] = mapped_column(Float, default=0.5)
    neuroticism: Mapped[float] = mapped_column(Float, default=0.5)

    # ── Free-form descriptor ──────────────────────────────────────────────
    persona_summary: Mapped[str | None] = mapped_column(Text)

    # ── Learning metadata ─────────────────────────────────────────────────
    trait_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationship ──────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="personality_profile")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PersonalityProfile user_id={self.user_id} confidence={self.trait_confidence:.2f}>"
