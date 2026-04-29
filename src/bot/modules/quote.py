import io
import os
from html import escape

from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from src.bot.tools.router import Router


quote_router = Router('quote')
quote_router.router_filters = filters.me

CARD_W = 720
PAD = 24
AVATAR = 96
NAME_SIZE = 28
TEXT_SIZE = 26
BG = (24, 26, 32)
PANEL = (35, 39, 48)
NAME_COLOR = (110, 200, 255)
TEXT_COLOR = (230, 232, 236)
META_COLOR = (140, 144, 152)


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/Library/Fonts/Arial.ttf',
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or ['']:
        if not raw_line:
            lines.append('')
            continue
        words = raw_line.split(' ')
        cur = ''
        for w in words:
            candidate = (cur + ' ' + w).strip() if cur else w
            bbox = font.getbbox(candidate)
            width = bbox[2] - bbox[0]
            if width <= max_width or not cur:
                cur = candidate
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def _circle_avatar(img: Image.Image, size: int) -> Image.Image:
    img = img.convert('RGBA').resize(
        (size, size), Image.LANCZOS
    )
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


async def _fetch_avatar(
    client: Client, user
) -> Image.Image | None:
    if user is None or not getattr(user, 'photo', None):
        return None
    try:
        buf = await client.download_media(
            user.photo.big_file_id, in_memory=True
        )
        if buf is None:
            return None
        if isinstance(buf, str):
            with open(buf, 'rb') as f:
                data = f.read()
        else:
            data = buf.getvalue()
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


def _initial_avatar(name: str, size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (60, 90, 130, 255))
    draw = ImageDraw.Draw(img)
    letter = (name or '?').strip()[:1].upper() or '?'
    font = _font(int(size * 0.55))
    bbox = font.getbbox(letter)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        letter,
        font=font,
        fill=(240, 240, 240),
    )
    return _circle_avatar(img, size)


def _render_quote(
    name: str,
    text: str,
    avatar: Image.Image | None,
) -> bytes:
    name_font = _font(NAME_SIZE)
    text_font = _font(TEXT_SIZE)

    text_x = PAD + AVATAR + PAD
    text_max = CARD_W - text_x - PAD
    lines = _wrap_text(text or ' ', text_font, text_max)
    line_h = TEXT_SIZE + 6
    text_block_h = max(len(lines), 1) * line_h
    height = max(
        AVATAR + PAD * 2,
        PAD + NAME_SIZE + 12 + text_block_h + PAD,
    )

    img = Image.new('RGBA', (CARD_W, height), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (PAD - 8, PAD - 8, CARD_W - PAD + 8, height - PAD + 8),
        radius=18,
        fill=PANEL,
    )

    if avatar is None:
        avatar_img = _initial_avatar(name, AVATAR)
    else:
        avatar_img = _circle_avatar(avatar, AVATAR)
    img.paste(avatar_img, (PAD, PAD), avatar_img)

    draw.text(
        (text_x, PAD),
        name or '',
        font=name_font,
        fill=NAME_COLOR,
    )
    y = PAD + NAME_SIZE + 12
    for line in lines:
        draw.text(
            (text_x, y),
            line,
            font=text_font,
            fill=TEXT_COLOR,
        )
        y += line_h

    out = io.BytesIO()
    img.convert('RGB').save(
        out, format='PNG', optimize=True
    )
    out.seek(0)
    out.name = 'quote.png'
    return out.getvalue()


@quote_router.message(
    filters.command(['q', 'quote'], prefixes='.')
)
async def quote_cmd(msg: Message, client: Client):
    target = msg.reply_to_message
    if target is None:
        await msg.edit(
            '<b>Usage:</b> reply to a message with '
            '<code>.q</code>.',
            parse_mode=ParseMode.HTML,
        )
        return

    text = (target.text or target.caption or '').strip()
    if not text:
        await msg.edit(
            '<b>Quote:</b> message has no text.',
            parse_mode=ParseMode.HTML,
        )
        return

    user = target.from_user
    if user is not None:
        name = (
            (user.first_name or '')
            + (' ' + user.last_name if user.last_name else '')
        ).strip() or (user.username or 'User')
    else:
        name = getattr(target.sender_chat, 'title', 'Channel')

    try:
        avatar = await _fetch_avatar(client, user)
        png = _render_quote(name, text, avatar)
        bio = io.BytesIO(png)
        bio.name = 'quote.png'
        await msg.delete()
        await client.send_photo(
            chat_id=msg.chat.id,
            photo=bio,
            reply_to_message_id=target.id,
        )
    except Exception as e:
        await msg.edit(
            f'<b>Quote error:</b> <code>{escape(str(e))}</code>',
            parse_mode=ParseMode.HTML,
        )
