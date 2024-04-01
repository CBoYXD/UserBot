from .fun import fun_router
from .ignore import ignore_router
from .interpreters import intrp_router

routers = [ignore_router, fun_router, intrp_router]
