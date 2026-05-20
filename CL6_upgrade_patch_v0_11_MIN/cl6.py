#!/usr/bin/env python3
import argparse, sys, json, os, tempfile
from pathlib import Path
from cl6b.convert import cl5_to_cl6_rechunk
from cl6b.validate import validate_manifest
from cl6b.pack import pack as pack_container, extract as extract_container, _read_footer, FT_INDEX, FT_MANIFEST_JSON
from cl6b.signing import sign_manifest, verify_manifest, sign_manifest_ed25519, verify_manifest_ed25519
from cl6b.partial import extract_file as partial_extract, extract_file_fast as partial_extract_fast
from cl6b.ioframes import read_frames
from cl6b.toc import build_toc

def cmd_convert_rechunk(a):
    man, dr = cl5_to_cl6_rechunk(a.cl5_dir, a.out_dir, a.v1, a.v2, a.min_kib, a.avg_kib, a.max_kib, a.codec, a.level)
    print(json.dumps(dr, indent=2)); return 0

def cmd_validate(a):
    ok = validate_manifest(a.path, strict=a.strict, chunks_dir=a.chunks_dir)
    return 0 if ok else 2

def cmd_pack(a):
    out = pack_container(a.manifest, a.chunks_dir, a.out_file); print(out); return 0

def cmd_extract(a):
    out = extract_container(a.container, a.out_dir); print(out); return 0

def cmd_extract_file(a):
    out = partial_extract(a.container, a.path, a.out_file, a.range)
    print(out); return 0

def cmd_sign(a):
    sign_manifest(a.path, a.key, a.kid); print("signed"); return 0

def cmd_verify(a):
    ok = verify_manifest(a.path, a.key); print(ok); return 0 if ok else 2

def cmd_sign_ed25519(a):
    try:
        priv = Path(a.private_key).read_text()
        sign_manifest_ed25519(a.path, priv, a.kid)
        print("signed-ed25519"); return 0
    except Exception as e:
        print(str(e), file=sys.stderr); return 3

def cmd_verify_ed25519(a):
    try:
        pub = Path(a.public_key).read_text()
        ok = verify_manifest_ed25519(a.path, pub)
        print(ok); return 0 if ok else 2
    except Exception as e:
        print(str(e), file=sys.stderr); return 3

def split_bytes(data: bytes, part_bytes: int):
    return [data[i:i+part_bytes] for i in range(0, len(data), part_bytes)] or [b""]

def cmd_split(a):
    src = Path(a.container).read_bytes()
    payload = a.payload if a.payload else int(0.90 * 1024 * 1024)  # default ~900 KiB
    base = Path(a.out_dir); base.mkdir(parents=True, exist_ok=True)
    import zipfile
    links = []
    for i, chunk in enumerate(split_bytes(src, payload), start=1):
        name = f"{Path(a.container).stem}.part{str(i).zfill(3)}"
        zname = base / f"{name}.zip"
        with zipfile.ZipFile(zname, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(name, chunk)
        links.append(str(zname))
    print("\n".join(links)); return 0

def cmd_join(a):
    p = Path(a.parts_dir)
    zs = sorted(p.glob("*.part*.zip"))
    if not zs: print("no parts found", file=sys.stderr); return 2
    import zipfile
    with open(a.out_file, "wb") as w:
        for zf in zs:
            with zipfile.ZipFile(zf, "r") as z:
                n = z.namelist()[0]
                w.write(z.read(n))
    print(a.out_file); return 0

def cmd_selfcheck(a):
    path = Path(a.container)
    report = {"container": str(path), "footer_index": False, "index_readable": False, "sample_file": None}
    with path.open("rb") as fp:
        off = _read_footer(fp)
        report["footer_index"] = (off >= 0)
        if off >= 0:
            fp.seek(off)
            try:
                fr = next(read_frames(fp))
                report["index_readable"] = (fr.ftype == FT_INDEX)
            except Exception as e:
                report["index_error"] = str(e)
    # sample extract first file (if present)
    try:
        manifest = None
        with path.open("rb") as fp:
            fp.seek(0)
            for fr in read_frames(fp):
                if fr.ftype == FT_MANIFEST_JSON:
                    manifest = json.loads(fr.payload.decode("utf-8")); break
        if manifest and manifest.get("files"):
            f0 = manifest["files"][0]["path"]
            with tempfile.TemporaryDirectory() as td:
                partial_extract(str(path), f0, str(Path(td)/"sample.bin"), "0:65536")
                report["sample_file"] = f0
    except Exception as e:
        report["sample_error"] = str(e)
    print(json.dumps(report, indent=2)); return 0



def cmd_parts_check(a):
    """Verifica che esistano tutte le parti xs.partNNN.zip di un base name."""
    from pathlib import Path
    import re, json
    p = Path(a.dir)
    base = a.base
    patt = re.compile(re.escape(base) + r"\.xs\.part(\d{3})\.zip$")
    parts = {}
    for f in sorted(p.glob(base + ".xs.part*.zip")):
        m = patt.search(f.name)
        if m:
            parts[int(m.group(1))] = f
    if not parts:
        print(json.dumps({"base": base, "found": 0, "present": [], "missing": []}, indent=2)); return 1
    present = sorted(parts.keys())
    mn, mx = present[0], present[-1]
    missing = [i for i in range(mn, mx+1) if i not in parts]
    rep = {
        "base": base,
        "found": len(present),
        "first": mn, "last": mx,
        "present": present,
        "missing": missing,
    }
    print(json.dumps(rep, indent=2)); return 0 if not missing else 2

def cmd_join_xs(a):
    """Ricompone file da parti xs.partNNN.zip concatenando l'unico entry interno."""
    from pathlib import Path
    import zipfile, re
    p = Path(a.dir)
    base = a.base
    patt = re.compile(re.escape(base) + r"\.xs\.part(\d{3})\.zip$")
    parts = []
    for f in sorted(p.glob(base + ".xs.part*.zip")):
        m = patt.search(f.name)
        if m:
            parts.append((int(m.group(1)), f))
    if not parts:
        print("no parts found for", base); return 2
    parts.sort()
    outp = Path(a.out)
    with outp.open("wb") as w:
        for _, zf in parts:
            with zipfile.ZipFile(zf, "r") as z:
                name = z.namelist()[0]
                w.write(z.read(name))
    print(str(outp)); return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("convert-rechunk")
    sc.add_argument("--cl5-dir", required=True); sc.add_argument("--out-dir", required=True)
    sc.add_argument("--v1", default="dataset_v1_full.bin"); sc.add_argument("--v2", default="dataset_v2_full.bin")
    sc.add_argument("--min-kib", type=int, default=256); sc.add_argument("--avg-kib", type=int, default=512); sc.add_argument("--max-kib", type=int, default=1024)
    sc.add_argument("--codec", choices=["zlib","none","zstd","lz4"], default="zlib"); sc.add_argument("--level", type=int, default=6)
    sc.set_defaults(func=cmd_convert_rechunk)

    sv = sub.add_parser("validate")
    sv.add_argument("--path", required=True); sv.add_argument("--strict", action="store_true"); sv.add_argument("--chunks-dir", required=True)
    sv.set_defaults(func=cmd_validate)

    sp = sub.add_parser("pack")
    sp.add_argument("--manifest", required=True); sp.add_argument("--chunks-dir", required=True); sp.add_argument("--out-file", required=True)
    sp.set_defaults(func=cmd_pack)

    sx = sub.add_parser("extract")
    sx.add_argument("--container", required=True); sx.add_argument("--out-dir", required=True)
    sx.set_defaults(func=cmd_extract)

    sxf = sub.add_parser("extract-file")
    sxf.add_argument("--container", required=True); sxf.add_argument("--path", required=True); sxf.add_argument("--out-file", required=True); sxf.add_argument("--toc", default=None)
    sxf.add_argument("--range", default=None, help="start:end (byte range), opzionale")
    sxf.set_defaults(func=cmd_extract_file)

    ss = sub.add_parser("sign")
    ss.add_argument("--path", required=True); ss.add_argument("--key", required=True); ss.add_argument("--kid", default=None)
    ss.set_defaults(func=cmd_sign)

    svf = sub.add_parser("verify")
    svf.add_argument("--path", required=True); svf.add_argument("--key", required=True)
    svf.set_defaults(func=cmd_verify)

    sse = sub.add_parser("sign-ed25519")
    sse.add_argument("--path", required=True); sse.add_argument("--private-key", required=True); sse.add_argument("--kid", default=None)
    sse.set_defaults(func=cmd_sign_ed25519)

    sve = sub.add_parser("verify-ed25519")
    sve.add_argument("--path", required=True); sve.add_argument("--public-key", required=True)
    sve.set_defaults(func=cmd_verify_ed25519)

    sp2 = sub.add_parser("split")
    sp2.add_argument("--container", required=True); sp2.add_argument("--out-dir", required=True)
    sp2.add_argument("--payload", type=int, default=None, help="payload bytes per part (default ~0.9 MiB)")
    sp2.set_defaults(func=cmd_split)

    sj = sub.add_parser("join")
    sj.add_argument("--parts-dir", required=True); sj.add_argument("--out-file", required=True)
    sj.set_defaults(func=cmd_join)

    stoc = sub.add_parser("build-toc")
        stoc.add_argument("--container", required=True)
        stoc.add_argument("--out", default=None)
        stoc.set_defaults(func=cmd_build_toc)

        sh = sub.add_parser("selfcheck")
    sh.add_argument("--container", required=True)
    sh.set_defaults(func=cmd_selfcheck)

    
spc = sub.add_parser("parts-check")
spc.add_argument("--dir", required=True)
spc.add_argument("--base", required=True, help="basename senza suffissi .xs.partNNN.zip")
spc.set_defaults(func=cmd_parts_check)

sjx = sub.add_parser("join-xs")
sjx.add_argument("--dir", required=True)
sjx.add_argument("--base", required=True)
sjx.add_argument("--out", required=True)
sjx.set_defaults(func=cmd_join_xs)

    args = ap.parse_args(argv); return args.func(args)

if __name__ == "__main__":
    sys.exit(main())


def cmd_build_toc(a):
    out = build_toc(a.container, a.out)
    print(out); return 0
