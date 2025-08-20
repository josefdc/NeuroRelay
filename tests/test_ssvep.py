"""Tests for SSVEP detection."""

import numpy as np
import pytest
from neurorelay.signal.ssvep_detector import SSVEPDetector, SSVEPConfig, generate_reference_signals


def test_ssvep_config():
    """Test SSVEP configuration."""
    config = SSVEPConfig(
        frequencies=[8.0, 10.0, 12.0, 15.0],
        sample_rate=250.0,
        window_seconds=3.0
    )
    
    assert len(config.frequencies) == 4
    assert config.sample_rate == 250.0
    assert config.window_seconds == 3.0


def test_reference_generation():
    """Test reference signal generation."""
    frequencies = [8.0, 10.0]
    sample_rate = 250.0
    duration = 2.0
    
    refs = generate_reference_signals(frequencies, sample_rate, duration, harmonics=2)
    
    assert len(refs) == 2  # Two frequencies
    for freq, ref_signal in refs.items():
        assert ref_signal.shape[0] == int(duration * sample_rate)  # Correct length
        assert ref_signal.shape[1] == 4  # 2 harmonics * 2 (sin/cos) = 4 references


def test_ssvep_detector_creation():
    """Test SSVEP detector creation."""
    config = SSVEPConfig(
        frequencies=[8.0, 10.0, 12.0],
        sample_rate=250.0,
        window_seconds=2.0
    )
    
    detector = SSVEPDetector(config)
    
    assert len(detector.references) == 3
    assert detector.config.sample_rate == 250.0
    
    # Test min_padlen method
    min_pad = detector.min_padlen()
    assert min_pad >= 0
    assert isinstance(min_pad, int)


def test_synthetic_ssvep_detection():
    """Test SSVEP detection on synthetic data."""
    # Create config
    target_freq = 10.0
    frequencies = [8.0, target_freq, 12.0, 15.0]
    sample_rate = 250.0
    duration = 3.0
    
    config = SSVEPConfig(
        frequencies=frequencies,
        sample_rate=sample_rate,
        window_seconds=duration
    )
    
    detector = SSVEPDetector(config)
    
    # Generate synthetic SSVEP data (3 channels)
    n_samples = int(duration * sample_rate)
    n_channels = 3
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    # Create signal with target frequency + noise
    signal = np.sin(2 * np.pi * target_freq * t)
    noise = 0.1 * np.random.randn(n_samples)
    
    data = np.zeros((n_samples, n_channels))
    for ch in range(n_channels):
        data[:, ch] = signal + noise * (0.5 + ch * 0.1)  # Slightly different noise per channel
    
    # Run detection
    detected_freq, confidence, scores = detector.detect(data)
    
    # Should detect the target frequency
    assert detected_freq == target_freq
    assert confidence > 0.1  # Some reasonable confidence
    assert len(scores) == len(frequencies)
    assert target_freq in scores


def test_preprocessing():
    """Test data preprocessing."""
    config = SSVEPConfig(
        frequencies=[10.0],
        sample_rate=250.0,
        window_seconds=2.0,
        bandpass_freq=(5.0, 40.0),
        notch_freq=50.0
    )
    
    detector = SSVEPDetector(config)
    
    # Create test data
    n_samples = 500
    n_channels = 2
    data = np.random.randn(n_samples, n_channels)
    
    # Apply preprocessing
    filtered = detector.preprocess(data)
    
    assert filtered.shape == data.shape
    assert not np.array_equal(filtered, data)  # Should be different after filtering


def test_empty_data_handling():
    """Test handling of empty or invalid data."""
    config = SSVEPConfig(
        frequencies=[10.0],
        sample_rate=250.0
    )
    
    detector = SSVEPDetector(config)
    
    # Empty data
    empty_data = np.array([]).reshape(0, 3)
    freq, conf, scores = detector.detect(empty_data)
    
    assert freq == 0.0
    assert conf == 0.0
    assert len(scores) == 0


def test_config_update():
    """Test configuration updates."""
    config = SSVEPConfig(
        frequencies=[10.0],
        sample_rate=250.0,
        window_seconds=2.0
    )
    
    detector = SSVEPDetector(config)
    original_refs = len(detector.references)
    
    # Update frequencies
    detector.update_config(frequencies=[8.0, 10.0, 12.0])
    
    assert len(detector.references) == 3
    assert len(detector.references) != original_refs


def test_12hz_synthetic_detection():
    """Test SSVEP detection on 12 Hz synthetic signal."""
    # Create config with multiple frequencies including 12 Hz
    frequencies = [8.0, 10.0, 12.0, 15.0]
    sample_rate = 250.0
    duration = 2.5  # Shorter for faster test
    
    config = SSVEPConfig(
        frequencies=frequencies,
        sample_rate=sample_rate,
        window_seconds=duration,
        bandpass_freq=(6.0, 40.0),  # Wider band
        notch_freq=None  # No notch for synthetic
    )
    
    detector = SSVEPDetector(config)
    
    # Generate synthetic SSVEP at 12 Hz with some noise
    n_samples = int(duration * sample_rate)
    n_channels = 3
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    # Strong 12 Hz signal with light noise
    target_freq = 12.0
    signal = np.sin(2 * np.pi * target_freq * t) + 0.05 * np.random.randn(n_samples)
    
    data = np.zeros((n_samples, n_channels))
    for ch in range(n_channels):
        # Add slight variation per channel
        noise_factor = 0.8 + ch * 0.1  # 0.8, 0.9, 1.0
        data[:, ch] = signal + 0.02 * noise_factor * np.random.randn(n_samples)
    
    # Run detection
    detected_freq, confidence, scores = detector.detect(data)
    
    # Should detect the 12 Hz target
    assert detected_freq == target_freq, f"Expected {target_freq} Hz, got {detected_freq} Hz"
    assert confidence > 0.4, f"Low confidence: {confidence:.3f}"  # Should be reasonably confident
    
    # 12 Hz should have the highest score
    max_score_freq = max(scores.keys(), key=lambda f: scores[f])
    assert max_score_freq == target_freq
    
    # Score should be meaningfully higher than others
    target_score = scores[target_freq]
    other_scores = [scores[f] for f in scores if f != target_freq]
    if other_scores:
        max_other = max(other_scores)
        assert target_score > max_other * 1.2, "Target frequency should be clearly dominant"


if __name__ == '__main__':
    pytest.main([__file__])