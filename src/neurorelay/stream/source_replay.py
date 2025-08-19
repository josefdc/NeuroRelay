from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Tuple

import numpy as np


@dataclass
class ReplayConfig:
    sample_rate_hz: float = 250.0
    chunk_sec: float = 1.0
    channels: List[str] | None = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = ["O1", "Oz", "O2"]


def load_csv(path: Path) -> Tuple[np.ndarray, List[str]]:
    """
    Expect CSV with header: t,O1,Oz,O2,label
    Returns array of shape (n, 5): columns [t, O1, Oz, O2, label_index]
    """
    import csv

    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = {name: i for i, name in enumerate(header)}
        rows: list[tuple[float, float, float, float, float]] = []
        label_map = {"SUMMARIZE": 0, "TODOS": 1, "DEADLINES": 2, "EMAIL": 3}
        for r in reader:
            t = float(r[cols["t"]])
            o1 = float(r[cols["O1"]])
            oz = float(r[cols["Oz"]])
            o2 = float(r[cols["O2"]])
            label = r[cols.get("label", -1)] if "label" in cols else ""
            lab_idx = float(label_map.get(label, -1))
            rows.append((t, o1, oz, o2, lab_idx))
    arr = np.asarray(rows, dtype=float)
    return arr, header


essr = 1e-9


def replay_chunks(path: Path, cfg: ReplayConfig) -> Generator[np.ndarray, None, None]:
    """
    Stream CSV in chunks of cfg.chunk_sec without loading everything into memory.
    CSV header: t,O1,Oz,O2,label
    """
    import csv
    import time

    sr = cfg.sample_rate_hz
    chunk_n = max(1, int(sr * cfg.chunk_sec))
    buf = []

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            buf.append([float(row["O1"]), float(row["Oz"]), float(row["O2"])])
            if len(buf) >= chunk_n:
                x = np.asarray(buf, dtype=float)
                yield x
                buf.clear()
                time.sleep(cfg.chunk_sec)  # pace at ~real-time

        if buf:
            x = np.asarray(buf, dtype=float)
            yield x
