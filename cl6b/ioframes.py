# Minimal frame IO: [type u8][len varint][crc32c u32][payload]
import struct
from typing import Iterator, BinaryIO, Tuple
from .util import uvarint_encode, uvarint_decode
from .crc32c import crc32c

class Frame:
    __slots__ = ("ftype","payload")
    def __init__(self, ftype: int, payload: bytes):
        self.ftype = ftype & 0xFF
        self.payload = payload

def write_frame(fp: BinaryIO, ftype: int, payload: bytes) -> None:
    fp.write(bytes([ftype & 0xFF]))
    l = uvarint_encode(len(payload))
    fp.write(l)
    crc = crc32c(payload)
    fp.write(struct.pack("<I", crc))
    fp.write(payload)

def write_frame_ex(fp: BinaryIO, ftype: int, payload: bytes) -> Tuple[int,int,int]:
    """Write frame and return (frame_start_offset, payload_start_offset, frame_end_offset)."""
    frame_start = fp.tell()
    fp.write(bytes([ftype & 0xFF]))
    l = uvarint_encode(len(payload))
    fp.write(l)
    crc = crc32c(payload)
    fp.write(struct.pack("<I", crc))
    payload_start = fp.tell()
    fp.write(payload)
    end = fp.tell()
    return frame_start, payload_start, end

def read_frames(fp: BinaryIO) -> Iterator[Frame]:
    while True:
        b = fp.read(1)
        if not b:
            return
        ftype = b[0]
        vbuf = bytearray()
        while True:
            c = fp.read(1)
            if not c:
                raise EOFError("truncated varint")
            vbuf += c
            if (c[0] & 0x80) == 0:
                break
        length, _ = uvarint_decode(bytes(vbuf), 0)
        crc_raw = fp.read(4)
        if len(crc_raw) != 4:
            raise EOFError("truncated crc")
        (crc_read,) = struct.unpack("<I", crc_raw)
        payload = fp.read(length)
        if len(payload) != length:
            raise EOFError("truncated payload")
        if crc32c(payload) != crc_read:
            raise ValueError("CRC32C mismatch")
        yield Frame(ftype, payload)
