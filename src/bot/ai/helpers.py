from html import escape

from pyrogram.types import Message


def extract_prompt(msg: Message) -> str:
    """Extract prompt text from message (after command).

    Returns the combined prompt for the AI: the user-typed text plus
    the replied-to message text (if any) as additional context.
    """
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    typed = parts[1].strip() if len(parts) >= 2 else ''
    reply_text = ''
    if msg.reply_to_message:
        reply_text = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    if typed and reply_text:
        return typed + '\n\n' + reply_text
    return typed or reply_text


def extract_display_prompt(msg: Message) -> str:
    """User-typed prompt only (no replied-to text), for display."""
    text = msg.text or ''
    parts = text.split(maxsplit=1)
    typed = parts[1].strip() if len(parts) >= 2 else ''
    if typed:
        return typed
    if msg.reply_to_message:
        return (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ''
        ).strip()
    return ''


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
