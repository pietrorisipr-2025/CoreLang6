
#!/usr/bin/env python3
"""
Dedup report su uno o più TOC v2: calcola chunk unici e duplicati e stima il risparmio.
"""
import argparse, json
from pathlib import Path
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tocs", nargs="+", help="file .toc.v2.json")
    ap.add_argument("--out", default="dedup_report.json")
    args = ap.parse_args()

    seen = {}
    owners = defaultdict(list)
    total_chunks = 0
    total_bytes = 0
    for toc_p in args.tocs:
        T = json.loads(Path(toc_p).read_text())
        if T.get("version") != 2:
            raise SystemExit(f"{toc_p} non è TOC v2")
        for cid, ch in T["chunks"].items():
            total_chunks += 1
            total_bytes += int(ch["orig_len"])
            key = (ch["sha256"], int(ch["orig_len"]))
            if key not in seen:
                seen[key] = {"count": 0, "bytes": int(ch["orig_len"])}
            seen[key]["count"] += 1
            owners[key].append({"toc": toc_p, "cid": cid})

    unique = sum(1 for k,v in seen.items() if v["count"] == 1)
    dup = sum(1 for k,v in seen.items() if v["count"] > 1)
    potential_save = sum(v["bytes"] * (v["count"] - 1) for v in seen.values() if v["count"] > 1)

    rep = {
        "inputs": args.tocs,
        "total_chunks": total_chunks,
        "total_bytes": total_bytes,
        "unique_chunks": unique,
        "duplicate_groups": dup,
        "potential_savings_bytes": potential_save,
        "top_duplicates": sorted(
            [{"sha256":k[0], "len":k[1], "count":v["count"]} for k,v in seen.items() if v["count"]>1],
            key=lambda x: (x["len"]*x["count"]), reverse=True
        )[:50]
    }
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print("OK:", args.out)

if __name__ == "__main__":
    main()
