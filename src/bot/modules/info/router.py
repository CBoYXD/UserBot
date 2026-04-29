from pyrogram import filters

from src.bot.tools.router import Router


info_router = Router('info')
info_router.router_filters = filters.me

HTTP_TIMEOUT = 10.0
