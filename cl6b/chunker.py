# Rolling chunker using a gear-hash-like variant for content-defined chunking.
from typing import List, Tuple

# 256 pseudo-random 64-bit constants (deterministic)
_GEAR = [0] * 256
def _init():
    # Initialize with a simple LCG-based stream
    x = 0x243F6A8885A308D3
    for i in range(256):
        x = (x * 0x5851F42D4C957F2D + 0x14057B7EF767814F) & ((1<<64)-1)
        _GEAR[i] = x
_init()

def _mask(avg_size: int) -> int:
    p = 1
    while p < avg_size:
        p <<= 1
    return p - 1

def boundaries(data: bytes, min_size: int, avg_size: int, max_size: int) -> List[int]:
    n = len(data)
    if n == 0:
        return [0]
    cuts: List[int] = []
    mask = _mask(avg_size)
    pos = 0
    while pos < n:
        start = pos
        end = min(start + min_size, n)
        # prime hash on min_size region
        h = 0
        for i in range(start, end):
            h = ((h << 1) ^ _GEAR[data[i]]) & ((1<<64)-1)
        pos = end
        while pos < n and (pos - start) < max_size:
            b = data[pos]
            h = ((h << 1) ^ _GEAR[b]) & ((1<<64)-1)
            pos += 1
            if (pos - start) >= min_size and (h & mask) == 0:
                break
        cuts.append(pos)
    if cuts[-1] != n:
        cuts[-1] = n
    return cuts

def chunk_ranges(data: bytes, min_kib: int = 256, avg_kib: int = 512, max_kib: int = 1024) -> List[Tuple[int,int]]:
    min_size = min_kib * 1024
    avg_size = avg_kib * 1024
    max_size = max_kib * 1024
    cuts = boundaries(data, min_size, avg_size, max_size)
    ranges: List[Tuple[int,int]] = []
    prev = 0
    for c in cuts:
        ranges.append((prev, c - prev))
        prev = c
    return ranges
