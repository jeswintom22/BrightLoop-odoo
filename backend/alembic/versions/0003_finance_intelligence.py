"""Phase 2 (P4): financial_summaries — persisted AI report storage.

Revision ID: 0003_finance_intelligence
Revises: 0002_phase1
Create Date: 2026-10-31

Dialect-portable (sqlite dev/tests + Postgres prod): sa.JSON maps to JSONB
on Postgres via the shared Base conventions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_finance_intelligence"
down_revision: Union[str, None] = "0002_phase1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_summaries",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("period_kind", sa.String(16), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False),
        sa.Column("summary_text", sa.Text, nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(60)),
        sa.Column("generated_by", sa.Uuid),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "period_kind", "period_start", "period_end",
            name="uq_financial_summary_period",
        ),
    )
    op.create_index(
        "ix_financial_summaries_created", "financial_summaries", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_financial_summaries_created", table_name="financial_summaries")
    op.drop_table("financial_summaries")
