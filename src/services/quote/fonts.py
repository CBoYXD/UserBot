import os

from PIL import ImageFont

from src.services.quote.constants import FONT_CANDIDATES


_cache: dict[int, ImageFont.ImageFont] = {}


def get_font(size: int) -> ImageFont.ImageFont:
    cached = _cache.get(size)
    if cached is not None:
        return cached
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _cache[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _cache[size] = font
    return font
