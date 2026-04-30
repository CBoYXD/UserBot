import json
from functools import lru_cache
from logging import getLogger

from pydantic import BaseModel
from pydantic import Field
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


class OllamaSettings(BaseModel):
    base_url: str = 'http://127.0.0.1:11434'
    chat_model: str = 'qwen3:8b'
    embed_model: str = ''
    timeout: float = 120.0
    health_ttl: int = 20


class AgenticSettings(BaseModel):
    db_path: str = 'data/agentic.sqlite3'
    max_agent_steps: int = 3
    ingest_enabled: bool = True
    auto_reply_default: bool = False
    require_ollama: bool = True
    embeddings_enabled: bool = False
    recent_cache_size: int = 80
    search_limit: int = 12


class Config(BaseSettings):
    userbot: UserBotSettings
    redis: RedisSettings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    agentic: AgenticSettings = Field(default_factory=AgenticSettings)
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

    async def load(self):
        raw = await self.redis.get(self.key)
        if raw is None:
            self.data = {}
            return
        self.data = json.loads(raw.decode('utf-8'))

    async def save(self):
        await self.redis.set(
            self.key,
            json.dumps(
                self.data,
                ensure_ascii=False,
                indent=3,
            ),
        )
