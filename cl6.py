#!/usr/bin/env python3
# Repaired CoreLang6 CLI (minimal) v0.16
import argparse, sys, json, hashlib
from pathlib import Path

# Import toolkit modules
sys.path.insert(0, str(Path(__file__).parent))
from cl6b.hashing import cid_hex
from cl6b.merkle import merkle_root
from cl6b.codecs import compress, CodecError
from cl6b.chunker import chunk_ranges
from cl6b.pack import pack as pack_container
from cl6b.toc import build_toc_v2
from cl6b.partial import extract_file as partial_extract, extract_file_fast as partial_extract_fast

PROFILES = {
    "zlib-compat": {"codec": "zlib", "level": 6, "avg_kib": 512},
    "zstd-lean":   {"codec": "zstd", "level": 6, "avg_kib": 512},
    "store":       {"codec": "store", "level": 0, "avg_kib": 1024},
}

def build_manifest_from_dir(input_dir: str, profile: str, chunks_dir: str, manifest_out: str) -> str:
    prof = PROFILES[profile]; codec = prof["codec"]; level = prof["level"]; avg_kib = prof["avg_kib"]
    root = Path(input_dir); cdir = Path(chunks_dir); cdir.mkdir(parents=True, exist_ok=True)
    files=[]; chunks=[]; leaves=[]
    for p in sorted(root.rglob("*")):
        if p.is_dir(): continue
        rel = p.relative_to(root).as_posix()
        blob = p.read_bytes()
        spans = [(s, s+ln) for s,ln in chunk_ranges(blob, avg_kib=avg_kib)]
        file_segments = []; file_off = 0
        for s,e in spans:
            seg = blob[s:e]; cid = cid_hex(seg)
            try:
                comp = compress(codec, seg, level=level)
            except CodecError:
                fallback = "zlib" if codec == "zstd" else "store"
                comp = compress(fallback, seg, level=6 if fallback=="zlib" else 0)
                codec = fallback
            (cdir / cid).write_bytes(comp)
            zmeta = {"algo": codec, "level": level, "clen": len(comp), "ratio": round(len(seg)/len(comp), 4) if len(comp) else None}
            chunks.append({"cid": cid, "size": len(seg), "z": zmeta})
            leaves.append(bytes.fromhex(cid))
            file_segments.append({"cid": cid, "file_offset": file_off, "length": (e - s)})
            file_off += (e - s)
        files.append({"path": rel, "size": p.stat().st_size, "segments": file_segments})
    root_hash = merkle_root(leaves, fanout=1024).hex() if leaves else ""
    manifest = {
        "schema": "CL6/MANIFEST_v3", "version": "3.0", "release_id": f"cl6-pack-{profile}", "created_at": "now",
        "merkle": {"fanout": 1024, "root": root_hash},
        "chunks": chunks, "files": files,
        "profiles": [{"name": profile, "http": {}, "chunking": {"avg_kib": avg_kib}, "K": 16, "codec": {"name": codec, "level": level}}],
    }
    Path(manifest_out).write_text(json.dumps(manifest, indent=2)); return manifest_out

def cmd_pack_profile(a):
    input_dir = Path(a.input_dir)
    if not input_dir.exists(): raise SystemExit("input-dir non esiste")
    if a.profile not in PROFILES: raise SystemExit("profilo non valido")
    tmp = Path(a.tmp_dir or ".cl6_chunks"); tmp.mkdir(parents=True, exist_ok=True)
    man_path = Path(a.out_file).with_suffix(".manifest.json")
    build_manifest_from_dir(str(input_dir), a.profile, str(tmp), str(man_path))
    pack_container(str(man_path), str(tmp), str(Path(a.out_file)))
    print(str(Path(a.out_file))); return 0

def cmd_build_toc_v2(a):
    out = build_toc_v2(a.container, a.out); print(out); return 0

def cmd_extract_file(a):
    if a.toc:
        out = partial_extract_fast(a.container, a.toc, a.path, a.out_file, a.range, a.verify)
    else:
        out = partial_extract(a.container, a.path, a.out_file, a.range)
    print(out); return 0

def cmd_verify_file(a):
    import json as _j, hashlib as _h, pathlib as _p
    T = _j.loads(_p.Path(a.toc).read_text())
    if T.get("version") != 2: raise SystemExit("TOC non è v2: usa build-toc-v2")
    entry = T["files"].get(a.path)
    if not entry: raise SystemExit("file non trovato nel TOC")
    tmp = _p.Path(a.out or ".cl6_verify.tmp")
    partial_extract_fast(a.container, a.toc, a.path, str(tmp), None, True)
    got = _h.sha256(tmp.read_bytes()).hexdigest()
    ok = (got == entry["sha256"])
    rep = {"path": a.path, "expected": entry["sha256"], "got": got, "ok": ok}
    tmp.unlink(missing_ok=True)
    print(json.dumps(rep, indent=2)); return 0 if ok else 2

def cmd_release_checklist(a):
    import json as _j
    from cl6b.pack import _read_footer
    from cl6b.ioframes import read_frames
    cp = Path(a.container); 
    if not cp.exists(): raise SystemExit("container non trovato")
    toc = None
    if a.toc and Path(a.toc).exists():
        T = _j.loads(Path(a.toc).read_text())
        if T.get("version") != 2: raise SystemExit("TOC non è v2")
        toc = T
    with cp.open("rb") as fp:
        off = _read_footer(fp); fp.seek(off); fr = next(read_frames(fp)); idx = _j.loads(fr.payload.decode("utf-8"))
    codec = idx["chunks"][0]["codec"] if idx["chunks"] else "n/a"
    checks = {"container": str(cp), "codec": codec, "toc_v2": bool(toc)}
    if a.expect_codec and a.expect_codec != codec:
        checks["codec_mismatch"] = {"expected": a.expect_codec, "found": codec}
    if toc:
        checks["chunks_index"] = len(idx["chunks"]); checks["chunks_toc"] = len(toc["chunks"]); checks["files_toc"] = len(toc["files"])
        checks["ok_counts"] = (len(idx["chunks"]) == len(toc["chunks"]))
    print(json.dumps(checks, indent=2)); return 0

def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)

    pk = sub.add_parser("pack-profile")
    pk.add_argument("--input-dir", required=True)
    pk.add_argument("--out-file", required=True)
    pk.add_argument("--profile", choices=list(PROFILES.keys()), required=True)
    pk.add_argument("--tmp-dir"); pk.set_defaults(func=cmd_pack_profile)

    bt2 = sub.add_parser("build-toc-v2")
    bt2.add_argument("--container", required=True)
    bt2.add_argument("--out", default=None); bt2.set_defaults(func=cmd_build_toc_v2)

    sxf = sub.add_parser("extract-file")
    sxf.add_argument("--container", required=True)
    sxf.add_argument("--path", required=True)
    sxf.add_argument("--out-file", required=True)
    sxf.add_argument("--toc", default=None)
    sxf.add_argument("--range", default=None)
    sxf.add_argument("--verify", action="store_true")
    sxf.set_defaults(func=cmd_extract_file)

    vf = sub.add_parser("verify-file")
    vf.add_argument("--container", required=True)
    vf.add_argument("--toc", required=True)
    vf.add_argument("--path", required=True)
    vf.add_argument("--out"); vf.set_defaults(func=cmd_verify_file)

    rcl = sub.add_parser("release-checklist")
    rcl.add_argument("--container", required=True)
    rcl.add_argument("--toc")
    rcl.add_argument("--expect-codec"); rcl.set_defaults(func=cmd_release_checklist)

    args = ap.parse_args(argv or sys.argv[1:])
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
