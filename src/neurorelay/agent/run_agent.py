# src/neurorelay/agent/run_agent.py
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..agent.tools_local import AgentConfig, handle_selection


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int((time.time()%1)*1000):03d}Z"


def load_config() -> AgentConfig:
    cfg_path = Path("config/default.json")
    sandbox_root = Path("workspace")
    out_dir = Path("workspace/out")
    if cfg_path.exists():
        try:
            raw = json.loads(cfg_path.read_text())
            sandbox_root = Path(raw.get("sandbox_root", "workspace"))
            out_dir = Path(raw.get("out_dir", "workspace/out"))
        except Exception:
            pass
    return AgentConfig(sandbox_root=sandbox_root, out_dir=out_dir, in_dir=sandbox_root / "in")


def log_event(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main() -> int:
    cfg = load_config()
    log_path = Path("logs/agent.jsonl")
    # A small hello banner on stdout so parent knows we're alive (also JSON)
    hello = {
        "type": "agent_hello",
        "ts": now_iso(),
        "agent": {"name": "gpt-oss-local", "version": "0.1.0"},
        "sandbox_root": str(cfg.sandbox_root),
        "out_dir": str(cfg.out_dir),
    }
    print(json.dumps(hello, ensure_ascii=False), flush=True)

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception as e:
            err = {"type": "agent_error", "ts": now_iso(), "error": f"bad json: {e!r}"}
            print(json.dumps(err, ensure_ascii=False), flush=True)
            log_event(log_path, err)
            continue

        # Only handle SELECT
        intent = (event.get("intent") or {}).get("name")
        args = (event.get("intent") or {}).get("args") or {}
        label = (args.get("label") or "").upper()
        conf = float(event.get("confidence", 0.0))
        ctx = event.get("context") or {}
        file = Path(ctx["file"]).resolve() if ctx.get("file") else None
        topic = ctx.get("topic")

        log_event(log_path, {"type": "agent_event", "ts": now_iso(), "recv": event})

        if intent != "SELECT":
            out = {"type": "agent_result", "ts": now_iso(), "status": "ignored", "reason": "non-select"}
            print(json.dumps(out, ensure_ascii=False), flush=True)
            continue

        # Run tool
        result = handle_selection(label, cfg, file=file, topic=topic)

        payload = {
            "type": "agent_result",
            "ts": now_iso(),
            "label": label,
            "confidence": conf,
            **result,
        }
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        log_event(log_path, payload)

    bye = {"type": "agent_bye", "ts": now_iso()}
    print(json.dumps(bye, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())