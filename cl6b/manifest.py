# CL6/MANIFEST_v3 loader & validator (stdlib-only). Adds strict checks with on-disk chunk verification.
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from .merkle import merkle_root

REQUIRED_TOP = ["schema","version","release_id","merkle","chunks","files"]

def load(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())

def validate(man: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    for k in REQUIRED_TOP:
        if k not in man:
            errs.append(f"missing top-level key: {k}")
    if man.get("schema") != "CL6/MANIFEST_v3":
        errs.append("schema must be 'CL6/MANIFEST_v3'")
    if not isinstance(man.get("chunks"), list) or not man["chunks"]:
        errs.append("chunks must be a non-empty array")
    if not isinstance(man.get("files"), list) or not man["files"]:
        errs.append("files must be a non-empty array")
    mk = man.get("merkle", {})
    if not isinstance(mk.get("fanout", 0), int) or mk.get("fanout", 0) < 2:
        errs.append("merkle.fanout must be int >= 2")
    if not isinstance(mk.get("root",""), str) or len(mk.get("root","")) < 16:
        errs.append("merkle.root must be non-empty string")
    seen = set()
    leaves = []
    for i, ch in enumerate(man.get("chunks", [])):
        cid = ch.get("cid")
        size = ch.get("size")
        if not isinstance(cid, str) or len(cid) < 16:
            errs.append(f"chunks[{i}].cid invalid")
        if not isinstance(size, int) or size < 0:
            errs.append(f"chunks[{i}].size invalid")
        if cid in seen:
            errs.append(f"duplicate chunk cid: {cid}")
        seen.add(cid)
        try:
            leaves.append(bytes.fromhex(cid))
        except Exception:
            errs.append(f"chunks[{i}].cid is not hex")
    for j, f in enumerate(man.get("files", [])):
        if not isinstance(f.get("path",""), str) or not isinstance(f.get("size",0), int):
            errs.append(f"files[{j}] invalid path/size")
        segs = f.get("segments", [])
        if not isinstance(segs, list) or not segs:
            errs.append(f"files[{j}].segments must be non-empty array")
        total_len = 0
        last_off = -1
        for k, s in enumerate(segs):
            cid = s.get("cid"); off = s.get("file_offset"); ln = s.get("length")
            if not isinstance(cid, str): errs.append(f"files[{j}].segments[{k}].cid invalid")
            if not isinstance(off, int) or off < 0: errs.append(f"files[{j}].segments[{k}].file_offset invalid")
            if not isinstance(ln, int) or ln < 0: errs.append(f"files[{j}].segments[{k}].length invalid")
            if off <= last_off:
                errs.append(f"files[{j}].segments[{k}] not strictly increasing offsets")
            last_off = off
            total_len += ln if isinstance(ln, int) else 0
        if isinstance(f.get("size"), int) and total_len != f["size"]:
            errs.append(f"files[{j}] size mismatch: segments sum {total_len} != size {f['size']}")
    if leaves:
        root = merkle_root(leaves, fanout=man["merkle"]["fanout"]).hex()
        if root != man["merkle"]["root"]:
            errs.append("merkle.root mismatch with computed leaves")
    return errs

def validate_strict(man_path: str, chunks_dir: Optional[str] = None) -> List[str]:
    man = load(man_path)
    errs = validate(man)
    if chunks_dir:
        d = Path(chunks_dir)
        for ch in man.get("chunks", []):
            cid = ch["cid"]; sz = ch["size"]
            z = ch.get("z") or {}
            clen = z.get("clen", None)
            p = d / cid
            if not p.exists():
                errs.append(f"chunk file missing: {p}")
            else:
                on_disk = p.stat().st_size
                expected = clen if (clen is not None) else sz
                if on_disk != expected:
                    errs.append(f"size mismatch on disk: {cid} {on_disk} != {expected}")
    return errs
