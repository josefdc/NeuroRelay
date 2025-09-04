Below is a **ready‑to‑drop‑in `README.md`** (user manual) for your repo. It’s written for a first‑time operator to get from zero to a working demo (simulation → live LSL → agent outputs), with clear steps, commands, controls, and troubleshooting.

---

# NeuroRelay — Offline SSVEP Brain‑to‑Agent Demo

**NeuroRelay** is a 4‑option SSVEP interface (SUMMARIZE / TODOS / DEADLINES / EMAIL) that runs *fully offline* on your machine. It reads EEG from LSL, performs live SSVEP decoding, and triggers a local agent that drafts results into `workspace/out/`. If a local LLM (e.g., **LM Studio**) is running, the agent uses it; otherwise it falls back to deterministic heuristics.

* UI: **PySide6**
* Live streaming: **Lab Streaming Layer (pylsl)**
* Detection: **CCA** with bandpass/notch and optional harmonics
* Agent sandbox: **reads `workspace/in/`**, **writes `workspace/out/`**, never touches your system config or external services unless you point it there.

---

## Table of Contents

- [NeuroRelay — Offline SSVEP Brain‑to‑Agent Demo](#neurorelay--offline-ssvep-braintoagent-demo)
  - [Table of Contents](#table-of-contents)
  - [Quick Start (TL;DR)](#quick-start-tldr)
  - [Install \& Environment](#install--environment)
    - [Requirements](#requirements)
    - [Install](#install)
    - [Optional environment variables (for LLM)](#optional-environment-variables-for-llm)
  - [Config File (`config/default.json`)](#config-file-configdefaultjson)
  - [Running the UI](#running-the-ui)
    - [Simulation mode (no EEG required)](#simulation-mode-no-eeg-required)
    - [Live mode (LSL + EEG)](#live-mode-lsl--eeg)
  - [Agent Behavior \& Outputs](#agent-behavior--outputs)
  - [Console Tools (no UI)](#console-tools-no-ui)
    - [Live SSVEP demo (LSL)](#live-ssvep-demo-lsl)
    - [Synthetic SSVEP CSV generator](#synthetic-ssvep-csv-generator)
  - [Controls \& Shortcuts](#controls--shortcuts)
  - [Logs \& Where Things Go](#logs--where-things-go)
  - [Troubleshooting \& FAQ](#troubleshooting--faq)
  - [Security \& Offline Model](#security--offline-model)
  - [Command Cheat Sheet](#command-cheat-sheet)
  - [What to Expect in a Demo](#what-to-expect-in-a-demo)

---

## Quick Start (TL;DR)

```bash
# 1) Create a virtualenv and install (UI + stream + agent extras)
uv venv
uv sync -E ui -E stream -E agent

# 2) Put a test file in the sandbox
mkdir -p workspace/in
cp examples/demo.md workspace/in/ || echo "Make sure there's a .md/.txt/.pdf/.docx file in workspace/in"

# 3) Run the UI in SIMULATION mode (no EEG needed)
uv run neurorelay-ui

#   - Use arrow keys or 1..4 to simulate selection
#   - Outputs appear in workspace/out

# 4) (Later) Run in LIVE mode if you have an LSL EEG stream
uv run neurorelay-ui --live
```

**Outputs** land in `workspace/out/`:

* `*_summary.md`, `*_todos.md`, `*_deadlines.md` / `*.ics`, or `draft_YYYYmmdd-HHMMSS.md` (EMAIL).

---

## Install & Environment

### Requirements

* **Python 3.11+**
* Linux/macOS/Windows (Linux is the smoothest for live demos)
* Optional: **LM Studio** running locally (for higher‑quality summaries/emails); otherwise we fallback to heuristics.

### Install

We recommend using **uv**:

```bash
uv venv
# Base + UI + LSL streaming + Agent tooling
uv sync -E ui -E stream -E agent
```

Alternatives:

```bash
# Using pip (not recommended; extras must be spelled out)
pip install -e .[ui,stream,agent]
```

### Optional environment variables (for LLM)

If you’ll use LM Studio:

```bash
export NEURORELAY_GPT_MODEL="openai/gpt-oss-20b"      # or any local model label in LM Studio
export NEURORELAY_LMSTUDIO_URL="http://localhost:1234/v1"
export NEURORELAY_LLM_TIMEOUT="30"
```

> If a local LLM isn’t reachable, the agent still works with deterministic heuristics.

---

## Config File (`config/default.json`)

This config shapes both UI timing and detection:

```json
{
  "monitor_hz": 120,
  "freqs_hz": [8.57, 10.0, 12.0, 15.0],
  "window_sec": 3.0,
  "step_sec": 0.5,
  "dwell_sec": 1.2,
  "tau": 0.65,
  "channels": ["O1", "Oz", "O2"],
  "bandpass_hz": [5, 40],
  "notch_hz": 60,
  "decoder": "CCA",
  "artifact_guard": true,
  "sandbox_root": "workspace",
  "out_dir": "workspace/out",
  "flicker_mode": "sinusoidal",
  "ui_intensity": 0.85
}
```

**Key fields**

* `monitor_hz`: your display refresh (60/75/120/144…).
* `freqs_hz`: 4 SSVEP target frequencies for the tiles.
* `window_sec`: analysis window for live detection.
* `dwell_sec`: how long the “winner” must be stable to commit.
* `tau`: confidence threshold for commits.
* `channels`: preferred EEG channels (we’ll select them if present in stream metadata).
* `bandpass_hz`, `notch_hz`: preprocessing filters.
* `sandbox_root`, `out_dir`: where the agent reads from / writes to.
* `flicker_mode`: `"sinusoidal"` (recommended) or `"square"`.
* `ui_intensity`: flicker amplitude (0.25–1.0 recommended).

> **Tip:** If your monitor is 60 Hz, you can also use `--auto-freqs` when launching the UI to derive frequencies based on your refresh rate.

---

## Running the UI

### Simulation mode (no EEG required)

This is the fastest way to verify the agent and outputs:

```bash
uv run neurorelay-ui
```

* Put a `.md/.txt/.pdf/.docx` file into **`workspace/in/`**; the **most recent** file is the “active document.”
* Look at the four flickering tiles: **SUMMARIZE / TODOS / DEADLINES / EMAIL**.
* Use **arrow keys** or **1..4** to simulate a selection (see [Controls](#controls--shortcuts)).

Outputs land in `workspace/out/`:

* `*_summary.md`, `*_todos.md`, `*_deadlines.md` and `*_deadlines.ics`, or `draft_YYYYmmdd-*.md` for Email.

### Live mode (LSL + EEG)

If you have an EEG stream on **LSL**:

1. Make sure your LSL source is broadcasting a stream of type **`EEG`** (optionally with channel labels `O1, Oz, O2`).

2. Start the UI with live detection:

   ```bash
   uv run neurorelay-ui --live
   ```

   Optional flags:

   * `--lsl-type EEG` (default)
   * `--lsl-name <name>` to pick a specific stream
   * `--prediction-rate 4.0` (Hz) to adjust the prediction cadence
   * `--fullscreen` for stimulus quality
   * `--auto-freqs` to adapt to monitor refresh

3. **Status (bottom‑right)**

   * **Green dot** = connected
   * **Yellow** = delayed
   * **Red** = no data

4. When a frequency wins and stays stable **≥ dwell\_sec** with confidence **≥ tau**, the selection commits and triggers the agent.

> If you don’t see predictions: verify your LSL stream with the console demo (below), confirm `channels` in the config, and check sample rate.

---

## Agent Behavior & Outputs

* The agent runs automatically as a subprocess when the UI starts.
* It receives a `SELECT` event with the chosen label and optional context (active file, email topic).
* Tools:

  * **SUMMARIZE** → `workspace/out/<file>_summary.md`
    Uses LM Studio if available; otherwise a heuristic summary.
  * **TODOS** → `workspace/out/<file>_todos.md`
    Greps imperative lines and bullet‑style todos, marks due/candidate lines.
  * **DEADLINES** → `workspace/out/<file>_deadlines.md` + `.ics`
    Parses “due by/on …/tomorrow/next <weekday>/EOD/COB” and writes an ICS.
  * **EMAIL** → `workspace/out/draft_<timestamp>.md`
    Drafts a short email (LLM if available; else a safe template). If an active file exists, it’s mentioned as context.

**Active document picking**: The agent uses the most recently modified file in `workspace/in/` with extension `.txt/.md/.pdf/.docx`.

> If no file is found for SUMMARIZE/TODOS/DEADLINES, the agent returns a clear error and does not write output.

---

## Console Tools (no UI)

### Live SSVEP demo (LSL)

```bash
uv run neurorelay-stream-demo \
  --stream-type EEG \
  --freqs "8.57,10,12,15" \
  --window 3.0 \
  --step 0.5 \
  --bandpass 5,40 \
  --notch 60 \
  --method cca \
  -v
```

* Prints live predictions and per‑frequency scores.
* Use this to debug your LSL stream and confirm sample rate, channel names, and data availability.

### Synthetic SSVEP CSV generator

```bash
uv run neurorelay-gen-synth --out data/sim_session.csv --sr 250 --monitor-hz 60 --seed 42
# or derive freqs from monitor
uv run neurorelay-gen-synth --out data/sim_session.csv --monitor-hz 120 --freqs auto
```

This generates test data for algorithm development and unit tests. (The UI consumes LSL live data; CSV is for offline dev/tests.)

---

## Controls & Shortcuts

In the **UI**:

* **SPACE** — Pause / Resume
* **ESC** — Exit
* **H** — Toggle HUD (mode/map/config labels)
* **F11** — Toggle fullscreen
* **A** — Show/hide Agent dock
* **P** — Show/hide Center panel
* **Arrow keys or 1..4** — Simulate a winner (SIMULATION mode)

  * Left/Up/`1` → **SUMMARIZE**
  * Right/`2` → **TODOS**
  * Down/`3` → **DEADLINES**
  * `4` → **EMAIL**
* **Intensity slider** — adjust flicker amplitude (bottom area)

**Open output**: If enabled in your build, the “Open” button in the Agent area will attempt to open the last output. (On some platforms this may require `xdg-open` or manual opening of the file.)

---

## Logs & Where Things Go

* **Input files**: `workspace/in/` (drop `.md/.txt/.pdf/.docx` here)
* **Outputs**: `workspace/out/`

  * `*_summary.md`, `*_todos.md`, `*_deadlines.md`, `*_deadlines.ics`, `draft_*.md`
* **Agent log (JSONL)**: `logs/agent.jsonl`
* **BrainBus logs**: `logs/brainbus_*.jsonl` (if present from scripts)
* **Config**: `config/default.json`

---

## Troubleshooting & FAQ

**I don’t see flicker / timing feels off.**

* Use **Fullscreen** (`--fullscreen` or press **F11**).
* Set `monitor_hz` correctly in `config/default.json`.
* Consider `--auto-freqs` so frequencies match your refresh rate (e.g., 60 Hz → 8.57/10/12/15 Hz).

**Live label says “no data”.**

* Make sure an LSL EEG stream is running (`type=EEG`).
* Try `uv run neurorelay-stream-demo` to verify.
* If you use a specific stream name, pass `--lsl-name <name>`.
* Check that the sample rate is reasonable (≥ 100 Hz recommended).

**Agent says “no input document found”.**

* Place a `.md/.txt/.pdf/.docx` in `workspace/in/`.
* The most recent file is used automatically.

**Summaries/emails look generic.**

* Ensure LM Studio is running (`NEURORELAY_LMSTUDIO_URL` points to it, model is loaded).
* If an LLM isn’t available, we intentionally produce conservative heuristic outputs.

**Filter padding errors / detection unstable.**

* Increase `window_sec` (e.g., 3.0 → 3.5) to satisfy filter padding.
* Confirm `bandpass_hz` and `notch_hz` are below Nyquist (sample\_rate/2).

**“Failed to start neurorelay-agent”.**

* Make sure `uv sync -E agent` was run (for PDF/DOCX & LLM client libs).
* Check `logs/agent.jsonl` and console output.

**“Open” button doesn’t open the file.**

* On some platforms, `xdg-open` may not be available. Open the path shown in the UI manually from `workspace/out/`.

---

## Security & Offline Model

* **Sandboxed I/O**: The agent reads **only** from `workspace/in/` and writes **only** to `workspace/out/`.
* **No network required**: LM Studio is optional. Without it, the agent uses deterministic local heuristics.
* **Non‑destructive**: The agent creates new files; it never modifies inputs.

---

## Command Cheat Sheet

```bash
# Install
uv venv
uv sync -E ui -E stream -E agent

# UI: simulation (no EEG)
uv run neurorelay-ui

# UI: live (LSL)
uv run neurorelay-ui --live --fullscreen

# UI: adapt freqs to monitor refresh
uv run neurorelay-ui --auto-freqs

# Console: live SSVEP (diagnostics)
uv run neurorelay-stream-demo -v

# Generate synthetic CSV
uv run neurorelay-gen-synth --out data/sim_session.csv --monitor-hz 120 --freqs auto
```

---

## What to Expect in a Demo

1. **Launch UI** (simulation first).
2. Drop a sample doc into `workspace/in/`.
3. Simulate a selection (arrow keys / 1..4).
4. Watch the **Agent** label change to `pending…`, then `→ <output_path>`.
5. Find your file in `workspace/out/`.
6. (If live) Enable `--live`, confirm the link dot turns **green**, then fixate a tile until the dwell ring completes to commit.

---
