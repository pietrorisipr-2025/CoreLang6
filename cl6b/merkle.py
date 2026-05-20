# Merkle tree with configurable fanout (default 1024). Leaves are raw digests (bytes).
from typing import List
from .hashing import hash_concat

def merkle_root(leaves: List[bytes], fanout: int = 1024) -> bytes:
    if not leaves:
        return b""
    level = leaves[:]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), fanout):
            chunk = level[i:i+fanout]
            # reduce chunk by pairwise folding
            acc = chunk[0]
            for c in chunk[1:]:
                acc = hash_concat(acc, c)
            nxt.append(acc)
        level = nxt
    return level[0]
