from pathlib import Path

from PIL import ImageFont


FONT_PATH = Path(__file__).parent / 'assets' / 'Roboto.ttf'

_cache: dict[int, ImageFont.FreeTypeFont] = {}


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Return bundled Roboto at the requested size."""
    cached = _cache.get(size)
    if cached is not None:
        return cached
    font = ImageFont.truetype(str(FONT_PATH), size)
    _cache[size] = font
    return font
