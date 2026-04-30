from src.bot.afk import afk_router
from src.bot.ai import ai_router
from src.bot.fun import fun_router
from src.bot.info import info_router
from src.bot.interpreters import intrp_router
from src.bot.notes import notes_router
from src.bot.quote import quote_router

routers = [
    fun_router,
    intrp_router,
    ai_router,
    notes_router,
    afk_router,
    quote_router,
    info_router,
]
