from ..tools.router import Router
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from asyncio import sleep

fun_router = Router('fun')
fun_router.router_filters = filters.me


@fun_router.message(
    filters.command('тайп', prefixes='.')
    | filters.command('type', prefixes='.')
)
async def type_fun(msg: Message):
    orig_text = (
        msg.text.split(
            '.тайп' if '.тайп' in msg.text else '.type', maxsplit=1
        )[1]
    ).strip()
    text = orig_text
    tbp = ''
    typing_symbol = '▒'

    while tbp != orig_text:
        try:
            await msg.edit(tbp + typing_symbol)
            await sleep(0.05)

            tbp = tbp + text[0]
            text = text[1:]

            await msg.edit(tbp)
            await sleep(0.05)

        except FloodWait as e:
            await sleep(e.x)


@fun_router.message(
    filters.command('спам', prefixes='.')
    | filters.command('spam', prefixes='.')
)
async def spam_fun(msg: Message):
    num = int(msg.text[5:].strip())
    await msg.delete()
    try:
        for n in range(num):
            await msg.reply_text(str(n))
    except FloodWait as e:
        await sleep(e.x)
