# Conformance runner (small): generate two versions, convert with rechunk+zlib, validate strict, sign & verify.
import os, json, random, hashlib, sys, subprocess
from pathlib import Path

def gen_file(path: Path, size_bytes: int, seed: int = 123):
    rng = random.Random(seed)
    block = bytearray(64*1024)
    with open(path, "wb") as f:
        written = 0
        while written < size_bytes:
            for i in range(len(block)):
                block[i] = rng.randrange(0, 256)
            chunk = bytes(block)
            want = min(len(chunk), size_bytes - written)
            f.write(chunk[:want])
            written += want

def mutate(path_in: Path, path_out: Path, ratio: float = 0.05, seed: int = 7):
    data = bytearray(path_in.read_bytes())
    n = max(1, int(len(data) * ratio))
    rng = random.Random(seed)
    for _ in range(n):
        i = rng.randrange(0, len(data))
        data[i] = (data[i] + rng.randrange(1, 251)) % 256
    path_out.write_bytes(bytes(data))

def main():
    base = Path.cwd() / "conf_run"
    if base.exists():
        for root, dirs, files in os.walk(base, topdown=False):
            for name in files:
                os.remove(Path(root)/name)
            for name in dirs:
                os.rmdir(Path(root)/name)
        os.rmdir(base)
    base.mkdir()

    v1 = base / "dataset_v1_full.bin"
    v2 = base / "dataset_v2_full.bin"
    gen_file(v1, 10 * 1024 * 1024, seed=123)
    mutate(v1, v2, ratio=0.05, seed=7)

    cl5_dir = base / "cl5_release"
    cl5_dir.mkdir()
    (cl5_dir / "dataset_v1_full.bin").write_bytes(v1.read_bytes())
    (cl5_dir / "dataset_v2_full.bin").write_bytes(v2.read_bytes())
    (cl5_dir / "SHARD_MANIFEST_v3.json").write_text(json.dumps({"shard_kib":512,"shards":[],"files":[]}, indent=2))

    out_dir = base / "cl6_out"
    out_dir.mkdir()
    cli = Path(__file__).resolve().parents[1] / "cl6.py"
    # Convert with zlib compression metadata
    cmd = [sys.executable, str(cli), "convert-rechunk", "--cl5-dir", str(cl5_dir), "--out-dir", str(out_dir),
           "--min-kib","256","--avg-kib","512","--max-kib","1024","--codec","zlib","--level","6"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)

    man = out_dir / "CL6_MANIFEST_v3.json"
    # Sign & verify
    key = "test-secret-key"
    res_s = subprocess.run([sys.executable, str(cli), "sign", "--path", str(man), "--key", key, "--kid", "conf"], capture_output=True, text=True)
    print(res_s.stdout)
    res_v = subprocess.run([sys.executable, str(cli), "verify", "--path", str(man), "--key", key], capture_output=True, text=True)
    print(res_v.stdout)

    # Validate strict explicitly (after signing)
    cmd = [sys.executable, str(cli), "validate", "--path", str(man), "--strict", "--chunks-dir", str(out_dir/"chunks")]
    res2 = subprocess.run(cmd, capture_output=True, text=True)
    print(res2.stdout)
    if res2.returncode != 0:
        print(res2.stderr, file=sys.stderr)
        sys.exit(res2.returncode)

    dr = json.loads((out_dir/"DELTA_REPORT.json").read_text())
    # Compute avg compression ratio from 'z' fields
    man_obj = json.loads(man.read_text())
    ratios = [ch.get("z",{}).get("ratio",1.0) for ch in man_obj.get("chunks",[])]
    avg_ratio = sum(ratios)/len(ratios) if ratios else 1.0

    report = {
        "v1_bytes": dr["v1"]["bytes"],
        "v2_bytes": dr["v2"]["bytes"],
        "reuse_pct": dr["stats"]["reuse_pct"],
        "new_bytes": dr["stats"]["new_bytes"],
        "total_chunks": dr["stats"]["total_chunks"],
        "avg_compression_ratio": avg_ratio
    }
    (base / "CONFORMANCE_REPORT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
