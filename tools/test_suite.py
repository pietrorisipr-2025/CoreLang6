#!/usr/bin/env python3
"""CL6 light test suite.
Usage:
  python3 tools/test_suite.py --container file.cl6b --quick
  python3 tools/test_suite.py --container file.cl6b --full
"""
import argparse, json, tempfile
from pathlib import Path
from cl6b.pack import _read_footer, FT_INDEX, FT_MANIFEST_JSON, extract as extract_container
from cl6b.ioframes import read_frames
from cl6b.partial import extract_file as partial_extract

def quick(container: Path):
    rep = {"container": str(container), "footer": False, "index": False, "sample_file": None}
    with container.open("rb") as fp:
        off = _read_footer(fp); rep["footer"] = (off >= 0)
        if off >= 0:
            fp.seek(off)
            try:
                fr = next(read_frames(fp)); rep["index"] = (fr.ftype == FT_INDEX)
            except Exception as e:
                rep["index_error"] = str(e)
    # manifest & sample
    try:
        manifest = None
        with container.open("rb") as fp:
            fp.seek(0)
            for fr in read_frames(fp):
                if fr.ftype == FT_MANIFEST_JSON:
                    manifest = json.loads(fr.payload.decode("utf-8")); break
        if manifest and manifest.get("files"):
            f0 = manifest["files"][0]["path"]
            with tempfile.TemporaryDirectory() as td:
                partial_extract(str(container), f0, str(Path(td)/"sample.bin"), "0:65536")
                rep["sample_file"] = f0
    except Exception as e:
        rep["sample_error"] = str(e)
    return rep

def full(container: Path):
    rep = quick(container)
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/"rec"
            extract_container(str(container), str(out))
            rep["full_extract_ok"] = True
    except Exception as e:
        rep["full_extract_ok"] = False
        rep["full_extract_error"] = str(e)
    return rep

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    args = ap.parse_args()
    c = Path(args.container)
    rep = quick(c) if args.quick else full(c)
    print(json.dumps(rep, indent=2))

if __name__ == "__main__":
    main()
