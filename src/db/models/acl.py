from __future__ import annotations

from sqlalchemy import BigInteger, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AclGrant(Base):
    __tablename__ = 'acl_grants'

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("cast(strftime('%s', 'now') as integer)"),
    )
