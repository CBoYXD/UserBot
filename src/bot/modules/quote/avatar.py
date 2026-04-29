import io

from PIL import Image, ImageDraw
from pyrogram import Client

from src.bot.modules.quote.fonts import get_font


def circle_avatar(img: Image.Image, size: int) -> Image.Image:
    img = img.convert('RGBA').resize(
        (size, size), Image.LANCZOS
    )
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def initial_avatar(name: str, size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (60, 90, 130, 255))
    draw = ImageDraw.Draw(img)
    letter = (name or '?').strip()[:1].upper() or '?'
    font = get_font(int(size * 0.55))
    bbox = font.getbbox(letter)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        letter,
        font=font,
        fill=(240, 240, 240),
    )
    return circle_avatar(img, size)


async def fetch_avatar(
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
