"""Helpers for extracting per-scenario panels from combined map figures."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def split_scenario_panels(
    image_path,
    *,
    top_frac: float = 0.11,
    bottom_frac: float = 0.17,
    gap_frac: float = 0.012,
) -> list[Image.Image]:
    """
    Split a 1×3 matplotlib comparison PNG into three scenario panels.

    Margins are proportional so cropping works across DPI/export sizes.
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    top = int(height * top_frac)
    bottom = int(height * (1.0 - bottom_frac))
    panel_height = bottom - top

    gap = int(width * gap_frac)
    usable = width - 2 * gap
    panel_width = usable // 3

    panels: list[Image.Image] = []
    for i in range(3):
        left = gap + i * panel_width
        right = left + panel_width if i < 2 else width - gap
        panels.append(img.crop((left, top, right, top + panel_height)))

    return panels


def panel_to_bytes(panel: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = BytesIO()
    panel.save(buffer, format=fmt)
    return buffer.getvalue()
