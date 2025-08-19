#src/neurorelay/scripts/synthetic_ssvep.py
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import List, Tuple

import numpy as np

LABELS = ("SUMMARIZE", "TODOS", "DEADLINES", "EMAIL")


def make_session(
    out_csv: Path,
    sample_rate_hz: float = 250.0,
    monitor_hz: float = 60.0,
    freqs_hz: Tuple[float, float, float, float] = (8.57, 10.0, 12.0, 15.0),
    block_order: Tuple[int, ...] = (0, 1, 2, 3, 0, 2, 1, 3),
    eval_sec: float = 3.0,
    dwell_sec: float = 1.2,
    rest_sec: float = 0.8,
    noise_sigma: float = 0.15,
    seed: int | None = None,
) -> None:
    sr = sample_rate_hz
    blocks = []
    for idx in block_order:
        f = freqs_hz[idx]
        blocks.append(("focus", idx, f, eval_sec))
        blocks.append(("dwell", idx, f, dwell_sec))
        blocks.append(("rest", -1, 0.0, rest_sec))

    all_t: List[float] = []
    o1: List[float] = []
    oz: List[float] = []
    o2: List[float] = []
    labels: List[str] = []
    t_acc = 0.0

    # Initialize RNG with optional seed for reproducibility
    rng = np.random.default_rng(seed)

    def add_sine_block(tag: str, label_idx: int, f_hz: float, seconds: float) -> None:
        nonlocal t_acc
        n = int(round(seconds * sr))
        t = (np.arange(n) / sr) + t_acc
        if f_hz > 0:
            g = 1.0 if tag == "focus" else 1.35 if tag == "dwell" else 0.0
            base = g * (np.sin(2 * math.pi * f_hz * t) + 0.35 * np.sin(2 * math.pi * 2 * f_hz * t))
        else:
            base = np.zeros_like(t)
        o1_sig = 0.9 * base + rng.normal(0, noise_sigma, size=n)
        oz_sig = 1.1 * base + rng.normal(0, noise_sigma, size=n)
        o2_sig = 0.95 * base + rng.normal(0, noise_sigma, size=n)

        all_t.extend(t.tolist())
        o1.extend(o1_sig.tolist())
        oz.extend(oz_sig.tolist())
        o2.extend(o2_sig.tolist())
        lab = LABELS[label_idx] if 0 <= label_idx < 4 else ""
        labels.extend([lab] * n)
        t_acc += seconds

    for tag, idx, f, secs in blocks:
        add_sine_block(tag, idx, f, secs)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "O1", "Oz", "O2", "label"])
        for i in range(len(all_t)):
            w.writerow([f"{all_t[i]:.6f}", f"{o1[i]:.6f}", f"{oz[i]:.6f}", f"{o2[i]:.6f}", labels[i]])


def main() -> int:
    p = argparse.ArgumentParser(description="Generate synthetic SSVEP CSV for replay")
    p.add_argument("--out", default="data/sim_session.csv", help="Output CSV path")
    p.add_argument("--sr", type=float, default=250.0, help="Sample rate (Hz)")
    p.add_argument("--monitor-hz", type=float, default=60.0, help="Monitor refresh (Hz)")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducible data")
    p.add_argument("--freqs", type=str, default="", help='Comma list (e.g. "8.57,10,12,15") or "auto" for monitor_hz/[7,6,5,4]')
    args = p.parse_args()
    
    out = Path(args.out)
    
    # Handle frequency specification
    if args.freqs.strip().lower() == "auto":
        freqs = (args.monitor_hz/7.0, args.monitor_hz/6.0, args.monitor_hz/5.0, args.monitor_hz/4.0)
        print(f"Auto frequencies for {args.monitor_hz} Hz: {freqs}")
    elif args.freqs:
        parts = [float(x.strip()) for x in args.freqs.split(",")]
        assert len(parts) == 4, "--freqs must have exactly 4 values"
        freqs = (parts[0], parts[1], parts[2], parts[3])
    else:
        freqs = (8.57, 10.0, 12.0, 15.0)
    
    print(f"Using frequencies: {freqs}")
    
    make_session(
        out_csv=out, 
        sample_rate_hz=args.sr, 
        monitor_hz=args.monitor_hz, 
        freqs_hz=freqs,
        seed=args.seed
    )
    print(f"Wrote {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
