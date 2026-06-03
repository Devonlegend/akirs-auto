"""seed akwa ibom geography

Revision ID: a1b2c3d4e5f6
Revises: e39c96d4d538
Create Date: 2026-06-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from config.geography import all_entries

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e39c96d4d538"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    geographies = sa.table(
        "geographies",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
        sa.column("parent_id", sa.Integer),
    )

    entries = all_entries()

    for entry in entries:
        conn.execute(
            sa.insert(geographies).values(name=entry.name, kind=entry.kind, parent_id=None)
        )

    # Resolve parent_ids in a second pass by name lookup.
    rows = conn.execute(sa.select(geographies.c.id, geographies.c.name, geographies.c.kind)).fetchall()
    name_to_id: dict[tuple[str, str], int] = {(r.name, r.kind): r.id for r in rows}

    for entry in entries:
        if entry.parent is None:
            continue
        # parent can be a state (kind="state") or an lga (kind="lga"); try lga first then state.
        parent_id = name_to_id.get((entry.parent, "lga")) or name_to_id.get((entry.parent, "state"))
        if parent_id is None:
            continue
        conn.execute(
            sa.update(geographies)
            .where(geographies.c.name == entry.name)
            .where(geographies.c.kind == entry.kind)
            .values(parent_id=parent_id)
        )


def downgrade() -> None:
    op.execute("DELETE FROM geographies")
