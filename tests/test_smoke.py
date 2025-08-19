import json
from pathlib import Path
import subprocess
import sys


def test_config_loads_and_has_freqs():
    cfg = json.loads(Path("config/default.json").read_text())
    assert "freqs_hz" in cfg and len(cfg["freqs_hz"]) == 4


def test_cli_runs():
    subprocess.check_call([sys.executable, "-m", "neurorelay", "--print-config"])
