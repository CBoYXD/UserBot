from redis.asyncio import Redis

from src.services.codex import CodexClient


AI_MODEL_KEY = 'settings:ai:model'
AI_EFFORT_KEY = 'settings:ai:effort'
ALLOWED_EFFORTS = {
    'minimal',
    'low',
    'medium',
    'high',
    'xhigh',
}


async def get_ai_preferences(
    redis: Redis,
    codex: CodexClient,
) -> tuple[str, str, str, str]:
    raw_model = await redis.get(AI_MODEL_KEY)
    raw_effort = await redis.get(AI_EFFORT_KEY)

    model = (
        raw_model.decode('utf-8').strip()
        if raw_model
        else codex.model
    )
    effort = (
        raw_effort.decode('utf-8').strip().lower()
        if raw_effort
        else codex.reasoning_effort
    )

    if effort not in ALLOWED_EFFORTS:
        effort = codex.reasoning_effort

    model_source = 'redis' if raw_model else 'default'
    effort_source = 'redis' if raw_effort else 'default'
    return model, effort, model_source, effort_source
