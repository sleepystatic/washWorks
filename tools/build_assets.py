"""Generate the Wash Works logo and favicon set from the supplied source PNG.

The client supplied three PNGs and no vector source (discovery item A-1). Two of
them are flat navy tiles with no alpha, so the only workable master is
washworks_logo_png.png: pure black artwork on transparency, which makes it a
clean alpha mask. Everything here is a recolour or a downsample of that mask, so
nothing is redrawn and nothing is guessed.

Run:  python tools/build_assets.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pnglite import read_rgba, encode_rgba, write_rgba, write_ico  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "brand-source", "washworks_logo_png.png")
LOGO_DIR = os.path.join(ROOT, "static", "img", "logo")
ICON_DIR = os.path.join(ROOT, "static", "favicon")

NAVY = (0, 50, 116)      # #003274, measured from the supplied navy artwork
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

ALPHA_FLOOR = 32         # below this a pixel counts as empty when measuring bands


# --------------------------------------------------------------------------
# measuring
# --------------------------------------------------------------------------

def ink_rows(width, height, rgba, step=3):
    """Ink coverage per row, sampled every `step` columns."""
    return [
        sum(1 for x in range(0, width, step) if rgba[(y * width + x) * 4 + 3] > ALPHA_FLOOR)
        for y in range(height)
    ]


def ink_cols(width, height, rgba, y0, y1, step=3):
    """Ink coverage per column within a row band."""
    return [
        sum(1 for y in range(y0, y1 + 1, step) if rgba[(y * width + x) * 4 + 3] > ALPHA_FLOOR)
        for x in range(width)
    ]


def extent(counts):
    hits = [i for i, c in enumerate(counts) if c > 0]
    if not hits:
        raise ValueError("no ink found")
    return hits[0], hits[-1]


def bands(rows, top, bottom, min_gap=20):
    """Split a row range into content bands separated by empty-row runs."""
    gaps, start = [], None
    for y in range(top, bottom + 1):
        if rows[y] == 0:
            if start is None:
                start = y
        elif start is not None:
            if y - start >= min_gap:
                gaps.append((start, y - 1))
            start = None

    out, cursor = [], top
    for a, b in gaps:
        out.append((cursor, a - 1))
        cursor = b + 1
    out.append((cursor, bottom))
    return out


# --------------------------------------------------------------------------
# transforming
# --------------------------------------------------------------------------

def crop(width, height, rgba, x0, y0, x1, y1):
    w, h = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(w * h * 4)
    for y in range(h):
        src = ((y + y0) * width + x0) * 4
        dst = y * w * 4
        out[dst:dst + w * 4] = rgba[src:src + w * 4]
    return w, h, out


def tint(width, height, rgba, rgb):
    """Recolour opaque pixels, leaving the alpha channel untouched.

    The source is a single-colour mask, so this is lossless -- edge antialiasing
    is carried entirely by alpha and survives the recolour intact.
    """
    r, g, b = rgb
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        out[i] = r
        out[i + 1] = g
        out[i + 2] = b
    return width, height, out


def resize(width, height, rgba, tw, th):
    """Area-averaged downsample.

    Alpha is averaged and RGB held constant. Because the artwork is one flat
    colour plus alpha, that is exactly equivalent to premultiplied averaging --
    and it sidesteps the dark-halo artefact you get from naively averaging
    straight RGBA.
    """
    r, g, b = rgba[0], rgba[1], rgba[2]
    out = bytearray(tw * th * 4)
    xs = [(x * width // tw, max((x + 1) * width // tw, x * width // tw + 1)) for x in range(tw)]

    for y in range(th):
        y0 = y * height // th
        y1 = max((y + 1) * height // th, y0 + 1)
        for x in range(tw):
            x0, x1 = xs[x]
            total = n = 0
            for sy in range(y0, y1):
                row = sy * width * 4
                for sx in range(x0, x1):
                    total += rgba[row + sx * 4 + 3]
                    n += 1
            o = (y * tw + x) * 4
            out[o] = r
            out[o + 1] = g
            out[o + 2] = b
            out[o + 3] = total // n
    return tw, th, out


def pad_square(width, height, rgba, size, coverage, ground=None):
    """Centre the art on a square canvas, scaled to `coverage` of the edge."""
    target = int(size * coverage)
    scale = min(target / width, target / height)
    sw, sh = max(1, round(width * scale)), max(1, round(height * scale))
    _, _, small = resize(width, height, rgba, sw, sh)

    if ground:
        gr, gg, gb = ground
        canvas = bytearray([gr, gg, gb, 255] * (size * size))
    else:
        canvas = bytearray(size * size * 4)

    ox, oy = (size - sw) // 2, (size - sh) // 2
    for y in range(sh):
        for x in range(sw):
            s = (y * sw + x) * 4
            a = small[s + 3]
            if not a:
                continue
            d = ((y + oy) * size + (x + ox)) * 4
            if ground:
                # Composite the mark over the ground so the result stays opaque.
                inv = 255 - a
                for c in range(3):
                    canvas[d + c] = (small[s + c] * a + canvas[d + c] * inv) // 255
                canvas[d + 3] = 255
            else:
                canvas[d:d + 4] = small[s:s + 4]
    return size, size, canvas


# --------------------------------------------------------------------------

def main():
    if not os.path.exists(SOURCE):
        sys.exit(f"missing source art: {SOURCE}")

    os.makedirs(LOGO_DIR, exist_ok=True)
    os.makedirs(ICON_DIR, exist_ok=True)

    width, height, rgba = read_rgba(SOURCE)
    print(f"source        {os.path.basename(SOURCE)}  {width}x{height}")

    rows = ink_rows(width, height, rgba)
    top, bottom = extent(rows)
    found = bands(rows, top, bottom)
    if len(found) < 2:
        sys.exit("could not separate the icon from the wordmark")

    labels = ["icon", "wordmark", "tagline"]
    for (a, b), label in zip(found, labels):
        print(f"  band {label:9s} y {a}..{b}")

    def trimmed(y0, y1):
        cols = ink_cols(width, height, rgba, y0, y1)
        x0, x1 = extent(cols)
        return crop(width, height, rgba, x0, y0, x1, y1)

    full = trimmed(top, bottom)
    icon = trimmed(*found[0])
    print(f"  full lockup   {full[0]}x{full[1]}")
    print(f"  icon only     {icon[0]}x{icon[1]}")

    # ---- full lockup, one file per ground it has to sit on -----------------
    for name, rgb in (("black", BLACK), ("white", WHITE), ("navy", NAVY)):
        w, h, px = tint(*full, rgb)
        write_rgba(os.path.join(LOGO_DIR, f"washworks-logo-{name}.png"), w, h, px)
        print(f"  wrote logo    washworks-logo-{name}.png")

    for name, rgb in (("black", BLACK), ("white", WHITE), ("navy", NAVY)):
        w, h, px = tint(*icon, rgb)
        write_rgba(os.path.join(LOGO_DIR, f"washworks-icon-{name}.png"), w, h, px)
        print(f"  wrote icon    washworks-icon-{name}.png")

    # ---- favicons ----------------------------------------------------------
    # The mark is 1.48:1, so in a square tab slot it can only ever be about
    # two-thirds height -- the thin roller treads and sparkles fall below one
    # pixel well before 16px. A solid navy ground carrying a white mark reads
    # as one confident shape at tab size, where navy hairlines on transparency
    # just dissolve into the browser chrome. See discovery item A-3: a
    # purpose-drawn small mark is still the real fix.
    white_icon = tint(*icon, WHITE)
    ico_entries = []
    for size in (16, 32, 48):
        w, h, px = pad_square(*white_icon, size, 0.86, ground=NAVY)
        ico_entries.append((size, encode_rgba(w, h, px)))
        write_rgba(os.path.join(ICON_DIR, f"favicon-{size}.png"), w, h, px)
    write_ico(os.path.join(ICON_DIR, "favicon.ico"), ico_entries)
    print("  wrote favicon favicon.ico (16/32/48) + PNG siblings")

    # iOS ignores transparency and composites on black, so this one gets a ground.
    w, h, px = pad_square(*white_icon, 180, 0.72, ground=NAVY)
    write_rgba(os.path.join(ICON_DIR, "apple-touch-icon.png"), w, h, px)
    print("  wrote favicon apple-touch-icon.png (180, navy ground)")

    for size in (192, 512):
        w, h, px = pad_square(*white_icon, size, 0.72, ground=NAVY)
        write_rgba(os.path.join(ICON_DIR, f"icon-{size}.png"), w, h, px)
        print(f"  wrote favicon icon-{size}.png")

    # Maskable icons get cropped to a platform-chosen shape; keep the mark well
    # inside the safe zone so nothing important is clipped.
    w, h, px = pad_square(*white_icon, 512, 0.52, ground=NAVY)
    write_rgba(os.path.join(ICON_DIR, "icon-maskable-512.png"), w, h, px)
    print("  wrote favicon icon-maskable-512.png")

    print("\ndone. A-1 still stands: these are traced from raster, so a vector")
    print("source from the original designer would still be an upgrade.")


if __name__ == "__main__":
    main()
