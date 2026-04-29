from pyrogram import filters

from src.bot.tools.router import Router


notes_router = Router('notes')
notes_router.router_filters = filters.me
