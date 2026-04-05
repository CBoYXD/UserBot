from src.bot.modules.ai import ai_router
from src.bot.modules.fun import fun_router
from src.bot.modules.interpreters import intrp_router

routers = [fun_router, intrp_router, ai_router]
