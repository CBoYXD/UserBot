from ..config import RuntimeSettings
from .router import Router
from pyrogram import Client
from logging import getLogger


class Dispatcher:
    def __init__(
        self,
        client: Client,
        runtime_settings: RuntimeSettings,
        routers: list[Router],
        **dp_kwargs,
    ):
        self.__client = client
        self.__runtime_settings = runtime_settings
        self.__dp_kwargs = dp_kwargs
        self.__logger = getLogger('dispatcher')
        self.__routers = routers
        self.__exclude_handlers = set()
        self.__exclude_routers = set()

    def __get_available_routers(self) -> list[Router]:
        """
        Retrieves router handlers excluding a set 
        of handlers passed over self.__exclude_routers
        """
        if not bool(self.__exclude_routers):
            return self.__routers
        else:
            return [
                router
                for router in self.__routers
                if router.name not in self.__exclude_routers
            ]

    @property
    def logger(self):
        """Return dispatcher logger"""
        return self.__logger

    @property
    def dp_kwargs(self):
        return self.__dp_kwargs

    @property
    def runtime_settings(self):
        return self.__runtime_settings

    def register_routers(self) -> None:
        """Register all routers"""
        for router in self.__get_available_routers():
            router.dp_kwargs = dict(
                **self.__dp_kwargs,
                runtime_settings=self.__runtime_settings,
                dp=self,
            )
            for handler in router.get_handlers(
                self.__exclude_handlers
            ):
                self.__client.add_handler(*handler)

    def run(self) -> None:
        self.update_runtime_settings()
        self.register_routers()
        self.__client.run()

    def update_runtime_settings(self) -> None:
        self.__exclude_handlers = set(
            self.__runtime_settings.get('exclude_commands')
        )
        self.__exclude_routers = set(
            self.__runtime_settings.get('exclude_routers')
        )

    def restart(self) -> None:
        self.__client.stop()
        self.update_runtime_settings()
        self.register_routers()
        self.__client.run()
