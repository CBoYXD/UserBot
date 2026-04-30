from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Chat(Base):
    __tablename__ = 'chats'

    chat_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    last_seen_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    memory_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    auto_reply_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='{}'
    )
