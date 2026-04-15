"""Generators for deterministic synthetic test images. Used by reference
detector tests so fixtures live as code rather than binary files.
"""
from __future__ import annotations

import numpy as np
import cv2
from PIL import Image


def make_coin_image(
    *, canvas: tuple[int, int] = (800, 600), diameter_px: int = 100,
    centre: tuple[int, int] | None = None, bg: int = 220,
) -> Image.Image:
    """White background with a filled dark grey circle simulating a coin."""
    w, h = canvas
    arr = np.full((h, w, 3), bg, dtype=np.uint8)
    cx, cy = centre if centre else (w // 2, h // 2)
    cv2.circle(arr, (cx, cy), diameter_px // 2, (80, 80, 80), thickness=-1)
    cv2.circle(arr, (cx, cy), diameter_px // 2 - 3, (120, 120, 120), thickness=2)
    return Image.fromarray(arr)


def make_card_image(
    *, canvas: tuple[int, int] = (1200, 800),
    card_long_px: int = 600, aspect: float = 85.6 / 54.0,
    centre: tuple[int, int] | None = None,
) -> Image.Image:
    """White background with a filled dark rectangle simulating a card.
    Default aspect matches ID-1 (1.586); pass 160/66 for a PH bill.
    """
    w, h = canvas
    arr = np.full((h, w, 3), 230, dtype=np.uint8)
    cx, cy = centre if centre else (w // 2, h // 2)
    short_px = int(card_long_px / aspect)
    x1 = cx - card_long_px // 2
    y1 = cy - short_px // 2
    x2 = x1 + card_long_px
    y2 = y1 + short_px
    cv2.rectangle(arr, (x1, y1), (x2, y2), (60, 60, 60), thickness=-1)
    return Image.fromarray(arr)


def make_bill_image(
    *, canvas: tuple[int, int] = (1600, 900), bill_long_px: int = 800,
    centre: tuple[int, int] | None = None,
) -> Image.Image:
    """PH banknote has aspect 160/66 = 2.424."""
    return make_card_image(
        canvas=canvas, card_long_px=bill_long_px, aspect=160.0 / 66.0,
        centre=centre,
    )


def make_aruco_image(
    *, canvas: tuple[int, int] = (800, 600), marker_id: int = 0,
    side_px: int = 200, centre: tuple[int, int] | None = None,
) -> Image.Image:
    """White background with a real ArUco DICT_4X4_50 marker."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, side_px)
    marker_rgb = cv2.cvtColor(marker, cv2.COLOR_GRAY2RGB)
    w, h = canvas
    arr = np.full((h, w, 3), 255, dtype=np.uint8)
    cx, cy = centre if centre else (w // 2, h // 2)
    x1 = cx - side_px // 2
    y1 = cy - side_px // 2
    arr[y1:y1 + side_px, x1:x1 + side_px] = marker_rgb
    return Image.fromarray(arr)


def make_noise_image(
    *, canvas: tuple[int, int] = (800, 600), seed: int = 0,
) -> Image.Image:
    """Random noise — simulates a photo with no reference object at all."""
    rng = np.random.default_rng(seed)
    w, h = canvas
    arr = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr)
