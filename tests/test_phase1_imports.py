import pytest


def test_import_ui_module():
    """Test that UI module imports successfully when PySide6 is available."""
    pytest.importorskip("PySide6")
    import neurorelay.ui.ssvep_4buttons as ui
    assert hasattr(ui, "NeuroRelayWindow")
    assert hasattr(ui, "FlickerTile")
    assert hasattr(ui, "UiConfig")


def test_import_replay_module():
    """Test that replay module imports and has expected functions."""
    import neurorelay.stream.source_replay as replay
    assert hasattr(replay, "load_csv")
    assert hasattr(replay, "replay_chunks")
    assert hasattr(replay, "ReplayConfig")


def test_import_synthetic_generator():
    """Test that synthetic generator module imports and has main function."""
    import neurorelay.scripts.synthetic_ssvep as synth
    assert hasattr(synth, "make_session")
    assert hasattr(synth, "main")
    assert hasattr(synth, "LABELS")
    assert synth.LABELS == ("SUMMARIZE", "TODOS", "DEADLINES", "EMAIL")


def test_auto_freqs_match_ui_assumption(tmp_path):
    """Test that auto-freqs calculation matches UI assumption."""
    from neurorelay.scripts.synthetic_ssvep import make_session
    
    # UI auto-freqs: monitor_hz / [7,6,5,4]
    mhz = 60.0
    freqs = (mhz/7.0, mhz/6.0, mhz/5.0, mhz/4.0)
    out = tmp_path / "sim_auto.csv"
    make_session(out_csv=out, monitor_hz=mhz, freqs_hz=freqs, seed=7)
    assert out.exists() and out.stat().st_size > 0