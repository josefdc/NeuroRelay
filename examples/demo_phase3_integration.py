#!/usr/bin/env python3
"""Demonstrate Phase 3 live integration functionality."""

import time
import json
import tempfile
from pathlib import Path


def demo_phase3_integration():
    """Demo showing Phase 3 components working together."""
    print("🧠 NeuroRelay Phase 3 Integration Demo")
    print("=" * 50)
    
    # 1. Test configuration loading
    print("\n1. Testing configuration loading...")
    config_data = {
        "monitor_hz": 60.0,
        "freqs_hz": [8.57, 10.0, 12.0, 15.0],
        "window_sec": 3.0,
        "dwell_sec": 1.2,
        "tau": 0.65,
        "channels": ["O1", "Oz", "O2"],
        "bandpass_hz": [5, 40],
        "notch_hz": 60
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        config_path = Path(f.name)
    
    try:
        from neurorelay.ui.ssvep_4buttons import UiConfig
        cfg = UiConfig.from_json(config_path)
        print(f"  ✓ Config loaded: {len(cfg.freqs_hz)} frequencies, τ={cfg.tau}")
    finally:
        config_path.unlink(missing_ok=True)
    
    # 2. Test SSVEP detector components
    print("\n2. Testing SSVEP detection pipeline...")
    try:
        from neurorelay.signal.ssvep_detector import SSVEPDetector, SSVEPConfig
        import numpy as np
        
        # Create detector with config from UI
        channels = config_data["channels"]  # Use raw config data
        ssvep_cfg = SSVEPConfig(
            frequencies=cfg.freqs_hz,
            sample_rate=250.0,
            window_seconds=cfg.window_sec,
            channels=channels,
            method="cca"
        )
        detector = SSVEPDetector(ssvep_cfg)
        
        # Generate synthetic 10 Hz SSVEP
        t = np.linspace(0, cfg.window_sec, int(cfg.window_sec * 250))
        signal_10hz = np.sin(2 * np.pi * 10.0 * t) + 0.1 * np.random.randn(len(t))
        data = np.column_stack([signal_10hz] * len(channels))
        
        # Detect
        freq, conf, scores = detector.detect(data)
        print(f"  ✓ Detected {freq} Hz with confidence {conf:.3f}")
        print(f"    Scores: {[f'{f}:{s:.3f}' for f,s in scores.items()]}")
        
    except ImportError as e:
        print(f"  ⚠ SSVEP detector not available: {e}")
        ssvep_cfg = None  # Set fallback for later use
    
    # 3. Test live bridge components (if available)
    print("\n3. Testing live bridge components...")
    try:
        from neurorelay.bridge.qt_live_bridge import LivePredictor
        from neurorelay.stream.lsl_source import LSLConfig
        from neurorelay.signal.ssvep_detector import SSVEPConfig
        
        # Create fresh ssvep config for live bridge test
        channels = config_data["channels"]  # Use raw config data
        ssvep_cfg_live = SSVEPConfig(
            frequencies=cfg.freqs_hz,
            sample_rate=250.0,
            window_seconds=cfg.window_sec,
            channels=channels,
            method="cca"
        )
        
        # Just test construction, not actual connection
        lsl_cfg = LSLConfig(
            stream_type="EEG",
            stream_name=None,
            timeout=1.0,  # Short timeout for demo
            buffer_seconds=cfg.window_sec + 1.0,
        )
        
        predictor = LivePredictor(lsl_cfg, ssvep_cfg_live)
        print(f"  ✓ LivePredictor created successfully")
        print(f"    LSL config: {lsl_cfg.stream_type}, buffer={lsl_cfg.buffer_seconds:.1f}s")
        
        # Test Qt signal setup
        signal_names = ['prediction', 'status_changed', 'data_received']
        for name in signal_names:
            assert hasattr(predictor, name), f"Missing signal: {name}"
        print(f"  ✓ Qt signals available: {signal_names}")
        
    except ImportError as e:
        print(f"  ⚠ Live bridge not available: {e}")
    
    # 4. Test stability and dwell logic simulation
    print("\n4. Testing selection stability logic...")
    
    # Simulate prediction sequence with stability requirements
    predictions = [
        (10.0, 0.45),  # Below threshold
        (10.0, 0.70),  # Above threshold, count 1
        (10.0, 0.75),  # Same winner, count 2  
        (10.0, 0.82),  # Same winner, count 3 - now stable!
        (10.0, 0.78),  # Stable continues
    ]
    
    stable_idx = None
    stable_count = 0
    threshold = cfg.tau
    
    print(f"    Threshold τ = {threshold}")
    for i, (freq, conf) in enumerate(predictions):
        current_idx = cfg.freqs_hz.index(freq) if freq in cfg.freqs_hz else 0
        
        if stable_idx == current_idx:
            stable_count += 1
        else:
            stable_idx = current_idx
            stable_count = 1
            
        stable = stable_count >= 3
        above_thresh = conf >= threshold
        can_dwell = stable and above_thresh
        
        print(f"    Step {i+1}: {freq}Hz conf={conf:.2f} stable={stable} can_dwell={can_dwell}")
        
        if can_dwell and i >= 3:
            print(f"  ✓ Selection would trigger dwell at step {i+1}")
            break
    
    # 5. Test commit simulation
    print("\n5. Testing commit logic...")
    winner_idx = 1  # TODOS
    winner_conf = 0.82
    labels = ["SUMMARIZE", "TODOS", "DEADLINES", "EMAIL"]
    
    commit_msg = f"agent: {labels[winner_idx].lower()} • conf={winner_conf:.2f} (Phase 3 commit)"
    print(f"  ✓ Commit message: '{commit_msg}'")
    
    print("\n🎯 Phase 3 Integration Demo Complete!")
    print("\nKey features demonstrated:")
    print("  • Configuration loading and validation")
    print("  • SSVEP detection pipeline")  
    print("  • Live bridge component construction")
    print("  • Stability and dwell selection logic")
    print("  • Commit message formatting")
    print("\nReady for live EEG integration! 🧠→🤖")


if __name__ == "__main__":
    demo_phase3_integration()