
"""
CL6 codecs plugin layer.
Provides `compress(codec, data, level)` and `decompress(codec, data)`.

Supported:
  - "zlib"      (stdlib)
  - "store"     (no compression)
  - "zstd"      (requires `zstandard` package) [optional]
  - "lz4"       (requires `lz4.frame` package) [optional]
"""
import zlib

class CodecError(Exception):
    """Raised when a requested codec is unavailable or errors occur."""
    pass

_zstd = None
_lz4f = None
try:
    import zstandard as _zstd  # type: ignore
except Exception:
    _zstd = None
try:
    import lz4.frame as _lz4f  # type: ignore
except Exception:
    _lz4f = None

def compress(codec: str, data: bytes, level: int = 6) -> bytes:
    c = codec.lower()
    if c in ("zlib", "deflate"):
        comp = zlib.compressobj(level, zlib.DEFLATED, -zlib.MAX_WBITS)
        return comp.compress(data) + comp.flush()
    if c == "store":
        return data
    if c == "zstd":
        if _zstd is None:
            raise CodecError("zstd non disponibile: installa il pacchetto `zstandard`")
        cctx = _zstd.ZstdCompressor(level=level)
        return cctx.compress(data)
    if c == "lz4":
        if _lz4f is None:
            raise CodecError("lz4 non disponibile: installa il pacchetto `lz4`")
        return _lz4f.compress(data, compression_level=level)
    raise ValueError(f"codec non supportato: {codec}")

def decompress(codec: str, data: bytes) -> bytes:
    c = codec.lower()
    if c in ("zlib", "deflate"):
        d = zlib.decompressobj(-zlib.MAX_WBITS)
        return d.decompress(data) + d.flush()
    if c == "store":
        return data
    if c == "zstd":
        if _zstd is None:
            raise CodecError("zstd non disponibile: installa il pacchetto `zstandard`")
        dctx = _zstd.ZstdDecompressor()
        return dctx.decompress(data)
    if c == "lz4":
        if _lz4f is None:
            raise CodecError("lz4 non disponibile: installa il pacchetto `lz4`")
        return _lz4f.decompress(data)
    raise ValueError(f"codec non supportato: {codec}")

def available():
    return {
        "zlib": True,
        "store": True,
        "zstd": _zstd is not None,
        "lz4": _lz4f is not None,
    }
