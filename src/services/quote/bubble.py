import math

from PIL import Image, ImageDraw


def _arc_points(
    cx: float, cy: float, r: float, a0: float, a1: float, n: int
) -> list[tuple[float, float]]:
    return [
        (
            cx + r * math.cos(a0 + (a1 - a0) * i / n),
            cy + r * math.sin(a0 + (a1 - a0) * i / n),
        )
        for i in range(n + 1)
    ]


def _bezier_points(
    p0: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    p1: tuple[float, float],
    n: int,
) -> list[tuple[float, float]]:
    out = []
    for i in range(1, n + 1):
        t = i / n
        x = (
            (1 - t) ** 3 * p0[0]
            + 3 * (1 - t) ** 2 * t * c1[0]
            + 3 * (1 - t) * t ** 2 * c2[0]
            + t ** 3 * p1[0]
        )
        y = (
            (1 - t) ** 3 * p0[1]
            + 3 * (1 - t) ** 2 * t * c1[1]
            + 3 * (1 - t) * t ** 2 * c2[1]
            + t ** 3 * p1[1]
        )
        out.append((x, y))
    return out


def _bubble_polygon(
    w: float,
    h: float,
    r: float,
    tail: float,
    samples: int = 28,
) -> list[tuple[float, float]]:
    """Replicate canvas bubblePath: rounded rect with optional bottom-left tail."""
    if w < 2 * r:
        r = w / 2
    if h < 2 * r:
        r = h / 2

    pts: list[tuple[float, float]] = []
    pts.append((r, 0))
    pts += _arc_points(w - r, r, r, -math.pi / 2, 0, samples)
    pts += _arc_points(w - r, h - r, r, 0, math.pi / 2, samples)

    if tail > 0:
        pts.append((-tail, h))
        pts += _bezier_points(
            (-tail, h),
            (-tail * 0.4, h),
            (0, h - r * 0.3),
            (0, h - r),
            samples,
        )
    else:
        pts += _arc_points(
            r, h - r, r, math.pi / 2, math.pi, samples
        )

    pts += _arc_points(
        r, r, r, math.pi, math.pi * 1.5, samples
    )
    return pts


def draw_bubble(
    width: int,
    height: int,
    radius: int,
    tail: int,
    fill: tuple[int, int, int, int],
    supersample: int = 2,
) -> tuple[Image.Image, int]:
    """Render bubble and return (image, tail_offset)."""
    extra_left = math.ceil(tail * 0.8) if tail > 0 else 0
    canvas_w = (width + extra_left) * supersample
    canvas_h = height * supersample
    img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pts = _bubble_polygon(width, height, radius, tail)
    pts = [
        (
            (x + extra_left) * supersample,
            y * supersample,
        )
        for x, y in pts
    ]
    draw.polygon(pts, fill=fill)

    if supersample > 1:
        img = img.resize(
            (width + extra_left, height), Image.LANCZOS
        )
    return img, extra_left
