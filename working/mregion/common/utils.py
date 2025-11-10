# mregion/common/utils.py
from __future__ import annotations

import time
import uuid
import hashlib
from pathlib import Path
from typing import Any, Tuple
import numpy as np
from PIL import Image, ImageOps

# Optional backends
try:
    import tifffile  # type: ignore
    HAVE_TIFFFILE = True
except Exception:
    tifffile = None  # type: ignore
    HAVE_TIFFFILE = False

try:
    import pyvips  # type: ignore
    HAVE_PYVIPS = True
except Exception:
    pyvips = None  # type: ignore
    HAVE_PYVIPS = False

# App constants (defaults if not overridden elsewhere)
APP_VERSION = "refactor"
RNG_SEED = 1337

def now_ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def unique_name(prefix: str, suffix: str) -> str:
    return f"{prefix}_{now_ts()}_{uuid.uuid4().hex[:8]}.{suffix}"

def unique_name_with_stem(prefix: str, stem: str, suffix: str) -> str:
    safe = Path(stem).stem
    return f"{prefix}_{safe}_{now_ts()}_{uuid.uuid4().hex[:8]}.{suffix}"

def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def _ensure_u8_rgb(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        a = arr.astype(np.float32)
        lo, hi = np.percentile(a, [1, 99])
        hi = max(hi, lo + 1.0)
        a = np.clip((a - lo) / (hi - 1e-6), 0, 1)
        g = (a * 255).astype(np.uint8)
        return np.stack([g, g, g], axis=-1)
    if arr.ndim == 3:
        if arr.shape[2] == 1:
            g = arr[..., 0]
            return _ensure_u8_rgb(g)
        if arr.shape[2] >= 3:
            x = arr[..., :3]
            if x.dtype != np.uint8:
                # normalize per-channel
                x = x.astype(np.float32)
                lo = np.percentile(x, 1, axis=(0,1))
                hi = np.percentile(x, 99, axis=(0,1))
                hi = np.maximum(hi, lo + 1.0)
                x = np.clip((x - lo) / (hi - lo), 0, 1)
                x = (x * 255).astype(np.uint8)
            return x
    # fallback
    x = arr.astype(np.uint8, copy=False)
    if x.ndim == 2:
        return np.stack([x, x, x], axis=-1)
    if x.ndim == 3 and x.shape[2] >= 3:
        return x[..., :3]
    raise ValueError("Unsupported array shape for RGB conversion: %r" % (arr.shape,))

def load_tiff(path: str | Path) -> np.ndarray:
    p = str(path)
    if HAVE_TIFFFILE:
        return tifffile.imread(p)  # type: ignore
    # PIL fallback
    with Image.open(p) as im:
        return np.array(im)

def to_display_rgb(arr: np.ndarray) -> np.ndarray:
    return _ensure_u8_rgb(arr)

def ensure_dir(p: Path) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)

# Qt-only helper (used in Annotate list views)
from PyQt6 import QtGui
def make_color_swatch(color: QtGui.QColor, size: int = 16) -> QtGui.QPixmap:  # type: ignore
    pm = QtGui.QPixmap(size, size)
    pm.fill(color)
    return pm

def load_tiff_preview(path: str | Path, max_side: int = 4096) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Load a large TIFF as a preview efficiently.

    Returns (preview_rgb, scale, (H, W)) where:
    - preview_rgb: uint8 HxWx3 array for fast display
    - scale: original_width / preview_width
    - (H, W): original image size

    Prefers pyvips (fast, tiled), then tifffile pyramid, else PIL thumbnail.
    """
    path = str(path)
    # pyvips path
    if HAVE_PYVIPS and pyvips is not None:
        img = pyvips.Image.new_from_file(path, access="sequential")
        W, H = img.width, img.height
        thumb = img.thumbnail_image(max_side)
        tw, th = thumb.width, thumb.height
        # Ensure 3 bands
        if thumb.bands == 1:
            thumb = thumb.bandjoin([thumb, thumb])  # to 2
            thumb = thumb.bandjoin([thumb[0]])      # to 3
        elif thumb.bands > 3:
            thumb = thumb.extract_band(0, n=3)
        mem = thumb.write_to_memory()
        arr = np.frombuffer(mem, dtype=np.uint8).reshape(th, tw, thumb.bands)
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        scale = (W / tw) if tw else 1.0
        return arr, float(scale), (H, W)
    # tifffile pyramid
    if HAVE_TIFFFILE and tifffile is not None:
        with tifffile.TiffFile(path) as tf:  # type: ignore
            page = tf.series[0]
            # series shape can be (H, W) or (H, W, C)
            if hasattr(page, "levels") and page.levels:
                # Pick closest level <= max_side
                best = page.levels[0]
                for lev in page.levels:
                    lw, lh = lev.shape[-1], lev.shape[-2]
                    if max(lw, lh) <= max_side:
                        best = lev
                        break
                arr = best.asarray()
                W, H = page.shape[-1], page.shape[-2]
            else:
                arr = page.asarray()
                W, H = page.shape[-1], page.shape[-2]
                im = Image.fromarray(_ensure_u8_rgb(arr))
                im.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
                arr = np.array(im, dtype=np.uint8)
            arr = _ensure_u8_rgb(arr)
            scale = (W / arr.shape[1]) if arr.shape[1] else 1.0
            return arr.astype(np.uint8, copy=False), float(scale), (H, W)
    # PIL fallback
    im = Image.open(path)
    W, H = im.size
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    arr = np.array(im, dtype=np.uint8)
    scale = (W / arr.shape[1]) if arr.shape[1] else 1.0
    return arr, float(scale), (H, W)
