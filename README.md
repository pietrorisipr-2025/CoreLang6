# CoreLang6 (CL6)

**Packaging, distribution, and verifiable delivery of large binary artifacts** (datasets, ML models, corpora, indexes, logical backups) with:

- **Content-Defined Chunking (CDC)** to maximize reuse across versions
- **TOC v2** for **O(1)** partial extraction (chunk-level random access)
- **Verifiable integrity** (SHA-256 per chunk/file + global Merkle root)
- Optional **signing** (Ed25519; HMAC fallback)

> Practical goal: **transfer only the bytes that changed**, verify them automatically, and extract just what you need without downloading everything.

---

## The problem it solves

You have **10 GB** of data and update **3%**. With a traditional archive you often re-ship **10 GB**.

With CL6 you can typically ship **~300 MB** of delta (case-dependent), verify integrity **chunk-by-chunk**, and extract only a file (or a byte range of a file) without touching the rest.

**Before:** upload 10 GB → download 10 GB → manual/no verification  
**With CL6:** upload delta → selective download/extract → automatic SHA-256 + Merkle verification

---

## Typical use cases

- **Frequently updated datasets/corpora:** ship only new chunks between releases
- **ML models & patches:** LoRA, shards, index snapshots with dedup + verification
- **Large-scale distribution:** resume-friendly packaging; storage backends can be layered (S3/GCS/MinIO)
- **Partial access:** extract a single file (or range) without unpacking the whole container
- **Audit/compliance:** per-chunk/per-file hashes + optional signature

---

## How it works (high level)

A `.cl6b` container includes:

- **Chunks** (compressed or stored)
- **TOC v2** (chunk/file index for fast partial extraction and verification)
- **Manifest** (metadata, profile, file/segment mapping)
- **Integrity** (SHA-256 per chunk/file + Merkle root)
- Optional **signature**

Conceptual layout:

```
+------------------------ Release (.cl6b) -------------------------------+
| Manifest (files & segments) | TOC v2 (chunk/file index)               |
|  - file list               |  - per-chunk: {frame_start, comp_len,    |
|  - segments -> CID         |               orig_len, codec, sha256}   |
|  - build profile           |  - per-file:  {cids, offsets, total,     |
|                             |              sha256}                    |
|  +----------------------+   +--------------------------------------+  |
|  |  Compressed chunks   |   Footer -> TOC v2 offset                 |  |
|  | (zstd/zlib/lz4/store)|                                          |  |
|  +----------------------+------------------------------------------+  |
+------------------------------------------------------------------------+
              ^                              ^
              |                              |
            CDC                        O(1) access
      (rolling hash)                (chunk range-read)
```

### Key components

- **CDC (gear-hash rolling hash):** stable chunk boundaries even after inserts → high reuse
- **Codec-agnostic:** CL6 is **not** a codec; it uses zstd/zlib/lz4/store via profiles
- **TOC v2:** maps each chunk to position/codec/hash → fast random access and verification
- **Integrity:** SHA-256 per chunk and per file + Merkle root for the release
- **Signing:** optional Ed25519 (recommended) + HMAC fallback

---

## Quickstart

### Requirements
- **Python 3.9+**
- Optional (recommended) dependencies:
  - `zstandard` (best compression in most cases)
  - `lz4` (only if you use LZ4 profiles)
  - `blake3` (if you want BLAKE3 available; otherwise hashing may fall back)

### Install

```bash
git clone https://github.com/pietrorisipr-2025/CoreLang6
cd CoreLang6

python3 --version

python3 -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1

python -m pip install -U pip

# Optional but recommended:
pip install zstandard

# Optional:
# pip install lz4 blake3
```

### Smoke test (30 seconds)

```bash
mkdir -p data
echo "hello cl6" > data/hello.txt

# Pack using a zstd profile
python3 cl6.py pack-profile \
  --profile zstd-lean \
  --input-dir ./data \
  --out-file release.cl6b

# Build TOC v2
python3 cl6.py build-toc-v2 \
  --container release.cl6b

# Extract one file (TOC v2 fast-path) + verify chunks
python3 cl6.py extract-file \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json \
  --path hello.txt \
  --out-file out_hello.txt \
  --verify
```

If `out_hello.txt` contains `hello cl6`, you're good.

> If you do not install `zstandard`, use a compatible profile such as `zlib-compat` or `store`.

---

## Core workflow

### Build & release checklist

```bash
python3 cl6.py pack-profile \
  --profile zstd-lean \
  --input-dir ./data \
  --out-file release.cl6b

python3 cl6.py build-toc-v2 \
  --container release.cl6b

python3 cl6.py release-checklist \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json
```

### Partial extraction & verification

```bash
# Extract a single file (TOC v2 fast-path)
python3 cl6.py extract-file \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json \
  --path path/inside/container \
  --out-file output.bin \
  --verify

# Verify integrity of a specific file
python3 cl6.py verify-file \
  --container release.cl6b \
  --toc release.cl6b.toc.v2.json \
  --path path/inside/container
```

### Byte-range extraction

```bash
python3 cl6.py extract-file \
  --container release.cl6b \
  --path path/inside/container \
  --out-file output.bin \
  --range 0:65536
```

---

## Build profiles

| Profile       | Codec | Level | Avg chunk | When to use |
|--------------|-------|-------|-----------|-------------|
| `zstd-lean`   | zstd  | ~6    | ~512 KiB  | Production, slow networks, repetitive data |
| `zlib-compat` | zlib  | ~6    | ~512 KiB  | Maximum compatibility, fewer deps |
| `store`       | none  | 0     | ~1 MiB    | Debug or data already compressed |

> Profiles are policies: they choose codec + parameters + chunk targets.

---

## Delta-sync (operational concept)

Delta-sync is CID-based:

- Client → Server: “I already have these CIDs: […]”
- Server → Client: missing chunks + updated manifest

Result: transfer is proportional to the **delta**, not the full release.

> Implementation status depends on the current repo version; see `KNOWN_ISSUES.md`.

---

## Repository layout

- `cl6.py` — main CLI
- `cl6b/` — Python package
  - `chunker.py` — CDC (gear-hash)
  - `codecs.py` — codec plugins (zlib/zstd/lz4/store)
  - `hashing.py` — hashing (may fall back if optional deps missing)
  - `ioframes.py` — framed I/O (CRC32C)
  - `manifest.py` — manifest validator (MANIFEST v3)
  - `merkle.py` — Merkle tree (configurable fanout)
  - `pack.py` — pack/extract container
  - `partial.py` — partial extraction / byte-range logic
  - `signing.py` — Ed25519 + HMAC fallback
  - `toc.py` — TOC v1 / TOC v2 builder
  - `util.py` — varint (LEB128)
- `spec/` — format specs and guides
  - `CL6_SPEC_v1_0.md`
  - `README_TOC_v2.md`
  - `README_SIGNING.md`
  - `README_HTTP_RANGE.md`
  - `README_PARTIAL_EXTRACTION.md`
- `tools/` — extra utilities
- `conformance/` — conformance tests (generates artifacts at runtime)
- `Largest/` — optional area for large example artifacts

---

## Conformance

```md
> Note: `conformance/conf_run/` includes **pre-generated example artifacts** (datasets, chunks, and reports) so you can inspect expected outputs without running the suite.
> These files are **optional** and can be deleted at any time—running `python3 conformance/run_conformance.py` will regenerate them locally.


Run the conformance suite (it generates datasets/outputs locally):

```bash
python3 conformance/run_conformance.py
```

Tip: keep generated `.bin`, `chunks/`, `cl6_out/`, and reports out of version control unless you explicitly want to publish test artifacts.

---

## What CL6 is NOT

- Not a messaging protocol (pair it with HTTP/QUIC/gRPC for transport)
- Not a codec (it uses zstd/zlib/lz4/store; value is in chunking + index + dedup + verification)
- Not a replacement for ML build tooling (it packages and delivers build outputs)
- Not the best choice for “one small file, one-time transfer” (a plain `.zst` may be enough)

---

## Project status

**v0.16 — working prototype, not production-ready yet.**

Typically working features:
- `pack-profile`, `build-toc-v2`, `release-checklist`
- `extract-file` (with and without TOC v2, with chunk verification)
- `verify-file`
- byte-range extraction
- Ed25519 signing and HMAC fallback
- CRC32C (Castagnoli) implementation (pure Python)

Known issues / limitations: see **`KNOWN_ISSUES.md`**.

---

## Roadmap (high level)

- Final fix for random-access path in internal `pack.extract()`
- Decide stable hashing policy (explicit SHA-256 vs mandatory BLAKE3)
- Minimal delta-sync client/server implementation
- Go or Rust bindings (spec is language-agnostic)
- Native HTTP Range integration
- Observability (OpenTelemetry): bytes saved, p50/p95 latency, chunk reuse rate
- Semantic chunking for text/embeddings

---

## Contributing

If you're working on ML artifact distribution, dataset pipelines, or replication with delta-sync: open an issue with a real-world scenario. Practical feedback is the most valuable at this stage.

---

## License

MIT
