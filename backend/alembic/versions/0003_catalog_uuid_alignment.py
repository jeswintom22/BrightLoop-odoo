"""Catalog UUID alignment — reconcile Sherin's P2 model rework with the DB.

Revision ID: 0003_catalog_align
Revises: 0002_phase1
Create Date: 2026-10-31

Her models switched tax_configurations / subscription_plans / discounts to
Uuid PKs, renamed plan availability fields (start_date -> available_from,
end_date -> available_until, auto_closure -> automatic_closure), renamed
discounts.min_purchase_amount -> minimum_purchase_amount, added
discounts.description and tax_configurations.description, and flipped
FKs (products.tax_id, plans.tax_id, discount_products.discount_id,
quotation line plan_id) to Uuid.

NOTE: int -> Uuid conversion cannot preserve existing PK values; dev-stage
databases should re-seed catalog rows after upgrading (FK references to old
int ids are not migratable).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_catalog_align"
down_revision: Union[str, None] = "0002_phase1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tax_configurations") as b:
        b.alter_column("id", type_=sa.Uuid())
        b.add_column(sa.Column("description", sa.Text(), nullable=True))

    with op.batch_alter_table("products") as b:
        b.alter_column("tax_id", type_=sa.Uuid())

    with op.batch_alter_table("subscription_plans") as b:
        b.alter_column("id", type_=sa.Uuid())
        b.alter_column("tax_id", type_=sa.Uuid())
        b.alter_column("start_date", new_column_name="available_from", type_=sa.Date())
        b.alter_column("end_date", new_column_name="available_until", type_=sa.Date())
        b.alter_column("auto_closure", new_column_name="automatic_closure", type_=sa.Boolean())

    with op.batch_alter_table("discounts") as b:
        b.alter_column("id", type_=sa.Uuid())
        b.alter_column("min_purchase_amount", new_column_name="minimum_purchase_amount")
        b.add_column(sa.Column("description", sa.Text(), nullable=True))

    with op.batch_alter_table("discount_products") as b:
        b.alter_column("discount_id", type_=sa.Uuid())

    for table in ("quotation_template_lines", "quotation_lines", "subscriptions"):
        with op.batch_alter_table(table) as b:
            b.alter_column("plan_id", type_=sa.Uuid())


def downgrade() -> None:
    for table in ("subscriptions", "quotation_lines", "quotation_template_lines"):
        with op.batch_alter_table(table) as b:
            b.alter_column("plan_id", type_=sa.Integer())

    with op.batch_alter_table("discount_products") as b:
        b.alter_column("discount_id", type_=sa.Integer())

    with op.batch_alter_table("discounts") as b:
        b.drop_column("description")
        b.alter_column("minimum_purchase_amount", new_column_name="min_purchase_amount")
        b.alter_column("id", type_=sa.Integer())

    with op.batch_alter_table("subscription_plans") as b:
        b.alter_column("automatic_closure", new_column_name="auto_closure", type_=sa.Boolean())
        b.alter_column("available_until", new_column_name="end_date", type_=sa.Date())
        b.alter_column("available_from", new_column_name="start_date", type_=sa.Date())
        b.alter_column("tax_id", type_=sa.Integer())
        b.alter_column("id", type_=sa.Integer())

    with op.batch_alter_table("products") as b:
        b.alter_column("tax_id", type_=sa.Integer())

    with op.batch_alter_table("tax_configurations") as b:
        b.drop_column("description")
        b.alter_column("id", type_=sa.Integer())
