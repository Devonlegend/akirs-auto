"""add taxable entities table

Revision ID: d4f7a1b2c3e8
Revises: c9c255460452
Create Date: 2026-06-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f7a1b2c3e8"
down_revision: Union[str, None] = "c9c255460452"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "taxable_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("advertiser_id", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(length=256), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("emails", sa.Text(), nullable=True),
        sa.Column("phones", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("taxable_score", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "assessed_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["advertiser_id"], ["advertisers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("advertiser_id", name="uq_taxable_entity_advertiser"),
    )
    op.create_index(
        op.f("ix_taxable_entities_advertiser_id"),
        "taxable_entities",
        ["advertiser_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_taxable_entities_advertiser_id"), table_name="taxable_entities"
    )
    op.drop_table("taxable_entities")
