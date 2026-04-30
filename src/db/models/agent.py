from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AgentAction(Base):
    __tablename__ = 'agent_actions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    trigger_message_id: Mapped[int | None] = mapped_column(
        Integer
    )
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    decision_json: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    result_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='{}'
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )


class AgentTrace(Base):
    __tablename__ = 'agent_traces'
    __table_args__ = (
        Index('idx_agent_traces_trace_id', 'trace_id', 'id'),
        Index('idx_agent_traces_chat_id', 'chat_id', 'id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    trigger_message_id: Mapped[int | None] = mapped_column(
        Integer
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='{}'
    )
    created_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
