from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neurorelay", description="NeuroRelay CLI (phase 0)")
    parser.add_argument("--config", default="config/default.json", help="Path to config JSON")
    parser.add_argument("--print-config", action="store_true", help="Pretty-print loaded config and exit")
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        found = True
    else:
        cfg = {}
        found = False

    if args.print_config:
        import pprint

        pprint.pprint(cfg)
        return 0

    print("NeuroRelay skeleton ready ✅")
    print(f"Config: {cfg_path.resolve()} ({'found' if found else 'missing'})")
    print(f"Frequencies: {cfg.get('freqs_hz', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
