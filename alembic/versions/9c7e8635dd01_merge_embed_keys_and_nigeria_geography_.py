"""merge embed_keys and nigeria geography heads

Revision ID: 9c7e8635dd01
Revises: d34700f943d2, f2a7c8d9e0b1
Create Date: 2026-09-21 11:51:34.327433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c7e8635dd01'
down_revision: Union[str, None] = ('d34700f943d2', 'f2a7c8d9e0b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
