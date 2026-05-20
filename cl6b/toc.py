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
                    "comp_len": ch.get("comp_len") or ch.get("clen") or 0,
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
    Usa frame_start e parse del payload per localizzare i bytes compressi.
    """
    cp = Path(container_path)
    with cp.open("rb") as fp:
        manifest, index = _read_manifest_and_index(fp)

        # Mappa chunk base direttamente dall'indice
        by_cid = {}
        for ch in index["chunks"]:
            by_cid[ch["cid"]] = {
                "payload_start": int(ch["payload_start"]),
                "frame_start": int(ch.get("frame_start") or 0),
                "orig_len": int(ch["orig_len"]),
                "comp_len": int(ch.get("comp_len") or 0),
                "codec": ch.get("codec") or "zlib",
            }

        import hashlib
        from .codecs import decompress
        from .util import uvarint_decode

        # Calcola sha256 dei chunk leggendo il frame e tagliando la porzione compressa
        for cid, ch in by_cid.items():
            fp.seek(int(ch["frame_start"]))
            fr = next(read_frames(fp))
            b = fr.payload
            name_len = b[32]
            _o, i2 = uvarint_decode(b, 33+name_len)
            c2, j2 = uvarint_decode(b, i2)
            comp = b[j2:j2+c2]
            blob = decompress(ch["codec"], comp)
            if len(blob) != ch["orig_len"]:
                raise RuntimeError("chunk size mismatch")

            ch["sha256"] = hashlib.sha256(blob).hexdigest()
            ch["comp_len"] = c2  # normalizza comp_len coerente al frame

        toc = {
            "container": str(cp),
            "version": 2,
            "chunks": by_cid,  # cid -> {payload_start, frame_start, orig_len, comp_len, codec, sha256}
            "files": {},
        }

        # Calcola sha256 dei file concatenando i chunk in ordine
        import hashlib as _h
        for f in manifest["files"]:
            path = f["path"]
            segs = f["segments"]
            offsets = []
            running = 0
            hasher = _h.sha256()
            for s in segs:
                ch = by_cid[s["cid"]]
                offsets.append(running)
                running += ch["orig_len"]
                # usa blob ricostruito (senza rileggere dal file)
                # ma per evitare memoria, lo rigeneriamo on the fly
                fp.seek(int(ch["frame_start"]))
                fr = next(read_frames(fp))
                b = fr.payload
                name_len = b[32]
                _o, i2 = uvarint_decode(b, 33+name_len)
                c2, j2 = uvarint_decode(b, i2)
                comp = b[j2:j2+c2]
                blob = decompress(ch["codec"], comp)
                hasher.update(blob)
            toc["files"][path] = {"total": running, "cids": [s["cid"] for s in segs], "offsets": offsets, "sha256": hasher.hexdigest()}

    out = Path(out_path) if out_path else cp.with_suffix(cp.suffix + ".toc.v2.json")
    out.write_text(json.dumps(toc, indent=2))
    return str(out)
