import asyncio
import logging
import time

from pyrogram import Client
from redis.asyncio import Redis

from src.bot.modules.reminders import storage


_logger = logging.getLogger('reminders')
_loop_task: asyncio.Task | None = None


def ensure_loop(redis: Redis, client: Client) -> None:
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _loop_task = loop.create_task(_reminder_loop(redis, client))


async def start_reminder_loop(
    redis: Redis, client: Client
) -> None:
    """Public entry to start the loop at app boot."""
    ensure_loop(redis, client)


async def _fire(
    redis: Redis, client: Client, rid: str
) -> None:
    data = await storage.get(redis, rid)
    if data is not None:
        try:
            await client.send_message(
                chat_id=data['chat_id'],
                text=(
                    f'⏰ **Reminder #{rid}**\n'
                    f'{data.get("text", "")}'
                ),
                reply_to_message_id=data.get('reply_to'),
            )
        except Exception as e:
            _logger.warning(
                'Failed to send reminder %s: %s', rid, e
            )
    await storage.delete(redis, rid)


async def _reminder_loop(redis: Redis, client: Client):
    _logger.info('Reminder loop started')
    while True:
        try:
            now = int(time.time())
            for rid in await storage.pop_due(redis, now):
                await _fire(redis, client, rid)
        except Exception as e:
            _logger.exception('Reminder loop error: %s', e)
        await asyncio.sleep(5)
