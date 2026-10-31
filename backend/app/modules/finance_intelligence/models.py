"""Finance-intelligence persistence — generated financial summaries only.

Analytics are computed on demand (no cached metric tables); only the
AI-generated summary text is persisted so duplicate reports aren't
regenerated and the provenance (provider/model/period) is auditable.
"""

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from ...core.database import Base
from ...core.time import utc_now

JSONB = sa.JSON().with_variant(postgresql.JSONB, "postgresql")


class FinancialSummary(Base):
    __tablename__ = "financial_summaries"
    __table_args__ = (
        sa.UniqueConstraint(
            "period_kind", "period_start", "period_end",
            name="uq_financial_summary_period",
        ),
        sa.Index("ix_financial_summaries_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    period_kind: Mapped[str] = mapped_column(sa.String(16))  # "month" | "custom"
    period_start: Mapped[dt.date] = mapped_column(sa.Date)
    period_end: Mapped[dt.date] = mapped_column(sa.Date)
    metrics: Mapped[dict] = mapped_column(JSONB)
    summary_text: Mapped[str] = mapped_column(sa.Text)
    provider: Mapped[str] = mapped_column(sa.String(20))  # openai | gemini | template | template-fallback
    model: Mapped[str | None] = mapped_column(sa.String(60))
    generated_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )
