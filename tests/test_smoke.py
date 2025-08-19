import json
from pathlib import Path
import subprocess
import sys
import pytest


def test_config_loads_and_has_freqs():
    cfg = json.loads(Path("config/default.json").read_text())
    assert "freqs_hz" in cfg and len(cfg["freqs_hz"]) == 4


def test_cli_runs():
    subprocess.check_call([sys.executable, "-m", "neurorelay", "--print-config"])


def test_ui_import():
    """Test UI module imports (skip if PySide6 not available)."""
    pytest.importorskip("PySide6")
    import neurorelay.ui.ssvep_4buttons as ui
    assert hasattr(ui, "NeuroRelayWindow")
