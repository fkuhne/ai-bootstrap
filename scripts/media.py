"""Test media built with the standard library alone: a red square and a pure tone."""

import io
import math
import struct
import wave
import zlib


def red_square_png(size: int = 128) -> bytes:
    """A solid red PNG, built by hand so no imaging library is needed."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    row = b"\x00" + b"\xff\x00\x00" * size  # filter type 0, then RGB pixels
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )


def tone_wav(seconds: float = 1.0, frequency: float = 440.0, rate: int = 16000) -> bytes:
    """A pure tone as a 16-bit mono WAV."""
    samples = (
        int(12000 * math.sin(2 * math.pi * frequency * i / rate))
        for i in range(int(seconds * rate))
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return buffer.getvalue()
