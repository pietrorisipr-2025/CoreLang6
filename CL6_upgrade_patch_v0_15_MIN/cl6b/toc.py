# Precomputed TOC for CL6 containers
from pathlib import Path
import json
from .ioframes import read_frames
from .pack import FT_MANIFEST_JSON, FT_INDEX, _read_footer
from .util import uvarint_decode

def _read_manifest_and_index(fp):
    manifest = None
    fp.seek(0)
    for fr in read_frames(fp):
        if fr.ftype == FT_MANIFEST_JSON:
            manifest = json.loads(fr.payload.decode("utf-8"))
            break
    if manifest is None:
        raise RuntimeError("manifest mancante")
    idx_off = _read_footer(fp)
    if idx_off < 0:
        raise RuntimeError("indice mancante")
    fp.seek(idx_off)
    fr = next(read_frames(fp))
    if fr.ftype != FT_INDEX:
        raise RuntimeError("indice non valido")
    index = json.loads(fr.payload.decode("utf-8"))
    return manifest, index

def build_toc(container_path: str, out_path: str = None) -> str:
    """Crea un TOC pre-calcolato con codec e offset cumulativi per ogni file."""
    cp = Path(container_path)
    with cp.open("rb") as fp:
        manifest, index = _read_manifest_and_index(fp)

        # arricchisci i chunk con codec (leggendo le frame payload una tantum)
        by_cid = {}
        for ch in index["chunks"]:
            by_cid[ch["cid"]] = {
                "payload_start": ch["payload_start"],
                "orig_len": ch["orig_len"],
            }

        # Leggi codec_name per ciascun chunk una volta
        for cid, ch in by_cid.items():
            fp.seek(ch["payload_start"] - 2)
            fr2 = next(read_frames(fp))
            b = fr2.payload
            name_len = b[32]
            codec_name = b[33:33+name_len].decode("ascii")
            o2, i = uvarint_decode(b, 33+name_len)  # orig_len (ridondante)
            c2, j = uvarint_decode(b, i)           # comp_len
            ch["codec"] = codec_name

        # Costruisci TOC
        toc = {
            "container": str(cp),
            "version": 1,
            "chunks": by_cid,  # cid -> {payload_start, orig_len, codec}
            "files": {}
        }

        for f in manifest["files"]:
            path = f["path"]
            segs = f["segments"]
            offsets = []
            running = 0
            for s in segs:
                offsets.append(running)
                running += by_cid[s["cid"]]["orig_len"]
            toc["files"][path] = {
                "total": running,
                "cids": [s["cid"] for s in segs],
                "offsets": offsets,
            }

    out = Path(out_path) if out_path else cp.with_suffix(cp.suffix + ".toc.json")
    out.write_text(json.dumps(toc, indent=2))
    return str(out)

def pick_file_entry(toc: dict, target_path: str):
    f = toc["files"].get(target_path)
    if not f:
        raise FileNotFoundError(target_path)
    return f



import hashlib

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def build_toc_v2(container_path: str, out_path: str = None) -> str:
    """
    TOC v2: include sha256 per chunk (decompresso) e sha256 per file.
    """
    cp = Path(container_path)
    with cp.open("rb") as fp:
        manifest, index = _read_manifest_and_index(fp)

        # Mappa chunk base
        by_cid = {}
        for ch in index["chunks"]:
            by_cid[ch["cid"]] = {
                "payload_start": ch["payload_start"],
                "orig_len": ch["orig_len"],
            }

        from .util import uvarint_decode
        # Leggi codec e dati compressi una volta per calcolare hash su decompresso
        from .codecs import decompress
        for cid, ch in by_cid.items():
            fp.seek(ch["payload_start"] - 2)
            fr2 = next(read_frames(fp))
            b = fr2.payload
            name_len = b[32]
            codec_name = b[33:33+name_len].decode("ascii")
            o2, i = uvarint_decode(b, 33+name_len)
            c2, j = uvarint_decode(b, i)
            comp = b[j:j+c2]
            blob = decompress(codec_name, comp)
            if len(blob) != ch["orig_len"]:
                raise RuntimeError("chunk size mismatch")
            ch["codec"] = codec_name
            ch["sha256"] = _sha256(blob)

        toc = {
            "container": str(cp),
            "version": 2,
            "chunks": by_cid,  # cid -> {payload_start, orig_len, codec, sha256}
            "files": {},
        }

        # Calcola sha256 dei file concatenando i chunk in ordine
        for f in manifest["files"]:
            path = f["path"]
            segs = f["segments"]
            offsets = []
            running = 0
            hasher = hashlib.sha256()
            for i, s in enumerate(segs):
                offsets.append(running)
                ch = by_cid[s["cid"]]
                running += ch["orig_len"]
                # ricostruisci blob solo per hash (riusa quanto sopra? compresso non più accessibile qui)
                # per efficienza, rileggi e decomprimi come sopra
                fp.seek(ch["payload_start"] - 2)
                fr2 = next(read_frames(fp))
                b = fr2.payload
                name_len = b[32]
                codec_name = b[33:33+name_len].decode("ascii")
                o2, i2 = uvarint_decode(b, 33+name_len)
                c2, j2 = uvarint_decode(b, i2)
                comp = b[j2:j2+c2]
                blob = decompress(codec_name, comp)
                hasher.update(blob)
            toc["files"][path] = {
                "total": running,
                "cids": [s["cid"] for s in segs],
                "offsets": offsets,
                "sha256": hasher.hexdigest(),
            }

    out = Path(out_path) if out_path else cp.with_suffix(cp.suffix + ".toc.v2.json")
    out.write_text(json.dumps(toc, indent=2))
    return str(out)
