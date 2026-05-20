# Partial extraction (single file, optional byte range) using container index footer.
from pathlib import Path
import json
from typing import Optional, Tuple
from .ioframes import read_frames
from .pack import FT_MANIFEST_JSON, FT_INDEX, _read_footer
from .codecs import decompress, CodecError

def _parse_range(r: Optional[str], total: int) -> Tuple[int, int]:
    if not r:
        return 0, total
    # formats: "start:end", "start:", ":end"
    try:
        if ":" not in r:
            start = int(r); end = total
        else:
            a,b = r.split(":",1)
            start = int(a) if a.strip() else 0
            end = int(b) if b.strip() else total
        start = max(0, start)
        end = min(total, end)
        if end < start: end = start
        return start, end
    except Exception:
        # fallback to full
        return 0, total

def extract_file(container_path: str, target_path: str, out_file: str, byte_range: Optional[str] = None) -> str:
    cp = Path(container_path)
    manifest = None
    index = None
    # open and jump to index via footer
    with cp.open("rb") as fp:
        idx_off = _read_footer(fp)
        if idx_off < 0:
            raise RuntimeError("indice container mancante")
        # read manifest
        fp.seek(0)
        for fr in read_frames(fp):
            if fr.ftype == FT_MANIFEST_JSON:
                manifest = json.loads(fr.payload.decode("utf-8")); break
        if manifest is None:
            raise RuntimeError("manifest mancante")
        # read index
        fp.seek(idx_off)
        fr = next(read_frames(fp))
        if fr.ftype != FT_INDEX:
            raise RuntimeError("indice non valido")
        index = json.loads(fr.payload.decode("utf-8"))

        # locate file entry
        files = { f["path"]: f for f in manifest["files"] }
        if target_path not in files:
            raise FileNotFoundError(target_path)
        f = files[target_path]
        segs = f["segments"]

        # build map cid -> (orig_len, payload_start, comp_len, codec)
        by_cid = { ch["cid"]: ch for ch in index["chunks"] }
        sizes = []
        for s in segs:
            ch = by_cid.get(s["cid"])
            if ch is None: raise RuntimeError("chunk non indicizzato")
            sizes.append(ch["orig_len"])
        total = sum(sizes)
        start, end = _parse_range(byte_range, total)

        # walk chunks and emit only needed slice
        outp = Path(out_file); outp.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        cur_off = 0
        with outp.open("wb") as w:
            for s in segs:
                ch = by_cid[s["cid"]]
                olen = ch["orig_len"]
                # does this chunk intersect [start,end)?
                seg_start = cur_off
                seg_end = cur_off + olen
                cur_off = seg_end
                if seg_end <= start or seg_start >= end:
                    continue
                # read & decode this chunk
                fp.seek(ch["payload_start"] - 2)  # step back a bit & read frame cleanly
                fr2 = next(read_frames(fp))
                # decode payload format defined in pack: [cid(32)][name_len(1)][name][orig_len(var)][comp_len(var)][data]
                b = fr2.payload
                name_len = b[32]
                codec_name = b[33:33+name_len].decode("ascii")
                # varints (re-parse)
                from .util import uvarint_decode
                o2, i = uvarint_decode(b, 33+name_len)
                c2, j = uvarint_decode(b, i)
                data = b[j:j+c2]
                blob = decompress(codec_name, data)
                if len(blob) != olen:
                    raise RuntimeError("chunk size mismatch dopo decompressione")
                # compute slice within this chunk
                cut_s = max(0, start - seg_start)
                cut_e = min(olen, end - seg_start)
                part = blob[cut_s:cut_e]
                w.write(part); written += len(part)
                if seg_end >= end:
                    break
        return str(outp)


def extract_file_fast(container_path: str, toc_path: str, target_path: str, out_file: str, byte_range: Optional[str] = None, verify_chunks: bool = False) -> str:
    """Estrazione usando TOC pre-calcolato (niente parse index/manifest a runtime)."""
    from .toc import pick_file_entry
    from .util import uvarint_decode
    cp = Path(container_path)
    with open(toc_path, "r") as f:
        toc = json.load(f)
    entry = pick_file_entry(toc, target_path)
        is_v2 = toc.get('version') == 2
    cids = entry["cids"]
    offsets = entry["offsets"]
    total = entry["total"]
    start, end = _parse_range(byte_range, total)

    outp = Path(out_file); outp.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with cp.open("rb") as fp, outp.open("wb") as w:
        for i, cid in enumerate(cids):
            ch = toc["chunks"][cid]
            olen = ch["orig_len"]
            seg_start = offsets[i]
            seg_end = seg_start + olen
            if seg_end <= start or seg_start >= end:
                continue
            fp.seek(ch["payload_start"] - 2)
            fr2 = next(read_frames(fp))
            b = fr2.payload
            name_len = b[32]
            # codec_name = b[33:33+name_len].decode("ascii")  # non serve qui, solo per debug
            o2, i2 = uvarint_decode(b, 33+name_len)
            c2, j2 = uvarint_decode(b, i2)
            data = b[j2:j2+c2]
            blob = decompress(ch["codec"], data)
                if verify_chunks and is_v2:
                    import hashlib
                    if hashlib.sha256(blob).hexdigest() != toc['chunks'][cid]['sha256']:
                        raise RuntimeError(f"hash mismatch per chunk {cid}")
            if len(blob) != olen:
                raise RuntimeError("chunk size mismatch dopo decompressione")
            cut_s = max(0, start - seg_start)
            cut_e = min(olen, end - seg_start)
            w.write(blob[cut_s:cut_e]); written += (cut_e - cut_s)
            if seg_end >= end:
                break
    return str(outp)
