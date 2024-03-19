from typing import Awaitable, Optional, Callable
from logging import Logger, getLogger
import inspect
from functools import wraps
from pyrogram import handlers, Client
from pyrogram.types import Update
from pyrogram.filters import Filter, Message, AndFilter
from pyrogram.filters import create as create_filter
from redis.asyncio import Redis


class Router:
    def __init__(self, name):
        self.__name: str = name
        self.__logger: Logger = getLogger(name)
        self.__handlers: list = []
        self.__dp_kwargs: dict = {}
        self.__router_filters: Filter = None

    def __check_filters(self, filters) -> AndFilter:
        """
        Check filters
        Because value & None returns error
        """
        match self.__router_filters:
            case None:
                return filters
            case _:
                match filters:
                    case None:
                        return self.__router_filters
                    case _:
                        return self.__router_filters & filters

    @property
    def logger(self) -> Logger:
        """Return the router logger"""
        return self.__logger

    @property
    def name(self) -> str:
        return self.__name

    @property
    def redis(self) -> Redis:
        redis = self.dp_kwargs.get('redis')
        if redis is not None:
            return redis
        else:
            raise AttributeError('No Redis in dp_kwargs')

    @staticmethod
    def tags_me_filter() -> Filter:
        """
        Filters the message, returns True if the message is a tag to the client
        """

        async def func(ftl, client: Client, msg: Message) -> bool:
            return (
                (
                    not msg.outgoing
                )  # returns True, if message incomming to client
                and (
                    (msg.mentioned)
                    # returns True if message is mention
                    or (
                        bool(
                            msg.reply_to_message_id
                        )  # return True if message is reply
                        and (
                            (
                                msg.reply_to_message.from_user.id
                                if (
                                    msg.reply_to_message.from_user.id
                                    is not None
                                    if (
                                        (
                                            msg.reply_to_message.from_user
                                            is not None
                                        )
                                        if (
                                            msg.reply_to_message
                                            is not None
                                        )
                                        else False  # return False if message doesn`t have msg.reply_to_message
                                    )
                                    else False  # return False if message doesn`t have msg.reply_to_message.from_user
                                )
                                else None  # returns None, if all condidions above are False
                            )
                            == client.me.id  # returns True if the user who was replied to is you
                        )
                    )  # returns True if 2 conditions above are True
                )  # returns True if one of conditions above are True
            )  # returns True if 2 conditions above are True

        return create_filter(func, name='tags_me_filter')

    @property
    def dp_kwargs(self) -> dict:
        return self.__dp_kwargs

    @dp_kwargs.setter
    def dp_kwargs(self, kwargs: dict):
        self.__dp_kwargs = kwargs

    @property
    def router_filters(self, user_filter) -> Filter:
        return self.__router_filters

    @router_filters.setter
    def router_filters(self, value) -> None:
        self.__router_filters = value

    def get_db_result(
        self,
        db_func: Awaitable,
        pyro_filter: Callable,
        map_filter_func: Optional[Callable] = None,
        pyro_kwargs: Optional[dict] = None,
        db_kwargs: Optional[dict] = None,
    ) -> Filter:
        """
        Filter messages by param pyro_filter and db_result
        """

        async def func(flt, client: Client, update: Update) -> bool:
            pyro_kwargs = (
                flt.pyro_kwargs if flt.pyro_kwargs is not None else {}
            )
            db_kwargs = (
                flt.db_kwargs if flt.db_kwargs is not None else {}
            )
            db_result = await flt.db_func(
                self=self.redis, **db_kwargs
            )
            db_result = (
                flt.map_filter_func(db_result)
                if flt.map_filter_func is not None
                else db_result
            )
            return pyro_filter(db_result, **pyro_kwargs)

        return create_filter(
            func,
            name='db_filter',
            db_func=staticmethod(db_func),
            pyro_filter=pyro_filter,
            map_filter_func=staticmethod(map_filter_func),
            pyro_kwargs=pyro_kwargs,
            db_kwargs=db_kwargs,
        )

    @staticmethod
    def prepare_kwargs(func: Callable, kwargs: dict) -> dict:
        """
        Give only needed for function kwargs
        """
        spec = inspect.getfullargspec(func)

        if spec.varkw:
            return kwargs

        return {
            k: v
            for k, v in kwargs.items()
            if k in spec.args or k in spec.kwonlyargs
        }

    def inject(self, fn: Callable) -> Callable:
        """
        Prepare handler
        """

        @wraps(fn)
        async def wrapper(client: Client, update: Update):
            kwargs = self.dp_kwargs
            kwargs.update({'client': client, 'logger': self.logger})

            return await fn(update, **self.prepare_kwargs(fn, kwargs))

        return wrapper

    def message(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.MessageHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def edited_message(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.EditedMessageHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def deleted_messages(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.DeletedMessagesHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def callback_query(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.CallbackQueryHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )
            return func

        return decorator

    def inline_query(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.InlineQueryHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def chosen_inline_result(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.ChosenInlineResultHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def chat_member_updated(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.ChatMemberUpdatedHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def user_status(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.UserStatusHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def poll(
        self, filters: Filter = None, group: int = 0
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (
                    handlers.PollHandler(
                        func, self.__check_filters(filters)
                    ),
                    group,
                )
            )

            return func

        return decorator

    def disconnect(self) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(handlers.DisconnectHandler(func))

            return func

        return decorator

    def raw_update(self, group: int = 0) -> Callable:
        def decorator(func: Callable) -> Callable:
            func = self.inject(func)
            self.__handlers.append(
                (handlers.RawUpdateHandler(func), group)
            )

            return func

        return decorator

    def get_handlers(self, exclude_handlers: set):
        """
        Retrieves router handlers excluding a set
        of handlers passed over exclude_handlers
        """
        if exclude_handlers is None:
            return self.__handlers
        else:
            return [
                handler
                for handler in self.__handlers
                if handler[0].callback.__name__
                not in exclude_handlers
            ]
