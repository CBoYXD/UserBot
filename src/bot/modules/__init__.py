from src.bot.modules.afk import afk_router
from src.bot.modules.ai import ai_router
from src.bot.modules.fun import fun_router
from src.bot.modules.info import info_router
from src.bot.modules.interpreters import intrp_router
from src.bot.modules.notes import notes_router
from src.bot.modules.quote import quote_router
from src.bot.modules.reminders import reminders_router

routers = [
    fun_router,
    intrp_router,
    ai_router,
    notes_router,
    reminders_router,
    afk_router,
    quote_router,
    info_router,
]
