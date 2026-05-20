# CL6 container pack/extract (.cl6b) with footer for fast index seek + codec plugin
from pathlib import Path
import json, io, struct
from typing import Dict, Any
from .ioframes import write_frame_ex, read_frames, Frame
from .codecs import decompress, CodecError

FT_MANIFEST_JSON = 0x01
FT_CHUNK = 0x02
FT_INDEX = 0x10

FOOTER_MAGIC = b'CL6BIDX'

def pack(manifest_path: str, chunks_dir: str, out_file: str) -> str:
    man = json.loads(Path(manifest_path).read_text())
    chunks_dir = Path(chunks_dir)
    outp = Path(out_file)
    outp.parent.mkdir(parents=True, exist_ok=True)
    index = { "version": "1.1", "chunks": [] }

    with outp.open("wb") as fp:
        # manifest
        mbytes = json.dumps(man, indent=2).encode("utf-8")
        write_frame_ex(fp, FT_MANIFEST_JSON, mbytes)

        # chunks
        for ch in man["chunks"]:
            cid = ch["cid"]
            z = ch.get("z", {}) or {}
            algo = z.get("algo", "none")
            comp_len = z.get("clen", ch["size"])
            orig_len = ch["size"]
            data = (chunks_dir / cid).read_bytes()
            if len(data) != comp_len:
                raise ValueError(f"chunk {cid} expected clen {comp_len}, got {len(data)}")
            # payload: [cid(32B)][codec(1B ascii?) -> we keep name in index only][uvarint orig_len][uvarint comp_len][data]
            from .util import uvarint_encode
            pay = bytearray()
            pay += bytes.fromhex(cid)
            # store codec name length + bytes (to avoid enum drift)
            cname = (algo or "none").encode("ascii")
            if len(cname) > 31:
                raise ValueError("codec name too long")
            pay += bytes([len(cname)]) + cname
            pay += uvarint_encode(orig_len)
            pay += uvarint_encode(comp_len)
            pay += data
            frame_start, payload_start, frame_end = write_frame_ex(fp, FT_CHUNK, bytes(pay))
            index["chunks"].append({
                "cid": cid,
                "codec": algo,
                "orig_len": orig_len,
                "comp_len": comp_len,
                "frame_start": frame_start,
                "payload_start": payload_start + 32 + 1 + len(cname) + 2,  # after cid + codec name + varints (approx; strict decode uses varints anyway)
                "frame_end": frame_end
            })

        # index
        idx_start, _, _ = write_frame_ex(fp, FT_INDEX, json.dumps(index, separators=(',',':')).encode('utf-8'))
        fp.write(FOOTER_MAGIC + struct.pack("<Q", idx_start))
    return str(outp)

def _read_footer(fp) -> int:
    cur = fp.tell()
    fp.seek(0, 2)
    end = fp.tell()
    fp.seek(max(0, end - (len(FOOTER_MAGIC)+8)))
    tail = fp.read(len(FOOTER_MAGIC)+8)
    if len(tail) == len(FOOTER_MAGIC)+8 and tail[:len(FOOTER_MAGIC)] == FOOTER_MAGIC:
        import struct as _s
        (idx_start,) = _s.unpack("<Q", tail[len(FOOTER_MAGIC):])
        fp.seek(cur); return idx_start
    fp.seek(cur); return -1

def extract(container_path: str, out_dir: str) -> str:
    cp = Path(container_path)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    manifest = None
    chunks: Dict[str, bytes] = {}

    def _decode_chunk_payload(b: bytes):
        # [cid(32)] [name_len(1)] [name] [orig_len(var)] [comp_len(var)] [data]
        cid = b[:32].hex()
        name_len = b[32]
        codec = b[33:33+name_len].decode("ascii")
        from .util import uvarint_decode
        orig_len, i = uvarint_decode(b, 33+name_len)
        comp_len, j = uvarint_decode(b, i)
        data = b[j:j+comp_len]
        try:
            blob = decompress(codec, data)
        except CodecError as e:
            raise RuntimeError(f"decoder mancante per codec {codec}: {e}")
        if len(blob) != orig_len:
            raise ValueError("decoded chunk length mismatch")
        return cid, blob

    with cp.open("rb") as fp:
        idx = _read_footer(fp)
        if idx >= 0:
            # read manifest first
            fp.seek(0)
            for fr in read_frames(fp):
                if fr.ftype == FT_MANIFEST_JSON:
                    manifest = json.loads(fr.payload.decode("utf-8")); break
            # read index & random-access chunks
            fp.seek(idx)
            fr = next(read_frames(fp))
            if fr.ftype != FT_INDEX:
                raise ValueError("bad index frame")
            index = json.loads(fr.payload.decode("utf-8"))
            for ch in index["chunks"]:
                fp.seek(ch["payload_start"] - 2)  # step back a little to reparse cleanly
                fr2 = next(read_frames(fp))
                cid, blob = _decode_chunk_payload(fr2.payload)
                chunks[cid] = blob
        else:
            # stream all frames
            for fr in read_frames(fp):
                if fr.ftype == FT_MANIFEST_JSON:
                    manifest = json.loads(fr.payload.decode("utf-8"))
                elif fr.ftype == FT_CHUNK:
                    cid, blob = _decode_chunk_payload(fr.payload)
                    chunks[cid] = blob
                elif fr.ftype == FT_INDEX:
                    pass

    if manifest is None:
        raise ValueError("manifest frame missing")

    for f in manifest["files"]:
        outp = out / f["path"]
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("wb") as w:
            for s in f["segments"]:
                w.write(chunks[s["cid"]])
        if outp.stat().st_size != f["size"]:
            raise ValueError("recomposed file size mismatch")
    return str(out)
