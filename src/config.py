from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from os import path, getenv
from logging import getLogger
from redis.asyncio import Redis
import json


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
        env_nested_delimiter='__', env_file=getenv('ENV_FILE', None)
    )


@lru_cache
def get_config() -> Config:
    return Config()


def get_redis_engine(
    db_config: RedisSettings = get_config().redis,
) -> Redis:
    return Redis(
        host=db_config.host,
        port=db_config.port,
        db=db_config.name,
        password=db_config.password,
        username=db_config.user,
    )


class RuntimeSettings:
    def __init__(self, file_path: str = 'settings.json'):
        self.path = file_path
        self.logger = getLogger('RuntimeSettings')
        self.data = {}
        self.modified = path.getmtime(file_path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, m, **kwargs):
        self.data.update(m, **kwargs)

    def load(self):
        if not path.exists(self.path):
            return
        with open(self.path, 'r', encoding='utf-8') as fp:
            self.data = json.load(fp)

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as fp:
            json.dump(self.data, fp, ensure_ascii=False, indent=3)
