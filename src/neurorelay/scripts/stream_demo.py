#src/neurorelay/scripts/stream_demo.py
"""Console demo for live SSVEP detection via LSL."""

import argparse
import time
import sys
from typing import List

from ..stream.lsl_source import LSLSource, LSLConfig
from ..signal.ssvep_detector import SSVEPDetector, SSVEPConfig


def parse_frequencies(freq_str: str) -> List[float]:
    """Parse comma-separated frequency string."""
    return [float(f.strip()) for f in freq_str.split(',')]


def main():
    parser = argparse.ArgumentParser(description="Live SSVEP detector console demo")
    
    # LSL options
    parser.add_argument('--stream-type', default='EEG', help='LSL stream type')
    parser.add_argument('--stream-name', help='LSL stream name (optional)')
    parser.add_argument('--timeout', type=float, default=5.0, help='LSL connection timeout')
    
    # SSVEP detection options  
    parser.add_argument('--freqs', default="8.57,10,12,15", help='Target frequencies (Hz), comma-separated (default: 8.57,10,12,15)')
    parser.add_argument('--window', type=float, default=3.0, help='Analysis window (seconds)')
    parser.add_argument('--step', type=float, default=0.5, help='Prediction step (seconds)')
    parser.add_argument('--channels', help='EEG channels, comma-separated (optional)')
    parser.add_argument('--bandpass', default='5,40', help='Bandpass filter range (Hz)')
    parser.add_argument('--notch', type=float, help='Notch filter frequency (Hz)')
    parser.add_argument('--method', default='cca', choices=['cca', 'power'], help='Detection method')
    
    # Display options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--max-predictions', type=int, help='Max predictions before exit')
    
    args = parser.parse_args()
    
    # Parse arguments
    frequencies = parse_frequencies(args.freqs)
    channels = [c.strip() for c in args.channels.split(',')] if args.channels else None
    try:
        lo, hi = (float(x) for x in args.bandpass.split(','))
        bandpass = (lo, hi)
    except Exception:
        print("Invalid --bandpass. Use 'low,high' (e.g., 5,40).")
        return 1
    
    # Create configurations
    lsl_config = LSLConfig(
        stream_type=args.stream_type,
        stream_name=args.stream_name,
        timeout=args.timeout,
        buffer_seconds=args.window + 2.0  # Extra buffer
    )
    
    ssvep_config = SSVEPConfig(
        frequencies=frequencies,
        sample_rate=250.0,  # Will be updated from LSL
        window_seconds=args.window,
        channels=channels,
        bandpass_freq=bandpass,
        notch_freq=args.notch,
        method=args.method
    )
    
    print(f"NeuroRelay Live SSVEP Demo")
    print(f"Target frequencies: {frequencies} Hz")
    print(f"Window: {args.window}s, Step: {args.step}s")
    print(f"Method: {args.method}")
    if channels:
        print(f"Channels: {channels}")
    print()
    
    # Initialize components
    lsl_source = LSLSource(lsl_config)
    detector = SSVEPDetector(ssvep_config)
    
    try:
        # Connect to LSL
        print("Connecting to LSL stream...")
        if not lsl_source.connect():
            print("Failed to connect to LSL stream")
            return 1
        
        # Update detector with actual sample rate
        if lsl_source.sample_rate:
            detector.update_config(sample_rate=lsl_source.sample_rate)
            print(f"Sample rate: {lsl_source.sample_rate} Hz")
        
        # Start acquisition
        print("Starting data acquisition...")
        if not lsl_source.start():
            print("Failed to start LSL acquisition")
            return 1
        
        # Wait for initial data
        print(f"Waiting {args.window}s for initial data...")
        time.sleep(args.window + 0.5)
        
        print("\nStarting predictions (Ctrl+C to stop):")
        print("=" * 50)
        
        prediction_count = 0
        
        while True:
            # Get latest data
            data, timestamps, metadata = lsl_source.get_latest_data(args.window)
            
            # Check if we have enough data (including filter padding requirements)
            min_needed = max(10, detector.min_padlen() + 8)  # small safety margin
            if data is None or data.shape[0] < min_needed:
                if args.verbose:
                    print(f"Waiting for more data... (need {min_needed}, have {data.shape[0] if data is not None else 0})")
                time.sleep(0.1)
                continue
            
            # Run detection
            frequency, confidence, scores = detector.detect(
                data,
                metadata.get('channel_names') if metadata else None
            )
            
            # Display result
            if args.verbose:
                print(f"Samples: {data.shape[0]:4d} | ", end="")
                for freq in sorted(scores.keys()):
                    print(f"{freq:5.1f}Hz: {scores[freq]:.3f} | ", end="")
                print()
            
            print(f"Prediction: {frequency:5.1f} Hz | Confidence: {confidence:.3f}")
            
            prediction_count += 1
            if args.max_predictions and prediction_count >= args.max_predictions:
                break
            
            # Wait before next prediction
            time.sleep(max(0.0, args.step))
            
    except KeyboardInterrupt:
        print("\nStopping...")
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    finally:
        lsl_source.stop()
        print("Demo finished.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())