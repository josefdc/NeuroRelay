# NeuroRelay Phase 3 — Operator Runbook

## Quick Start Guide

### Prerequisites
1. **EEG acquisition system** publishing LSL stream (type="EEG")
   - OpenBCI GUI
   - Neuroscan CURRY 8 with MATLAB online bridge
   - Or any LSL-compatible EEG system
2. **Python environment** with dependencies installed
3. **Display** capable of stable refresh rate (50/60 Hz recommended)

### Setup Steps

1. **Install dependencies**
   ```bash
   cd /path/to/NeuroRelay
   uv sync -E ui -E stream
   
   # Install LSL library (choose one):
   conda install -c conda-forge liblsl
   # OR download binaries from https://github.com/sccn/liblsl/releases
   ```

2. **Configure EEG acquisition**
   - Start your EEG acquisition software
   - Ensure LSL stream is active (type="EEG", sampling rate ≥200 Hz)
   - Verify occipital channels are included (O1, Oz, O2 for best SSVEP detection)

3. **Launch live UI**
   ```bash
   # Basic live mode
   uv run neurorelay-ui --live --auto-freqs
   
   # Full configuration
   uv run neurorelay-ui --live \
     --auto-freqs \
     --lsl-type EEG \
     --lsl-name "YourStreamName" \
     --lsl-timeout 10.0 \
     --prediction-rate 4.0 \
     --fullscreen
   ```

### Operation Procedure

1. **System checks**
   - Look for **green status dot** (bottom of UI) = healthy connection
   - Yellow dot = delayed data, Red dot = no data
   - Status bar shows "Live SSVEP mode active" when connected

2. **User instructions**
   - Look steadily at one of the four tiles: SUMMARIZE, TODOS, DEADLINES, EMAIL
   - **Confidence underline** will grow as detection improves
   - **Dwell ring** appears when winner is stable and above threshold
   - Ring fills over ~1.2 seconds to confirm selection
   - **Agent Dock** shows committed selection with confidence score

3. **Controls during operation**
   - **H** — Toggle HUD (operator diagnostics)
   - **Space** — Pause/resume (pauses dwell accumulation)
   - **F11** — Toggle fullscreen
   - **ESC** — Exit application

### Expected Performance

- **Selection latency**: 3-4 seconds typical (3s window + ~1.2s dwell)
- **Stability requirement**: Winner must stay top-1 for ≥3 consecutive predictions
- **Confidence threshold**: τ = 0.65 (softmax of z-scored scores)
- **Tie guard**: Top-1 and top-2 must differ by ≥0.05 for dwell to accumulate

### Status Indicators

| Indicator | Color | Meaning |
|-----------|--------|---------|
| Status Dot | 🟢 Green | Healthy LSL connection, fresh data |
| Status Dot | 🟡 Yellow | Data delayed (>0.5s but <2s old) |
| Status Dot | 🔴 Red | No data (>2s since last update) |
| Underline | Growing | Live confidence for each tile |
| Ring | Filling | Dwell progress for stable winner |

### Troubleshooting

**Red status dot (no data)**
- Verify EEG acquisition is running and streaming
- Check LSL stream name/type matches UI configuration
- Try increasing `--lsl-timeout` to 10.0 or higher
- Use `--lsl-name` to specify exact stream name

**Yellow status dot (delayed data)**
- Check network connection between EEG PC and UI machine
- Reduce prediction rate: `--prediction-rate 3.0`
- Increase LSL buffer if needed in acquisition software

**No dwell ring appears**
- User may not be looking steadily enough at one tile
- Check that confidence threshold is met (underline >65%)
- Verify stability: winner should stay same for 3+ predictions
- Ensure top-1 and top-2 have clear margin (>5% difference)

**Flicker discomfort**
- Lower intensity slider (bottom left of UI)
- Take breaks every few minutes
- Ensure flicker frequencies are <20 Hz
- Consider 50 Hz monitor settings if 60 Hz frequencies are uncomfortable

**"Live init error" messages**
- Run `uv sync -E stream` to install streaming dependencies
- Install liblsl library (see Prerequisites)
- Check that pylsl can find liblsl shared library

### Configuration Files

**Main config**: `config/default.json`
```json
{
  "monitor_hz": 60.0,
  "freqs_hz": [8.57, 10.0, 12.0, 15.0],
  "window_sec": 3.0,
  "dwell_sec": 1.2,
  "tau": 0.65,
  "channels": ["O1", "Oz", "O2"],
  "bandpass_hz": [5, 40],
  "notch_hz": 60
}
```

**Auto frequencies** (when using `--auto-freqs`):
- 60 Hz displays: 8.57, 10, 12, 15 Hz
- 50 Hz displays: 8.33, 10, 12.5, 16.67 Hz

### Validation Checklist

Before each session, verify:
- [ ] EEG acquisition running with LSL stream active
- [ ] UI shows green status dot within 10 seconds
- [ ] Confidence underlines respond to gaze
- [ ] Dwell ring appears for steady gaze (>3 seconds)
- [ ] Selection commits to Agent Dock
- [ ] Pause/resume works correctly
- [ ] No error messages in status bar

### Session Logs

The application automatically logs events. Check these locations for diagnostics:
- Status messages appear in UI status bar
- Console output shows LSL connection details
- Future versions will log to `logs/` directory

### Emergency Procedures

**If UI becomes unresponsive:**
1. Press **ESC** to exit gracefully
2. If needed, use Ctrl+C in terminal
3. Check that LSL streams are properly closed

**If user experiences discomfort:**
1. Press **Space** to pause immediately
2. Lower intensity slider
3. Take a break from the screen
4. Consider switching to lower frequency set or different monitor

### Performance Optimization

**For better accuracy:**
- Ensure good electrode contact on occipital channels
- Use higher sampling rates (≥250 Hz)
- Reduce motion artifacts during recording
- Keep lighting conditions stable

**For lower latency:**
- Use local network connection (not WiFi)
- Increase prediction rate to 5 Hz if system can handle it
- Reduce LSL buffer size in acquisition software
- Use wired connection between EEG and UI computers

---

## Next Phase: Local Agent Integration

Phase 3 provides the selection mechanism. Phase 4 will add:
- BrainBus JSON protocol for intent→action mapping
- Local agent tools (summarize, extract TODOs, etc.)
- File-based workflows (workspace/in → workspace/out)
- Offline operation (no network dependencies)