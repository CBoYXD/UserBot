import io

from PIL import Image, ImageDraw, ImageFont

from src.bot.modules.quote.avatar import circle_avatar, initial_avatar
from src.bot.modules.quote.fonts import get_font


CARD_W = 720
PAD = 24
AVATAR = 96
NAME_SIZE = 28
TEXT_SIZE = 26
BG = (24, 26, 32)
PANEL = (35, 39, 48)
NAME_COLOR = (110, 200, 255)
TEXT_COLOR = (230, 232, 236)


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


def render_quote(
    name: str,
    text: str,
    avatar: Image.Image | None,
) -> bytes:
    name_font = get_font(NAME_SIZE)
    text_font = get_font(TEXT_SIZE)

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

    avatar_img = (
        circle_avatar(avatar, AVATAR)
        if avatar is not None
        else initial_avatar(name, AVATAR)
    )
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
    return out.getvalue()
