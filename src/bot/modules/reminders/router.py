from pyrogram import filters

from src.bot.tools.router import Router


reminders_router = Router('reminders')
reminders_router.router_filters = filters.me
