"""add acl_grants table

Revision ID: 002
Revises: 001
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'acl_grants',
        sa.Column('user_id', sa.BigInteger(), primary_key=True),
        sa.Column('scope', sa.Text(), primary_key=True),
        sa.Column(
            'created_at',
            sa.Integer(),
            nullable=False,
            server_default=sa.text(
                "cast(strftime('%s', 'now') as integer)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_table('acl_grants')
