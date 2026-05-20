
# CoreLang6 (CL6b) — SPEC v1.0.0

## Versioning
- SPEC version: **1.0.0**
- Container footer: offset indice (FT_INDEX) e sentinel finali invariati.
- Manifest: JSON con `files[]` (path, segments[cid]), opzione `capabilities`.
- Index: JSON `chunks[]` (cid, payload_start, orig_len, ...).

## Capabilities (manifest.capabilities)
- `codecs`: elenco (`zlib`, `store`, `zstd?`, `lz4?`)
- `chunk_kib`: {min, avg, max}
- `features`: es. ["toc-v1", "signed-toc", "hmac-fallback"]

## TOC v1
- `<container>.toc.json`: per ciascun `cid` → `payload_start`, `orig_len`, `codec`.
- `files[path]` → `total`, `cids[]`, `offsets[]` cumulativi.

## Compatibilità
- CL6b v1.0.0 deve leggere container creati con zlib/store; opzionali zstd/lz4 se disponibili.
- TOC è opzionale; quando presente, deve essere coerente con manifest/index.

## Integrità
- Facoltativa: firma Ed25519 dei file `manifest.json` e `*.toc.json`.
