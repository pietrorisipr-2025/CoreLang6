# Varint (unsigned) utilities — LEB128-like
def uvarint_encode(n: int) -> bytes:
    if n < 0:
        raise ValueError("uvarint cannot encode negative numbers")
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)

def uvarint_decode(data: bytes, offset: int = 0):
    shift = 0
    result = 0
    i = offset
    while i < len(data):
        b = data[i]
        result |= (b & 0x7F) << (shift)
        i += 1
        if (b & 0x80) == 0:
            return result, i
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")
    raise ValueError("incomplete varint")
