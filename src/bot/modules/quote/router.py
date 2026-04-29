from pyrogram import filters

from src.bot.tools.router import Router


quote_router = Router('quote')
quote_router.router_filters = filters.me
