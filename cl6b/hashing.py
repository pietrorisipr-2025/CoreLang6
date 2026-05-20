# Hash helpers: prefer BLAKE3-256; fallback to SHA-256 if blake3 module is unavailable.
import hashlib
try:
    import blake3  # type: ignore
    _HAS_BLAKE3 = True
except Exception:
    blake3 = None
    _HAS_BLAKE3 = False

def cid_bytes(data: bytes) -> bytes:
    if _HAS_BLAKE3:
        return blake3.blake3(data).digest()
    else:
        # Fallback: SHA-256 (NOTE: not BLAKE3 — replace in production)
        return hashlib.sha256(data).digest()

def cid_hex(data: bytes) -> str:
    return cid_bytes(data).hex()

def hash_concat(left: bytes, right: bytes) -> bytes:
    if _HAS_BLAKE3:
        h = blake3.blake3()
        h.update(left); h.update(right)
        return h.digest()
    else:
        h = hashlib.sha256()
        h.update(left); h.update(right)
        return h.digest()
