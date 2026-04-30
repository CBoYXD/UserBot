from html import escape

from pyrogram.types import Message


def extract_prompt(msg: Message) -> str:
    """Extract prompt text from message (after command)."""
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        if msg.reply_to_message:
            return msg.reply_to_message.text or ''
        return ''
    prompt = parts[1].strip()
    if msg.reply_to_message and msg.reply_to_message.text:
        prompt += '\n\n' + msg.reply_to_message.text
    return prompt


def build_ai_response(
    *,
    prompt_title: str,
    prompt: str,
    response: str,
) -> tuple[str, str]:
    html_text = (
        f'<b>{escape(prompt_title)}:</b> {escape(prompt)}\n\n'
        f'<b>AI:</b>\n{escape(response)}'
    )
    plain_text = (
        f'{prompt_title}:\n{prompt}\n\n'
        f'AI:\n{response}'
    )
    return html_text, plain_text
