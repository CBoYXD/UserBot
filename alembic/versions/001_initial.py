"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chats',
        sa.Column('chat_id', sa.BigInteger(), primary_key=True),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('title', sa.Text()),
        sa.Column('username', sa.Text()),
        sa.Column('first_seen_at', sa.Integer(), nullable=False),
        sa.Column('last_seen_at', sa.Integer(), nullable=False),
        sa.Column(
            'memory_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='1',
        ),
        sa.Column(
            'auto_reply_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'metadata_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
    )

    op.create_table(
        'users',
        sa.Column('user_id', sa.BigInteger(), primary_key=True),
        sa.Column(
            'is_self',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'is_bot',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
        sa.Column('username', sa.Text()),
        sa.Column('first_name', sa.Text()),
        sa.Column('last_name', sa.Text()),
        sa.Column('first_seen_at', sa.Integer(), nullable=False),
        sa.Column('last_seen_at', sa.Integer(), nullable=False),
        sa.Column('profile_summary', sa.Text()),
        sa.Column(
            'metadata_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
    )

    op.create_table(
        'messages',
        sa.Column('chat_id', sa.BigInteger(), primary_key=True),
        sa.Column('message_id', sa.Integer(), primary_key=True),
        sa.Column('sender_user_id', sa.BigInteger()),
        sa.Column('sender_chat_id', sa.BigInteger()),
        sa.Column('reply_to_message_id', sa.Integer()),
        sa.Column('thread_id', sa.Integer()),
        sa.Column('date_ts', sa.Integer(), nullable=False),
        sa.Column('edit_date_ts', sa.Integer()),
        sa.Column('text', sa.Text()),
        sa.Column('caption', sa.Text()),
        sa.Column('normalized_text', sa.Text()),
        sa.Column('media_type', sa.Text()),
        sa.Column(
            'entities_json',
            sa.Text(),
            nullable=False,
            server_default='[]',
        ),
        sa.Column(
            'raw_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
        sa.Column('deleted_at', sa.Integer()),
        sa.Column(
            'facts_extracted',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
    )
    op.create_index(
        'idx_messages_pending_extraction',
        'messages',
        ['facts_extracted', 'date_ts'],
        sqlite_where=sa.text(
            "deleted_at IS NULL AND normalized_text != ''"
        ),
    )

    # FTS5 virtual table – must be raw SQL
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS message_fts
        USING fts5(
            chat_id UNINDEXED,
            message_id UNINDEXED,
            normalized_text
        )
        """
    )

    op.create_table(
        'memory_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scope_type', sa.Text(), nullable=False),
        sa.Column('scope_id', sa.Text(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('from_ts', sa.Integer()),
        sa.Column('to_ts', sa.Integer()),
        sa.Column('source_count', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
    )

    op.create_table(
        'memory_facts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scope_type', sa.Text(), nullable=False),
        sa.Column('scope_id', sa.Text(), nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(
            'confidence',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            'scope_type', 'scope_id', 'key',
            name='uq_memory_facts_scope_key',
        ),
    )
    op.create_index(
        'idx_memory_facts_scope',
        'memory_facts',
        ['scope_type', 'scope_id'],
    )

    op.create_table(
        'agent_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('trigger_message_id', sa.Integer()),
        sa.Column('action_type', sa.Text(), nullable=False),
        sa.Column('decision_json', sa.Text(), nullable=False),
        sa.Column(
            'result_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
    )

    op.create_table(
        'agent_traces',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trace_id', sa.Text(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('trigger_message_id', sa.Integer()),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column(
            'payload_json',
            sa.Text(),
            nullable=False,
            server_default='{}',
        ),
        sa.Column('created_at', sa.Integer(), nullable=False),
    )
    op.create_index(
        'idx_agent_traces_trace_id',
        'agent_traces',
        ['trace_id', 'id'],
    )
    op.create_index(
        'idx_agent_traces_chat_id',
        'agent_traces',
        ['chat_id', 'id'],
    )


def downgrade() -> None:
    op.drop_table('agent_traces')
    op.drop_table('agent_actions')
    op.drop_table('memory_facts')
    op.drop_table('memory_summaries')
    op.execute('DROP TABLE IF EXISTS message_fts')
    op.drop_table('messages')
    op.drop_table('users')
    op.drop_table('chats')
