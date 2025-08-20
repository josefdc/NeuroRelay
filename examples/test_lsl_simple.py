#!/usr/bin/env python3
"""Simple LSL stream creator for testing NeuroRelay."""

import time
import numpy as np
import threading
from pylsl import StreamInfo, StreamOutlet

def create_synthetic_eeg_stream(duration_sec=30):
    """Create a synthetic EEG stream with SSVEP-like signals."""
    # Create stream info
    info = StreamInfo(
        name="TestEEGStream",
        type="EEG", 
        channel_count=8,
        nominal_srate=250,
        channel_format="float32",  # This should work with recent pylsl
        source_id="test_neurorelay"
    )
    
    # Add channel information
    chns = info.desc().append_child("channels")
    for i, ch_name in enumerate(["O1", "O2", "Oz", "P3", "P4", "Pz", "C3", "C4"]):
        ch = chns.append_child("channel")
        ch.append_child_value("label", ch_name)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    
    # Create outlet
    outlet = StreamOutlet(info)
    print(f"Created LSL outlet: {info.name()} ({info.type()})")
    print("Streaming synthetic EEG with SSVEP-like signals...")
    print("Frequencies: 8.57 Hz (strong), 10 Hz (medium), 12 Hz (weak), 15 Hz (noise)")
    
    start_time = time.time()
    sample_rate = 250
    dt = 1.0 / sample_rate
    
    try:
        while time.time() - start_time < duration_sec:
            t = time.time() - start_time
            
            # Generate synthetic data with multiple SSVEP frequencies
            # Channel 1 (O1): Strong 8.57 Hz signal
            ch1 = 0.5 * np.sin(2 * np.pi * 8.57 * t) + 0.1 * np.random.randn()
            
            # Channel 2 (O2): Medium 10 Hz signal  
            ch2 = 0.3 * np.sin(2 * np.pi * 10.0 * t) + 0.1 * np.random.randn()
            
            # Channel 3 (Oz): Weak 12 Hz signal
            ch3 = 0.2 * np.sin(2 * np.pi * 12.0 * t) + 0.1 * np.random.randn()
            
            # Remaining channels: mostly noise with weak 15 Hz
            noise_channels = [
                0.1 * np.sin(2 * np.pi * 15.0 * t) + 0.2 * np.random.randn()
                for _ in range(5)
            ]
            
            sample = [ch1, ch2, ch3] + noise_channels
            outlet.push_sample(sample)
            
            time.sleep(dt)
            
    except KeyboardInterrupt:
        print("\nStream stopped by user")
    
    print("Stream finished")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create synthetic EEG stream for testing")
    parser.add_argument("--duration", type=float, default=30, help="Stream duration (seconds)")
    args = parser.parse_args()
    
    create_synthetic_eeg_stream(args.duration)