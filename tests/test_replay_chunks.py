import numpy as np
from pathlib import Path
from neurorelay.stream.source_replay import ReplayConfig, replay_chunks


def test_replay_yields_chunks():
    """Test that replay_chunks yields numpy arrays with expected shape."""
    cfg = ReplayConfig(sample_rate_hz=250.0, chunk_sec=0.2, realtime=False)
    chunks = list(replay_chunks(Path("data/demo.csv"), cfg))
    assert len(chunks) > 0
    assert all(isinstance(c, np.ndarray) and c.shape[1] == 3 for c in chunks)


def test_replay_config_realtime_false():
    """Test that realtime=False doesn't sleep between chunks."""
    import time
    cfg = ReplayConfig(sample_rate_hz=250.0, chunk_sec=1.0, realtime=False)
    start = time.time()
    chunks = list(replay_chunks(Path("data/demo.csv"), cfg))
    elapsed = time.time() - start
    # Should complete much faster than real-time when realtime=False
    expected_realtime = len(chunks) * cfg.chunk_sec
    assert elapsed < expected_realtime * 0.1  # Should be <10% of real-time