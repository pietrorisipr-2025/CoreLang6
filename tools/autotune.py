#!/usr/bin/env python3
"""Suggest CL6 profile params from RTT (ms) and throughput (Mbit/s)."""
import argparse, math, json

def autotune(rtt_ms: float, mbit_s: float):
    bps = mbit_s * 1e6
    bdp_bytes = bps * (rtt_ms / 1000.0)
    # target chunk size around 1/16 of BDP, clamped
    avg_kib = int(max(256, min(1024, (bdp_bytes / 16) / 1024)))
    # concurrency ~ BDP / (avg_chunk) clamped 2..64
    conc = int(max(2, min(64, math.ceil(bdp_bytes / (avg_kib*1024)))))
    streams = conc
    return {
        "rtt_ms": rtt_ms, "mbit_s": mbit_s,
        "recommendation": {
            "avg_kib": avg_kib, "min_kib": max(128, avg_kib//2), "max_kib": min(2048, avg_kib*2),
            "http": {"h3_concurrency": conc, "streams": streams}
        }
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtt-ms", type=float, required=True)
    ap.add_argument("--mbit-s", type=float, required=True)
    args = ap.parse_args()
    print(json.dumps(autotune(args.rtt_ms, args.mbit_s), indent=2))

if __name__ == "__main__":
    main()
