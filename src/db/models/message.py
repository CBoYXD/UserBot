from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Message(Base):
    __tablename__ = 'messages'
    __table_args__ = (
        Index(
            'idx_messages_pending_extraction',
            'facts_extracted',
            'date_ts',
            sqlite_where='deleted_at IS NULL'
            " AND normalized_text != ''",
        ),
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    message_id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    sender_user_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        Integer
    )
    thread_id: Mapped[int | None] = mapped_column(Integer)
    date_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    edit_date_ts: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(Text)
    entities_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='[]'
    )
    raw_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='{}'
    )
    deleted_at: Mapped[int | None] = mapped_column(Integer)
    facts_extracted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
