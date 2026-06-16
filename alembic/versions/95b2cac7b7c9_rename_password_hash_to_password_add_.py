"""rename password_hash to password, add account_type and admins table

Revision ID: 95b2cac7b7c9
Revises: d4f7a1b2c3e8
Create Date: 2026-06-16 12:05:33.109294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '95b2cac7b7c9'
down_revision: Union[str, None] = 'd4f7a1b2c3e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('can_manage_embed_keys', sa.Boolean(), nullable=False),
    sa.Column('permissions', sa.String(length=256), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # Rename password_hash -> password while preserving existing hashes, and add
    # the polymorphic discriminator. Done in two steps so existing rows satisfy
    # the NOT NULL constraints (SQLite can't add NOT NULL columns to a populated
    # table without a default).
    op.add_column('users', sa.Column('password', sa.String(length=128), nullable=True))
    op.add_column('users', sa.Column('account_type', sa.Enum('User', 'Admin', name='account_type'), nullable=False, server_default='User'))
    op.execute("UPDATE users SET password = password_hash")
    with op.batch_alter_table('users') as batch:
        batch.alter_column('password', existing_type=sa.String(length=128), nullable=False)
        batch.alter_column('account_type', server_default=None, existing_type=sa.Enum('User', 'Admin', name='account_type'), existing_nullable=False)
        batch.drop_column('password_hash')


def downgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.VARCHAR(length=128), nullable=True))
    op.execute("UPDATE users SET password_hash = password")
    with op.batch_alter_table('users') as batch:
        batch.alter_column('password_hash', existing_type=sa.VARCHAR(length=128), nullable=False)
        batch.drop_column('account_type')
        batch.drop_column('password')
    op.drop_table('admins')
