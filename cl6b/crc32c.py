# Pure-Python CRC32C (Castagnoli) with precomputed table.
POLY = 0x1EDC6F41  # reflected

_TABLE = None

def _build_table():
    tbl = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLY
            else:
                crc >>= 1
        tbl.append(crc & 0xFFFFFFFF)
    return tuple(tbl)

def crc32c(data: bytes) -> int:
    global _TABLE
    if _TABLE is None:
        _TABLE = _build_table()
    crc = 0xFFFFFFFF
    for b in data:
        crc = (_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF
