"""app/models/decision.py — Decision ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    context: Mapped[str] = mapped_column(Text, nullable=False)    # What was the decision about?
    chosen_option: Mapped[str] = mapped_column(Text, nullable=False)  # What did the user decide?
    reasoning: Mapped[str | None] = mapped_column(Text)           # Why did they decide it?
    outcome: Mapped[str | None] = mapped_column(Text)             # What was the result?
    tags: Mapped[list] = mapped_column(JSONB, default=list)       # ["career", "finance", "health"]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="decisions")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Decision id={self.id} user_id={self.user_id}>"
