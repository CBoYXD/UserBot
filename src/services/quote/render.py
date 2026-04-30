import io

from PIL import Image, ImageDraw, ImageFont

from src.services.quote.bubble import draw_bubble
from src.services.quote.constants import (
    AVATAR_SIZE,
    BUBBLE_COLOR,
    GAP,
    INDENT,
    MAX_BUBBLE_W,
    MIN_BUBBLE_W,
    NAME_COLORS_DARK,
    NAME_SIZE,
    RADIUS,
    STICKER_MAX,
    SUPERSAMPLE,
    TAIL_SIZE,
    TEXT_COLOR,
    TEXT_SIZE,
)
from src.services.quote.fonts import get_font


def _name_color_for(user_id: int | None) -> tuple[int, int, int]:
    idx = abs(user_id) % len(NAME_COLORS_DARK) if user_id else 0
    return NAME_COLORS_DARK[idx]


def _wrap(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines() or ['']:
        if not raw:
            out.append('')
            continue
        cur = ''
        for word in raw.split(' '):
            cand = (cur + ' ' + word).strip() if cur else word
            bbox = font.getbbox(cand)
            if (bbox[2] - bbox[0]) <= max_w or not cur:
                cur = cand
            else:
                out.append(cur)
                cur = word
        if cur:
            out.append(cur)
    return out


def _measure(lines: list[str], font: ImageFont.FreeTypeFont) -> int:
    w = 0
    for line in lines:
        bbox = font.getbbox(line)
        w = max(w, bbox[2] - bbox[0])
    return w


def render_quote(
    name: str,
    text: str,
    avatar: Image.Image,
    user_id: int | None,
) -> bytes:
    name_font = get_font(NAME_SIZE)
    text_font = get_font(TEXT_SIZE)

    inner_max = MAX_BUBBLE_W - INDENT * 2
    name_lines = _wrap(name or '', name_font, inner_max)
    text_lines = _wrap(text or '', text_font, inner_max)

    name_w = _measure(name_lines, name_font)
    text_w = _measure(text_lines, text_font)
    inner_w = max(name_w, text_w, MIN_BUBBLE_W - INDENT * 2)
    bubble_w = inner_w + INDENT * 2

    name_line_h = NAME_SIZE + 6
    text_line_h = TEXT_SIZE + 6
    name_h = len(name_lines) * name_line_h if name else 0
    text_h = len(text_lines) * text_line_h if text else 0
    gap = INDENT // 2 if name and text else 0
    bubble_h = INDENT * 2 + name_h + gap + text_h

    avatar_block = AVATAR_SIZE + GAP
    canvas_w = avatar_block + bubble_w
    canvas_h = max(bubble_h, AVATAR_SIZE)

    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))

    bubble_img, tail_offset = draw_bubble(
        bubble_w,
        bubble_h,
        RADIUS,
        TAIL_SIZE,
        BUBBLE_COLOR,
        SUPERSAMPLE,
    )
    bubble_x = avatar_block
    bubble_y = canvas_h - bubble_h
    canvas.alpha_composite(
        bubble_img, (bubble_x - tail_offset, bubble_y)
    )

    avatar_y = canvas_h - AVATAR_SIZE
    canvas.alpha_composite(avatar, (0, avatar_y))

    draw = ImageDraw.Draw(canvas)
    text_x = bubble_x + INDENT
    cursor_y = bubble_y + INDENT

    if name:
        color = _name_color_for(user_id)
        for line in name_lines:
            draw.text(
                (text_x, cursor_y),
                line,
                font=name_font,
                fill=color,
            )
            cursor_y += name_line_h
        cursor_y += gap

    if text:
        for line in text_lines:
            draw.text(
                (text_x, cursor_y),
                line,
                font=text_font,
                fill=TEXT_COLOR,
            )
            cursor_y += text_line_h

    return _to_sticker_webp(canvas)


def _to_sticker_webp(img: Image.Image) -> bytes:
    img = _fit_to_sticker(img)
    out = io.BytesIO()
    img.save(out, format='WEBP', lossless=True)
    return out.getvalue()


def _fit_to_sticker(img: Image.Image) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest == STICKER_MAX:
        return img
    scale = STICKER_MAX / longest
    return img.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))),
        Image.LANCZOS,
    )
