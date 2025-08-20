#!/bin/bash
# Test script for NeuroRelay Phase 2 LSL functionality
# Run this to test the complete pipeline: synthetic stream -> live detection

echo "🧠 NeuroRelay Phase 2 Test - LSL Live Detection"
echo "=============================================="
echo

# Check if LSL is properly installed
if ! python3 -c "import pylsl; print('LSL version:', pylsl.__version__)" 2>/dev/null; then
    echo "❌ Error: pylsl not working properly"
    echo "Make sure you have installed liblsl:"
    echo "  sudo dpkg -i liblsl-1.16.2-noble_amd64.deb"
    echo "  sudo apt install -f"
    exit 1
fi

echo "✅ LSL library found and working"
echo

# Start synthetic stream in background
echo "🔧 Starting synthetic EEG stream..."
uv run python examples/test_lsl_simple.py --duration 60 &
STREAM_PID=$!

# Give stream time to start
sleep 2

# Run the live detector
echo "🎯 Starting live SSVEP detection..."
echo "Expected: Should detect 8.57 Hz as the strongest signal"
echo

# Run for 15 seconds with verbose output
uv run neurorelay-stream-demo \
    --stream-type EEG \
    --freqs 8.57,10,12,15 \
    --window 3.0 \
    --step 0.5 \
    --bandpass 5,40 \
    --notch 50 \
    --max-predictions 10 \
    --verbose

# Cleanup
echo
echo "🧹 Cleaning up..."
kill $STREAM_PID 2>/dev/null || true
wait $STREAM_PID 2>/dev/null || true

echo "✅ Test complete!"
echo
echo "If you saw predictions with 8.57 Hz as the top frequency,"
echo "then Phase 2 LSL integration is working correctly! 🎉"