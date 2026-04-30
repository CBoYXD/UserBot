from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    is_self: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_bot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    last_seen_at: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    profile_summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(
        Text, nullable=False, default='{}'
    )
