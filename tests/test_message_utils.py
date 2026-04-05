import unittest
from unittest.mock import AsyncMock

from pyrogram.enums import ParseMode

from src.bot.tools import utils


class EditOrSendAsTextFileTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_edits_short_message(self):
        msg = AsyncMock()
        text = 'short response'

        await utils.edit_or_send_as_text_file(msg, text)

        msg.edit.assert_awaited_once_with(
            text,
            parse_mode=ParseMode.HTML,
        )
        msg.reply_document.assert_not_awaited()

    async def test_sends_long_message_as_file(self):
        msg = AsyncMock()
        text = 'x' * (utils.MAX_TEXT_MESSAGE_LENGTH + 1)
        file_text = 'file payload'

        await utils.edit_or_send_as_text_file(
            msg,
            text,
            file_text=file_text,
            filename='answer.txt',
        )

        msg.edit.assert_awaited_once_with(
            '<b>Response is too long for Telegram.</b>\n'
            '<b>Sent as file:</b> <code>answer.txt</code>',
            parse_mode=ParseMode.HTML,
        )
        msg.reply_document.assert_awaited_once()

        document = msg.reply_document.await_args.kwargs[
            'document'
        ]
        self.assertEqual(document.name, 'answer.txt')
        self.assertEqual(
            document.getvalue(),
            file_text.encode('utf-8'),
        )
