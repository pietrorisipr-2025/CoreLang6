# CL6 Spec v0.7 (short)
- Container: sequence of frames + trailing footer `CL6BIDX` + u64le index_frame_start.
- Frames:
  - 0x01 MANIFEST (UTF-8 JSON) — includes files[], chunks[], profiles[], security{}.
  - 0x02 CHUNK — payload: [32B CID][1B codec][uvarint orig_len][uvarint comp_len][data].
  - 0x10 INDEX  — JSON with per-chunk {cid, codec, orig_len, comp_len, frame_start, payload_start, frame_end}.
- Codecs: none(0), zlib(1), zstd(2)*, lz4(3)* (*opzionali, richiedono librerie).
- Integrity: per-chunk content CID (BLAKE3/sha256 upstream), container framing CRC in ioframes, Merkle root in manifest.
- Signatures: `security.signatures[]` with HS256; ed25519 previsto (se librerie disponibili).

- Plugin codec: zstd/lz4 opzionali via modulo Python o binari di sistema.
