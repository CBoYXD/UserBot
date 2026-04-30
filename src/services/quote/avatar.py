import io

from PIL import Image, ImageDraw
from pyrogram import Client

from src.services.quote.constants import AVATAR_COLORS
from src.services.quote.fonts import get_font


def avatar_color_for(user_id: int | None) -> tuple:
    idx = (abs(user_id) % len(AVATAR_COLORS)) if user_id else 0
    return AVATAR_COLORS[idx]


def name_letters(user) -> str:
    first = getattr(user, 'first_name', '') or ''
    last = getattr(user, 'last_name', '') or ''
    if first and last:
        return (first[:1] + last[:1]).upper()
    src = first or getattr(user, 'username', '') or '?'
    words = src.split()
    if len(words) > 1:
        return (words[0][:1] + words[-1][:1]).upper()
    return (src[:1] or '?').upper()


def _diagonal_gradient(
    size: int, c1: tuple, c2: tuple
) -> Image.Image:
    """Cheap 2x2 -> NxN bilinear diagonal gradient."""
    src = Image.new('RGB', (2, 2))
    src.putpixel((0, 0), c1)
    mid = tuple(
        (a + b) // 2 for a, b in zip(c1, c2)
    )
    src.putpixel((1, 0), mid)
    src.putpixel((0, 1), mid)
    src.putpixel((1, 1), c2)
    return src.resize((size, size), Image.BILINEAR)


def _circle_mask(size: int) -> Image.Image:
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse(
        (0, 0, size - 1, size - 1), fill=255
    )
    return mask


def circle_avatar(img: Image.Image, size: int) -> Image.Image:
    img = img.convert('RGBA').resize(
        (size, size), Image.LANCZOS
    )
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), _circle_mask(size))
    return out


def initials_avatar(
    letters: str, size: int, colors: tuple
) -> Image.Image:
    base = _diagonal_gradient(size, colors[0], colors[1]).convert(
        'RGBA'
    )
    draw = ImageDraw.Draw(base)
    font_size = int(size * (0.38 if len(letters) > 1 else 0.48))
    font = get_font(font_size)
    bbox = font.getbbox(letters)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (
            (size - w) / 2 - bbox[0],
            (size - h) / 2 - bbox[1],
        ),
        letters,
        font=font,
        fill=(255, 255, 255),
    )
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(base, (0, 0), _circle_mask(size))
    return out


async def fetch_avatar_photo(
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


async def build_avatar(
    client: Client, user, size: int
) -> Image.Image:
    photo = await fetch_avatar_photo(client, user)
    if photo is not None:
        return circle_avatar(photo, size)
    return initials_avatar(
        name_letters(user),
        size,
        avatar_color_for(getattr(user, 'id', None)),
    )
