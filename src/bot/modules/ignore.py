from ..tools.router import Router
from pyrogram import filters, types, Client
from redis.asyncio import Redis
from asyncio import sleep

ignore_router = Router('ignore_router')


@ignore_router.message(
    filters.me
    & (
        filters.command('ігнор', prefixes='!')
        | filters.command('ignore', prefixes='!')
    )
)
async def ignore_tags_in_group(msg: types.Message, redis: Redis):
    await redis.rpush('ignore_chats', msg.chat.id)
    await msg.edit('Successfully added')
    await redis.aclose()
    await sleep(5)
    await msg.delete()


@ignore_router.message(
    filters.me
    & (
        filters.command('анігнор', prefixes='!')
        | filters.command('unignore', prefixes='!')
    )
)
async def unignore_tags_in_group(msg: types.Message, redis: Redis):
    await redis.lrem('ignore_chats', 0, msg.chat.id)
    await msg.edit('Successfully deleted')
    await redis.aclose()
    await sleep(5)
    await msg.delete()


@ignore_router.message(
    filters.me
    & (
        filters.command('олл_ігнор', prefixes='!')
        | filters.command('all_ignore', prefixes='!')
    )
)
async def all_ignore_tags_in_group(msg: types.Message, redis: Redis):
    await msg.edit(
        str(
            [
                int(n)
                for n in await redis.lrange('ignore_chats', 0, -1)
            ]
        )
    )


@ignore_router.message(
    Router.tags_me_filter()
    & ignore_router.get_db_result(
        db_func=Redis.lrange,
        pyro_filter=filters.chat,
        map_filter_func=lambda result: [int(n) for n in result],
        db_kwargs=dict(name='ignore_chats', start=0, end=-1),
    )
)
async def ignore_chats(msg: types.Message, client: Client):
    await client.read_chat_history(msg.chat.id)
