from pyrogram import filters

from src.bot.tools.router import Router


intrp_router = Router('intrp')
intrp_router.router_filters = filters.me
