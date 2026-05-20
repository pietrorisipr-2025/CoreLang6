# CL5→CL6 converters
import json, os, zlib
from pathlib import Path
from typing import Dict, Any, List, Tuple
from .hashing import cid_hex
from .merkle import merkle_root
from .chunker import chunk_ranges

def _profiles(avg_kib: int, codec: str, level: int):
    return [
        {"name": "eco", "http": {"h3_concurrency": 4, "streams": 4}, "shard_kib": avg_kib, "K": 16, "codec": {"name": codec, "level": level}},
        {"name": "turbo", "http": {"h3_concurrency": 16, "streams": 16}, "shard_kib": avg_kib, "K": 64, "codec": {"name": codec, "level": level}}
    ]

def cl5_to_cl6(cl5_dir: str, out_dir: str, path_v2: str = "dataset_v2_full.bin") -> str:
    cl5 = Path(cl5_dir); out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    man5 = json.loads((cl5 / "SHARD_MANIFEST_v3.json").read_text())
    files = man5.get("files", [])
    v2 = next((f for f in files if f.get("name")==path_v2), None)
    if not v2:
        raise RuntimeError("v2 file entry not found in CL5 manifest")
    v2_size = v2["size"]
    shard_ids = [s["id"] for s in man5["shards"]]
    chunk_map: Dict[str, Dict[str, Any]] = {}
    for sid in shard_ids:
        shard_path = cl5 / "shards" / sid
        b = shard_path.read_bytes()
        c_hex = cid_hex(b)
        if c_hex not in chunk_map:
            zc = zlib.compress(b, 6)
            chunk_map[c_hex] = { "cid": c_hex, "size": len(b), "z": {"algo":"zlib","level":6,"ratio": len(zc)/len(b) if len(b) else 1.0, "clen": len(zc)} }
    chunks = list(chunk_map.values())
    root = merkle_root([bytes.fromhex(ch["cid"]) for ch in chunks], fanout=1024).hex()
    segs = []
    file_off = 0
    for ch in chunks:
        ln = ch["size"]
        segs.append({ "cid": ch["cid"], "file_offset": file_off, "length": ln })
        file_off += ln
    man6 = {
        "schema": "CL6/MANIFEST_v3",
        "version": "3.0",
        "release_id": "generated",
        "created_at": "now",
        "merkle": {"fanout": 1024, "root": root},
        "chunks": chunks,
        "files": [{ "path": path_v2, "size": v2_size, "segments": segs }],
        "profiles": _profiles(512, "zlib", 6)
    }
    (out / "CL6_MANIFEST_v3.json").write_text(json.dumps(man6, indent=2))
    return str(out / "CL6_MANIFEST_v3.json")

def cl5_to_cl6_rechunk(cl5_dir: str, out_dir: str, v1_name: str = "dataset_v1_full.bin", v2_name: str = "dataset_v2_full.bin",
                       min_kib: int = 256, avg_kib: int = 512, max_kib: int = 1024,
                       codec: str = "zlib", level: int = 6) -> Tuple[str, Dict[str, Any]]:
    base = Path(cl5_dir); out = Path(out_dir)
    out_chunks = out / "chunks"; out_chunks.mkdir(parents=True, exist_ok=True)
    v1 = base / v1_name; v2 = base / v2_name
    b1 = v1.read_bytes(); b2 = v2.read_bytes()

    r1 = chunk_ranges(b1, min_kib, avg_kib, max_kib)
    r2 = chunk_ranges(b2, min_kib, avg_kib, max_kib)

    v1_cids = set()
    for (off, ln) in r1:
        v1_cids.add(cid_hex(b1[off:off+ln]))

    chunk_map: Dict[str, Dict[str, Any]] = {}
    leaves = []
    segs = []
    file_off = 0
    new_bytes = 0

    for (off, ln) in r2:
        blob = b2[off:off+ln]
        c = cid_hex(blob)
        if c not in chunk_map:
            if codec == "zlib":
                zc = zlib.compress(blob, level)
                zmeta = {"algo":"zlib","level":level,"ratio": (len(zc)/ln) if ln else 1.0, "clen": len(zc)}
                (out_chunks / c).write_bytes(zc)
            else:
                zmeta = {"algo":"none","level":0,"ratio":1.0, "clen": ln}
                (out_chunks / c).write_bytes(blob)
            chunk_map[c] = { "cid": c, "size": ln, "z": zmeta }
            leaves.append(bytes.fromhex(c))
            if c not in v1_cids:
                new_bytes += ln
        segs.append({ "cid": c, "file_offset": file_off, "length": ln })
        file_off += ln

    chunks = list(chunk_map.values())
    root = merkle_root([bytes.fromhex(ch["cid"]) for ch in chunks], fanout=1024).hex()

    man6 = {
        "schema": "CL6/MANIFEST_v3",
        "version": "3.0",
        "release_id": "generated",
        "created_at": "now",
        "merkle": { "fanout": 1024, "root": root },
        "chunks": chunks,
        "files": [{ "path": v2_name, "size": len(b2), "segments": segs }],
        "profiles": _profiles(avg_kib, codec, level)
    }
    man_path = out / "CL6_MANIFEST_v3.json"
    man_path.write_text(json.dumps(man6, indent=2))

    delta_report = {
        "v1": { "name": v1_name, "bytes": len(b1) },
        "v2": { "name": v2_name, "bytes": len(b2) },
        "chunking": { "min_kib": min_kib, "avg_kib": avg_kib, "max_kib": max_kib, "codec": codec, "level": level },
        "stats": {
            "total_chunks": len(segs),
            "unique_chunks": len(chunks),
            "new_bytes": new_bytes,
            "reuse_bytes": len(b2) - new_bytes,
            "reuse_pct": (len(b2) - new_bytes) / len(b2) * 100.0 if len(b2) else 0.0
        }
    }
    (out / "DELTA_REPORT.json").write_text(json.dumps(delta_report, indent=2))
    return str(man_path), delta_report
