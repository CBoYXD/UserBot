import asyncio
import json
from functools import lru_cache
from logging import getLogger

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis


class UserBotSettings(BaseModel):
    api_id: int
    api_hash: str


class RedisSettings(BaseModel):
    name: str
    host: str
    port: int
    user: str
    password: str


class Config(BaseSettings):
    userbot: UserBotSettings
    redis: RedisSettings
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
    )


@lru_cache
def get_config() -> Config:
    return Config()


def get_redis_engine(
    db_config: RedisSettings | None = None,
) -> Redis:
    if db_config is None:
        db_config = get_config().redis
    return Redis(
        host=db_config.host,
        port=db_config.port,
        db=db_config.name,
        password=db_config.password,
        username=db_config.user,
    )


class RuntimeSettings:
    def __init__(
        self,
        redis: Redis,
        key: str = 'settings:runtime',
    ):
        self.redis = redis
        self.key = key
        self.logger = getLogger('RuntimeSettings')
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, m, **kwargs):
        self.data.update(m, **kwargs)

    def load(self):
        raw = asyncio.run(self.redis.get(self.key))
        if raw is None:
            self.data = {}
            return
        self.data = json.loads(raw.decode('utf-8'))

    def save(self):
        asyncio.run(
            self.redis.set(
                self.key,
                json.dumps(
                    self.data,
                    ensure_ascii=False,
                    indent=3,
                ),
            )
        )
