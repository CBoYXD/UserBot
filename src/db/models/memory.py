from __future__ import annotations

from sqlalchemy import (
    Float,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class MemorySummary(Base):
    __tablename__ = 'memory_summaries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    from_ts: Mapped[int | None] = mapped_column(Integer)
    to_ts: Mapped[int | None] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )


class MemoryFact(Base):
    __tablename__ = 'memory_facts'
    __table_args__ = (
        UniqueConstraint(
            'scope_type',
            'scope_id',
            'key',
            name='uq_memory_facts_scope_key',
        ),
        Index('idx_memory_facts_scope', 'scope_type', 'scope_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    created_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
