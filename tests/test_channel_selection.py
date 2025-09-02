#!/usr/bin/env python3
"""Test that channel selection fix works correctly in the live bridge."""

import numpy as np
import pytest
from neurorelay.signal.ssvep_detector import SSVEPDetector, SSVEPConfig


def test_channel_selection_with_names():
    """Test that channel names are properly used for channel selection."""
    # Create detector configured for specific channels
    config = SSVEPConfig(
        frequencies=[8.0, 10.0, 12.0, 15.0],
        sample_rate=250.0,
        window_seconds=3.0,
        channels=["O1", "Oz", "O2"],  # Only want these 3 channels
        method="cca"
    )
    detector = SSVEPDetector(config)
    
    # Generate synthetic data with more channels than we want
    t = np.linspace(0, 3.0, 750)  # 3s at 250Hz
    signal_10hz = np.sin(2 * np.pi * 10.0 * t) + 0.1 * np.random.randn(750)
    
    # Simulate 6-channel data where channels 1,3,4 are the ones we want
    all_channels = np.column_stack([
        np.random.randn(750),      # Channel 0: noise
        signal_10hz,               # Channel 1: O1 (signal)
        np.random.randn(750),      # Channel 2: noise  
        signal_10hz,               # Channel 3: Oz (signal)
        signal_10hz,               # Channel 4: O2 (signal)
        np.random.randn(750)       # Channel 5: noise
    ])
    
    # Test without channel names (should use all channels - less accurate)
    freq_all, conf_all, scores_all = detector.detect(all_channels)
    
    # Test with channel names (should select only the signal channels)
    channel_names = ["Fp1", "O1", "Fp2", "Oz", "O2", "T7"]  # Names for our 6 channels
    freq_selected, conf_selected, scores_selected = detector.detect(all_channels, channel_names)
    
    print(f"Without channel selection: {freq_all} Hz, conf={conf_all:.3f}")
    print(f"With channel selection: {freq_selected} Hz, conf={conf_selected:.3f}")
    
    # With proper channel selection, we should detect 10 Hz more confidently
    # since we're only using the signal channels, not the noise ones
    assert freq_selected == 10.0, f"Should detect 10 Hz with channel selection, got {freq_selected}"
    assert conf_selected > conf_all, f"Channel selection should improve confidence: {conf_selected:.3f} vs {conf_all:.3f}"
    
    print("✓ Channel selection improves detection accuracy")


def test_live_bridge_integration():
    """Test that the live bridge properly passes channel names to detector."""
    try:
        from neurorelay.bridge.qt_live_bridge import LivePredictor
        from neurorelay.stream.lsl_source import LSLConfig
        
        # Create live predictor configured for specific channels
        lsl_config = LSLConfig(
            stream_type="EEG",
            timeout=1.0,
            buffer_seconds=4.0
        )
        
        ssvep_config = SSVEPConfig(
            frequencies=[8.57, 10.0, 12.0, 15.0],
            sample_rate=250.0,
            window_seconds=3.0,
            channels=["O1", "Oz", "O2"],  # Only want occipital channels
            method="cca"
        )
        
        predictor = LivePredictor(lsl_config, ssvep_config)
        
        # Verify configuration was stored correctly
        assert predictor.ssvep_config.channels == ["O1", "Oz", "O2"]
        assert predictor.detector.config.channels == ["O1", "Oz", "O2"]
        
        print("✓ LivePredictor correctly configured with channel selection")
        
        # Note: We can't test the actual _predict method without a real LSL stream,
        # but we can verify the configuration is set up correctly for channel selection
        
    except ImportError:
        print("ℹ Live bridge not available (pylsl not installed)")
        pytest.skip("Live bridge components not available")


if __name__ == "__main__":
    test_channel_selection_with_names()
    test_live_bridge_integration()
    print("\nAll channel selection tests passed! 🎯")