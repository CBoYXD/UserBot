from asyncio import sleep

from pyrogram.errors import FloodWait
from pyrogram.types import Message

from src.core.acl import cmd
from src.core.router import Router


fun_router = Router('fun')


@fun_router.message(cmd('fun', 'type', 'тайп'))
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
            await sleep(e.value)


@fun_router.message(cmd('fun', 'spam', 'спам'))
async def spam_fun(msg: Message):
    if not bool(msg.reply_to_message):
        await msg.edit('Треба відповіддю на повідомлення')
        await sleep(3)
        await msg.delete()
    else:
        num = int(msg.text[5:].strip())
        await msg.delete()
        for _ in range(num):
            try:
                await msg.reply_text(
                    str(msg.reply_to_message.from_user.mention)
                )
            except FloodWait as e:
                await sleep(e.value)
