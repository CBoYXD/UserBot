from pyrogram import filters

from src.bot.tools.router import Router


ai_router = Router('ai')
ai_router.router_filters = filters.me
