"""seed nigeria geography

Revision ID: f2a7c8d9e0b1
Revises: d4f7a1b2c3e8
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.config.nigeria_geography import NIGERIA_STATES_LGAS

revision: str = "f2a7c8d9e0b1"
down_revision: Union[str, None] = "d4f7a1b2c3e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("geographies", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_geography_name_kind", type_="unique")
        batch_op.create_unique_constraint(
            "uq_geography_name_kind_parent",
            ["name", "kind", "parent_id"],
        )

    conn = op.get_bind()
    geographies = sa.table(
        "geographies",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
        sa.column("parent_id", sa.Integer),
    )

    state_ids: dict[str, int] = {}
    for state in NIGERIA_STATES_LGAS:
        row = conn.execute(
            sa.select(geographies.c.id)
            .where(geographies.c.name == state)
            .where(geographies.c.kind == "state")
            .where(geographies.c.parent_id.is_(None))
        ).first()
        if row is None:
            conn.execute(sa.insert(geographies).values(name=state, kind="state", parent_id=None))
            row = conn.execute(
                sa.select(geographies.c.id)
                .where(geographies.c.name == state)
                .where(geographies.c.kind == "state")
                .where(geographies.c.parent_id.is_(None))
            ).one()
            state_ids[state] = int(row.id)
        else:
            state_ids[state] = int(row.id)

    for state, lgas in NIGERIA_STATES_LGAS.items():
        parent_id = state_ids[state]
        for lga in lgas:
            exists = conn.execute(
                sa.select(geographies.c.id)
                .where(geographies.c.name == lga)
                .where(geographies.c.kind == "lga")
                .where(geographies.c.parent_id == parent_id)
            ).first()
            if exists is None:
                conn.execute(
                    sa.insert(geographies).values(name=lga, kind="lga", parent_id=parent_id)
                )


def downgrade() -> None:
    conn = op.get_bind()
    state_names = tuple(state for state in NIGERIA_STATES_LGAS if state != "Akwa Ibom")
    conn.execute(
        sa.text(
            """
            DELETE FROM geographies
            WHERE kind = 'lga'
              AND parent_id IN (
                SELECT id FROM geographies
                WHERE kind = 'state' AND name IN :state_names
              )
            """
        ).bindparams(sa.bindparam("state_names", expanding=True)),
        {"state_names": state_names},
    )
    conn.execute(
        sa.text("DELETE FROM geographies WHERE kind = 'state' AND name IN :state_names").bindparams(
            sa.bindparam("state_names", expanding=True)
        ),
        {"state_names": state_names},
    )

    with op.batch_alter_table("geographies", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_geography_name_kind_parent", type_="unique")
        batch_op.create_unique_constraint("uq_geography_name_kind", ["name", "kind"])
