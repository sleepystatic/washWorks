"""Minimal PNG read/write plus ICO packing, stdlib only.

Exists so the brand asset pipeline (tools/build_assets.py) has no third-party
dependency. It handles exactly what the Wash Works source art needs:
non-interlaced 8-bit PNG in greyscale, RGB, palette or RGBA.
"""

import struct
import zlib

_SIG = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_rgba(path):
    """Decode a PNG to (width, height, bytearray of RGBA rows)."""
    data = open(path, "rb").read()
    if data[:8] != _SIG:
        raise ValueError(f"{path} is not a PNG")

    pos, idat, plte, trns = 8, bytearray(), None, None
    width = height = depth = color = None

    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise ValueError("interlaced PNG not supported")
            if depth != 8:
                raise ValueError(f"bit depth {depth} not supported")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"PLTE":
            plte = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IEND":
            break
        pos += 12 + length

    channels = _CHANNELS[color]
    raw = zlib.decompress(bytes(idat))
    bpp = channels
    stride = width * channels

    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    offset = 0

    for y in range(height):
        ftype = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride

        # Undo the per-scanline filter in place.
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        elif ftype != 0:
            raise ValueError(f"unknown filter type {ftype}")

        base = y * width * 4
        for x in range(width):
            i = x * channels
            o = base + x * 4
            if color == 6:
                out[o:o + 4] = line[i:i + 4]
            elif color == 2:
                out[o:o + 3] = line[i:i + 3]
                out[o + 3] = 255
            elif color == 3:
                idx = line[i]
                out[o] = plte[idx * 3]
                out[o + 1] = plte[idx * 3 + 1]
                out[o + 2] = plte[idx * 3 + 2]
                out[o + 3] = trns[idx] if trns and idx < len(trns) else 255
            elif color == 4:
                g = line[i]
                out[o] = out[o + 1] = out[o + 2] = g
                out[o + 3] = line[i + 1]
            else:
                g = line[i]
                out[o] = out[o + 1] = out[o + 2] = g
                out[o + 3] = 255
        prev = line

    return width, height, out


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def encode_rgba(width, height, rgba):
    """Encode RGBA bytes to a PNG byte string."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: None. The art is flat colour, so this compresses fine.
        raw += rgba[y * stride:(y + 1) * stride]

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (_SIG + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def write_rgba(path, width, height, rgba):
    with open(path, "wb") as fh:
        fh.write(encode_rgba(width, height, rgba))


def write_ico(path, entries):
    """Pack (size, png_bytes) pairs into an .ico.

    PNG-compressed entries are what every browser and Windows Vista+ expects.
    """
    count = len(entries)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    directory, blobs = b"", b""

    for size, blob in entries:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)

    with open(path, "wb") as fh:
        fh.write(header + directory + blobs)
