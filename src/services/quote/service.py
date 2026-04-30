from pyrogram import Client
from pyrogram.types import Message

from src.services.quote.avatar import build_avatar
from src.services.quote.constants import AVATAR_SIZE
from src.services.quote.render import render_quote


class QuoteService:
    async def render_for_message(
        self, client: Client, target: Message
    ) -> bytes:
        name = self._display_name(target)
        text = (target.text or target.caption or '').strip()
        user = target.from_user or target.sender_chat
        user_id = getattr(user, 'id', None)
        avatar = await build_avatar(client, user, AVATAR_SIZE)
        return render_quote(name, text, avatar, user_id)

    @staticmethod
    def _display_name(target: Message) -> str:
        user = target.from_user
        if user is not None:
            full = (
                (user.first_name or '')
                + (
                    ' ' + user.last_name
                    if user.last_name
                    else ''
                )
            ).strip()
            return full or user.username or 'User'
        return getattr(target.sender_chat, 'title', 'Channel')
