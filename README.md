

# NeuroRelay — Brain‑to‑Agent (SSVEP, 4 options, offline) {#project-feature-name}

**Link:** *design-doc (repo/README will be generated)*
**Author(s):** NeuroRelay Team (TBD)
**Status:** In Progress
**Last Updated:** Aug 19, 2025

## Table of Contents

1. [Summary](#summary)
2. [Context](#context)
3. [Detailed Design](#detailed-design)

   * [Proposed Solution 1 — P0 (SSVEP 4 options + local agent)](#proposed-solution-1)
   * [Proposed Solution 2 — P0.5 (SSVEP + light personalization)](#proposed-solution-2)
   * [Proposed Solution 3 — P1 (Fallback P300/Hybrid)](#proposed-solution-3)
4. [Testing and Validation](#testing-and-validation)
5. [Future Considerations](#future-considerations)
6. [Glossary](#glossary)
7. [Assumptions & Non‑Goals](#assumptions-non-goals)
8. [User Stories](#user-stories)
9. [Architecture & Components](#architecture-components)
10. [Realtime with Neuroscan + CURRY 8](#realtime-curry)
11. [UI/UX Spec (PySide6/Qt)](#ui-ux-spec)
12. [Security & Privacy (offline)](#security)
13. [Risks & Mitigations](#risks)
14. [Repository & Deliverables](#repo)

---

## Summary {#summary}

**NeuroRelay** lets a user choose **one of four useful actions** by looking at an on‑screen option. We detect intent with **SSVEP** (steady-state visual evoked potentials) using a **Compumedics Neuroscan EEG (128ch)**; a **local agent** (**gpt‑oss**, no internet) executes the action: *summarize a document, extract to‑dos, flag deadlines, or draft an email*. Everything runs **offline** and includes **neurofeedback** for confidence/confirmation. P0 prioritizes a robust **real‑time** demo or **replay** from dataset/EDF.

---

## Context {#context}

* **Hackathon motivation (OpenAI Open Model Hackathon):** demonstrate **local agents** with **reasoning** that expand **human→AI bandwidth**. Specifically, a **brain→agent** interface using discrete intent channels (4 choices) instead of text/voice.
* **Why SSVEP (not free text):** with surface EEG, translating thoughts into text remains brittle. **SSVEP** supports **discrete decisions** that are **reliable and fast** (2–4 s) with occipital electrodes.
* **Available hardware/software:**

  * **Compumedics Neuroscan** 128‑channel system + **CURRY 8** for acquisition/analysis. CURRY targets Windows (Start menu, `C:\Program Files`, DirectX/OpenGL, dongle/license management).
  * CURRY supports **EDF export**, maintains **history/logs**, and **macros** for automating workflows.
* **Demo goal:** **end‑to‑end, offline** flow with **3–4 s total latency**, **≥80% accuracy**, and clear **UI/UX**.

---

## Detailed Design {#detailed-design}

### Proposed Solution 1 — P0 (SSVEP 4 options + local agent) {#proposed-solution-1}

> **Scope of this expansion:** clearer objectives, timing budget, stimulus design, decoding pipeline, decision policy, agent contracts, logging/telemetry, configuration defaults, fail‑safes, and an operator runbook.

#### 1) Objectives & Success Criteria

* **Functionality:** user selects exactly one of **4 actions** via visual focus.
* **Accuracy:** **≥80%** top‑1 per selection in live or replay mode.
* **Latency budget (stimulus→action):** **≤4.0 s** typical.
* **Auditability:** every decision emits a **BrainBus JSON** with timestamp, method, confidence, and file paths for results.
* **Offline:** no network access at any stage.
* **Safety:** actions are **non‑destructive** (drafts only, local files).

#### 2) End‑to‑End Timing Budget (target)

| Stage                                |     Budget (ms) | Notes                                |
| ------------------------------------ | --------------: | ------------------------------------ |
| Frame‑locked flicker & user fixation |          0–3000 | 3.0 s evaluation window (P0 default) |
| Acquisition chunking & preproc       |           20–60 | per 1 s chunk; cumulative negligible |
| Decoder (CCA/FBCCA)                  |           10–40 | on 3 s buffer, O1/Oz/O2              |
| Decision policy (threshold + dwell)  |        200–1200 | dwell default **1.2 s**              |
| Agent tool execution (local)         |        250–1200 | depends on tool/file size            |
| **Total**                            | **\~3.5–4.0 s** | median case                          |

#### 3) Visual Stimuli & UI Coupling

* **Layout:** 2×2 grid with large hit‑targets (each ≥20% screen width).
* **Frequencies (60 Hz monitor):** **8.57, 10, 12, 15 Hz** (i.e., frame inversions every 7, 6, 5, 4 frames respectively, 50% duty).
* **Frequencies (50 Hz monitor):** **8.33, 10, 12.5, 16.67 Hz** (divisors of 50).
* **Contrast modulation:** binary invert between light/dark blocks (no color dependence).
* **VSync:** frame‑accurate toggling; avoid timer‑based flicker (jitter→SNR loss).
* **Intensity slider:** user adjustable to manage visual comfort; includes **pause** hotkey.
* **State machine:** `idle → evaluate(3.0 s) → confirm(dwell 1.2 s) → action`.
* **Neurofeedback:** (1) live confidence bar; (2) circular dwell ring around the current top candidate; (3) toast upon action completion.

#### 4) Signal Acquisition & Preprocessing

* **Sampling rate:** ≥250 Hz (tolerant up to 1 kHz).
* **Channels:** **O1, Oz, O2** (optionally PO3, PO4 as backup).
* **Filters:**

  * **Notch**: 50/60 Hz (environment matched), IIR biquad or FIR zero‑phase (filtfilt).
  * **Band‑pass**: **5–40 Hz** passband (covers fundamentals and 2nd harmonics of chosen flickers).
* **Referencing:** **CAR** (common average reference) or **Oz** as reference if CAR is unstable.
* **Chunking:** rolling window; append incoming 1 s blocks → evaluate once window ≥3.0 s.
* **Artifact tolerance:** simple **blink/EMG guard**—if broadband power spikes exceed threshold within 0.2 s segments, reduce confidence (see Decision Policy).

#### 5) Decoder (CCA/FBCCA) & References

* **Reference construction per frequency `f`:**
  `sin(2π f t), cos(2π f t), sin(2π·2f t), cos(2π·2f t)` sampled at EEG rate over the **current window**.
* **CCA:** compute canonical correlations between multi‑channel EEG and the reference matrix for each `f`; obtain a scalar score per option.
* **FBCCA (optional toggle in P0):** split the band into sub‑bands (e.g., 5–20, 20–30, 30–40 Hz), run CCA per sub‑band, then combine with fixed weights; improves robustness to inter‑subject variability.
* **Scores → confidence:** normalize via **z‑score → softmax**; keep raw correlations for logs.

#### 6) Decision Policy (Threshold, Dwell, Stability)

* **Primary decision:** `label = argmax(scores)`.
* **Confidence threshold:** default **τ = 0.65** on softmax; below τ, extend evaluation by +0.5 s (once) or re‑enter evaluate state.
* **Dwell:** **1.2 s** continuous dominance required to commit; ring UI shows progress.
* **Stability check:** require **top‑1 unchanged** across the last **3 frame updates** (\~150–200 ms) before counting dwell time.
* **Artifact guard:** if broadband power z‑score > 4.0 for >80 ms during dwell, **reset dwell** (likely blink/motion).
* **Tie‑breakers:** if top‑1 and top‑2 are within **Δ ≤ 0.05** confidence for >0.5 s, trigger **“Need more evidence”**: extend window or prompt user to briefly refocus.

#### 7) BrainBus Contract & Telemetry

**Decision event (example):**

```json
{
  "ts": "2025-08-19T20:15:11.123Z",
  "decoder": { "type": "SSVEP", "version": "0.1.0", "mode": "CCA" },
  "window_sec": 3.0,
  "channels": ["O1","Oz","O2"],
  "freqs_hz": [8.57, 10, 12, 15],
  "scores": { "8.57": 0.12, "10": 0.81, "12": 0.05, "15": 0.02 },
  "intent": { "name": "SELECT", "args": { "label": "SUMMARIZE", "index": 0 } },
  "confidence": 0.81,
  "policy": { "tau": 0.65, "dwell_sec": 1.2, "artifact_guard": true }
}
```

**Additional events:** `session_start`, `evaluate_begin`, `evaluate_extend`, `dwell_reset_artifact`, `action_start`, `action_end`, `error`.

All events are persisted under `logs/` (rotated JSONL). A human‑readable session report is generated after each run.

#### 8) Local Agent Tools & Contracts (offline)

Agent runs **locally** (no network). Tools operate inside **`workspace/`** sandbox; outputs to **`workspace/out/`**.

1. **`summarize(file)`**

   * **Input:** path to `.pdf/.txt/.md/.docx`.
   * **Output:** `out/<basename>_summary.md`.
   * **Heuristics:** chunking with overlap; offline LLM prompt “concise, factual, bullet‑first”; include section headers discovered.

2. **`extract_todos(file)`**

   * **Output:** `out/<basename>_todos.md`
   * **Patterning:** detect imperative lines, deadlines (“by/on/ETA”), owners (`@` mentions), and numbers; produce checkboxes.

3. **`flag_deadlines(file)`**

   * **Output:** `out/<basename>_deadlines.md` and optional `.ics` in `out/`.
   * **NER rules:** detect date spans, relative dates (resolve from `session_start`), and “due/delivery/submit” keywords.

4. **`compose_email(topic, attachments?)`**

   * **Output:** `out/draft_<timestamp>.txt`.
   * **Behavior:** draft only; includes subject line suggestions; optionally lists attachments from `workspace/`.

**Agent invocation message (example):**

```json
{
  "ts": "2025-08-19T20:15:12.500Z",
  "agent": { "name": "gpt-oss-local", "version": "0.1.0" },
  "tool": "summarize",
  "args": { "file": "workspace/in/report_q3.pdf" },
  "trace_id": "nr-20250819-201509-001"
}
```

#### 9) Replay & Live Modes

* **Live:** stream from CURRY via MATLAB online hook (1 s chunks) → **LSL/TCP** bridge → `SourceLSL` consumer.
* **Replay:** EDF/CSV with markers via `SourceReplay` (deterministic for demos).
* **Mode parity:** identical preprocessing/decoder pipelines; only the source changes.

#### 10) Configuration Defaults (P0)

```json
{
  "monitor_hz": 60,
  "freqs_hz": [8.57, 10, 12, 15],
  "window_sec": 3.0,
  "step_sec": 0.5,
  "dwell_sec": 1.2,
  "tau": 0.65,
  "channels": ["O1","Oz","O2"],
  "bandpass_hz": [5, 40],
  "notch_hz": 60,
  "decoder": "CCA",          // "CCA" or "FBCCA"
  "artifact_guard": true,
  "sandbox_root": "workspace",
  "out_dir": "workspace/out"
}
```

#### 11) Fail‑Safes & UX Guardrails

* **Abort:** ESC key or on‑screen button to cancel current evaluation.
* **Idle timeout:** if no stable top‑1 for **>6 s**, auto‑pause and prompt.
* **Comfort:** brightness slider + “rest” prompt every 10 selections.
* **Non‑destructive actions:** writing drafts/files only; never send emails or delete content.

#### 12) Minimal Operator Runbook (P0)

1. **Setup:** verify monitor refresh (60/50 Hz), connect Neuroscan, open CURRY project.
2. **Start acquisition:** begin recording; enable MATLAB online processing (1 s chunks).
3. **Bridge:** run `bridge_matlab_lsl.m` or TCP publisher on Windows machine.
4. **Launch UI/decoder:** `python ui/ssvep_4buttons.py --mode live` on Mac (or `--mode replay --edf path`).
5. **Choose file:** place input files under `workspace/in/`.
6. **Demo flow:** user gazes at **SUMMARIZE / TODOS / DEADLINES / EMAIL** → confidence/dwell visible → action completes.
7. **Check outputs:** `workspace/out/` and `logs/*.jsonl`.
8. **Shut down:** stop acquisition, archive logs, optionally generate session report.

---

### Proposed Solution 2 — P0.5 (SSVEP + light personalization) {#proposed-solution-2}

* **Per‑user quick calibration (2–3 min):** frequency power scan and channel weighting (O1/Oz/O2/PO3/PO4).
* **FBCCA** (sub‑bands + harmonics) with **user‑learned** weights.
* **Adaptive policy:** if `conf < τ`, increase window to 3.5–4 s or repeat evaluation.

| Pros                        | Cons                           |
| --------------------------- | ------------------------------ |
| Boosts accuracy by \~3–8 pp | Adds 2–3 min setup before demo |

---

### Proposed Solution 3 — P1 (Fallback P300/Hybrid) {#proposed-solution-3}

* **P300** as a *Plan B* (row/column paradigm) if SSVEP is uncomfortable.
* **Hybrid:** use P300 “confirm” after SSVEP “select” (double safety lock).

| Pros                                  | Cons                              |
| ------------------------------------- | --------------------------------- |
| More robust in difficult environments | Added complexity and more fatigue |

---

## Testing and Validation {#testing-and-validation}

**Process (not individual tests):**

* **Unit tests:**

  * **Synthetic SSVEP generator** (sum of sinusoids + noise).
  * **Reference validation** (sin/cos, 1f/2f).
  * **Confidence normalization** (softmax/z‑score).

* **Edge cases:**

  * Artifacts (eye blinks), low SNR, saturation, near‑ties, 50/60 Hz monitors, packet loss (live).

* **Metrics:**

  * **Top‑1 accuracy** per selection (goal ≥80% in P0).
  * **Latency** stimulus→intent→action (3–4 s).
  * **ITR** (N=4, T=3 s): 23–33 bits/min for accuracy 0.85–0.95.
  * **UX:** brief survey (clarity, fatigue, perceived control).

---

## Future Considerations {#future-considerations}

* **More options** (6–8 frequencies) with adaptive layouts and controlled duty cycle.
* **TRCA/Ensemble‑TRCA** and **multisinusoidal SSVEP** for higher ITR.
* **Co‑adaptation** (light transfer learning).
* **Robotics/IoT:** map intents to physical actuators.
* **Wearables:** stimuli in AR/VR (no monitor PWM constraints).
* **Out of scope for P0:** medical claims, sending real emails (drafts only), cloud use.

---

## Glossary {#glossary}

* **SSVEP:** steady‑state visual evoked potential; staring at a flickering stimulus induces rhythmic occipital activity.
* **CCA/FBCCA:** canonical correlation analysis with sin/cos references (harmonics); FBCCA adds **sub‑bands** and weighting.
* **Dwell:** fixation time required to confirm an action.
* **CAR:** common average reference, subtracting the mean across channels.
* **EDF:** standard EEG format.

---

## Assumptions & Non‑Goals {#assumptions-non-goals}

**Assumptions**

* A 60 Hz monitor is available (frequencies 60/k).
* The user tolerates flicker <20 Hz with moderate brightness.
* CURRY 8 runs on **Windows** (acquisition); the agent runs locally on **Mac** (gpt‑oss inference). The CURRY workflow covers Windows‑specific paths, services, and launchers.

**Non‑Goals P0**

* Decoding free‑form language from EEG.
* Sending real emails (drafts only in a local folder).

---

## User Stories {#user-stories}

1. **As a user**, I want to select **SUMMARIZE/TODOS/DEADLINES/EMAIL** by looking at a button to execute hands‑free actions.
2. **As a demo judge**, I want to see **auditable JSON** (`intent`, `confidence`) and locally saved results.
3. **As an operator**, I want to run the flow **offline**, with **live** signal or **replay**.

---

## Architecture & Components {#architecture-components}

**Modules**

* `ui/` (PySide6/Qt, 2×2 with frame‑locked flicker).
* `stream/`

  * `SourceLSL` (if we use the bridge)
  * `SourceReplay` (EDF/CSV + markers)
* `signal/`

  * `preprocess.py` (notch 50/60, band‑pass 5–40 Hz, CAR)
  * `ssvep_cca.py` → `fbcca.py`
* `bus/`

  * `brainbus.py` (JSON {intent, confidence})
* `agent/`

  * `run_agent.py` (local gpt‑oss, offline)
  * `tools_local.py` (4 tools; outputs to `workspace/out/`)

**BrainBus Contract (example)**

```json
{
  "ts": "2025-08-19T20:15:11.123Z",
  "decoder": { "type": "SSVEP", "version": "0.1.0" },
  "intent": { "name": "SELECT", "args": { "label": "SUMMARIZE", "index": 0 } },
  "confidence": 0.81
}
```

**Decoder pseudocode**

```python
Xp = preprocess(X)                  # notch, band-pass, CAR
win.append(Xp); win.trim(3.0)
if phase == "evaluate" and win.len >= 3.0:
    scores = fbcca(win, freqs=[8.57,10,12,15], chans=[O1,Oz,O2])
    label, conf = argmax(scores), normalize(scores)
    if conf >= tau and dwell_ok:
        emit_brainbus(label, conf)
```

---

## Realtime with Neuroscan + CURRY 8 {#realtime-curry}

**Goal:** Acquire on **Windows** with CURRY and **feed in real time** to the decoder/UI (running on Mac) or, alternatively, **replay** a file.

**Relevant CURRY facts:**

* CURRY is Windows‑first: paths and startup/licensing procedures are Windows‑specific (Start menu, Sentinel LDK, `C:\Program Files`).
* CURRY can **export to EDF** and maintains **history/logs** and **macros**.
* CURRY supports **online MATLAB interface**; in online mode it can **send short blocks (≈1 s)** to MATLAB for real‑time processing.

**Integration routes (choose A for live):**

* **A) MATLAB→socket/LSL bridge (preferred live):**
  Use CURRY→MATLAB online hook receiving **1 s chunks**; in MATLAB, publish each block over **local TCP** or **LSL** to the Mac. Avoids disk writes and keeps latency low.

* **B) Shared folder + tail (simple, higher latency):**
  CURRY exports EDF segments; the Mac “tails” the file and processes rolling windows. Simpler but **higher latency**.

* **C) Replay (demo/backup):**
  Play back an **EDF** recorded with **markers** for repeatable judging.

**Markers/events:** Use CURRY events/epoching to mark “start/stop evaluation” if needed; rely on CURRY logs/reports for audit.

---

## UI/UX Spec (PySide6/Qt) {#ui-ux-spec}

**Framework:** **PySide6 (Qt for Python)** — precise **flicker** control (frame‑locking), native performance, easy socket/thread integration.

**Visual design**

* **2×2 layout** (each button ≥20% width).
* **Labels:** *SUMMARIZE / TODOS / DEADLINES / EMAIL*.
* **Flicker:** contrast inversion (light/dark), **50% duty**, synchronized to monitor refresh:

  * 60 Hz → 8.57 (60/7), 10 (60/6), 12 (60/5), 15 (60/4).
  * 50 Hz → 8.33 (50/6), 10 (50/5), 12.5 (50/4), 16.67 (50/3).
* **States:** *idle* → *evaluate (3 s)* → *confirm (dwell 1.2 s)* → *action done*.
* **Neurofeedback:** confidence bar and dwell ring around the “winner” button.
* **Accessibility:** flicker intensity slider, quick pause, **Replay** mode.

**Flicker synchronization (concept):** on a 60 Hz display, toggle every **k** frames:
`k = 7 (8.57 Hz), 6 (10 Hz), 5 (12 Hz), 4 (15 Hz)` for 50% duty (on/off in k‑frame blocks).

---

## Security & Privacy (offline) {#security}

* **No internet:** all local.
* **Sandbox** `workspace/` (read input; write under `workspace/out/`).
* **JSON logs** for intent/decisions; avoid sensitive personal data.

---

## Risks & Mitigations {#risks}

| Risk                        | Mitigation                                                        |
| --------------------------- | ----------------------------------------------------------------- |
| **Live streaming** unstable | Route A (MATLAB online 1 s); Route C (Replay) for the demo        |
| **Accuracy <80%**           | Extend window to 3.5–4 s; FBCCA; add PO3/PO4; moderate brightness |
| **Visual discomfort**       | Frequencies <20 Hz, adjustable intensity, breaks                  |
| **Irreversible actions**    | Drafts/local files only; dwell confirmation                       |
| **Monitor desync**          | Use frequencies as exact divisors of refresh; test both 50/60 Hz  |

---

## Repository & Deliverables {#repo}

**Structure**

```
neurorelay/
├─ README.md (this design and demo guide)
├─ config/default.json
├─ ui/ssvep_4buttons.py          # PySide6/Qt
├─ stream/source_lsl.py          # socket/LSL client (optional)
├─ stream/source_replay.py       # EDF/CSV with markers
├─ signal/preprocess.py
├─ decoder/ssvep_cca.py          # + fbcca.py
├─ bus/brainbus.py               # JSON schema
├─ agent/run_agent.py            # local gpt-oss (offline)
├─ agent/tools_local.py          # 4 tools
├─ scripts/synthetic_ssvep.py    # generator for tests
├─ scripts/evaluate_confusion.py # metrics
└─ workspace/, logs/, data/
```

**Hackathon deliverables**

* **Video (<3 min):** demo **Local mode: ON** → select SUMMARIZE/TODOS/DEADLINES/EMAIL (live or replay).
* **Public repo** with instructions, sample data, and clear mapping to **gpt‑oss**.
* **Submission description** (categories: *Best Local Agent*, *Weirdest Hardware*, *For Humanity*).
* **Results:** accuracy/latency/ITR; BrainBus JSONs; generated files.

---

## Appendix: Signal Pipeline (P0 parameters)

* **Sampling:** ≥250 Hz (tolerant up to 1 kHz).
* **Channels:** O1, Oz, O2 (+ PO3, PO4 optional).
* **Preproc:** notch 50/60, band‑pass 5–40 Hz, **CAR**.
* **Window:** 3.0 s; step 0.5–1.0 s.
* **References (per f):**
  `sin(2π f t), cos(2π f t), sin(2π 2f t), cos(2π 2f t)`
* **Decision:** `argmax(scores)`; **confidence** = softmax(z‑scores).
* **Threshold τ:** 0.65 (tunable).

---

## Notes on CURRY 8 (manual‑relevant)

* **Windows‑first:** installation/launcher and license/dongle support are Windows‑specific (Start menu, Sentinel service; remedies after Windows updates).
* **Export/formats:** EDF supported; history/logs and integrated reports; **macros** to repeat workflows.
* **MATLAB online:** CURRY can send **\~1 s blocks** to MATLAB during online operation (key for streaming bridge).

---
---

## Phase 1 — Stimulus/UI + Replay Harness

**Objective:**
Have a production‑quality **PySide6/Qt UI** that renders a 2×2 SSVEP stimulus reliably and a **replay harness** that lets us run the full loop without the EEG cap.

**Scope**

* **UI (PySide6/Qt)**: 2×2 grid, high‑contrast tiles labeled **SUMMARIZE / TODOs / DEADLINES / EMAIL**.
* **Flicker**: frame‑locked frequencies for 60 Hz displays: **8.57, 10, 12, 15 Hz** (50 Hz alt: 8.33, 10, 12.5, 16.67 Hz). 50% duty via frame counts (e.g., toggle every 6 frames for 10 Hz on 60 Hz).
* **Neurofeedback**: confidence bar + dwell ring (1.2 s) around the currently leading tile.
* **Replay**: EDF/CSV loader + “synthetic SSVEP” generator (sine @ f + noise) with markers to emulate sessions.
* **States**: *idle → evaluate (3 s) → confirm (dwell) → action done → idle*.

**Deliverables**

* `ui/ssvep_4buttons.py` (configurable frequencies, vsync).
* `stream/source_replay.py` (EDF/CSV with markers; synthetic generator).
* Config: `config/default.json` (monitor\_hz, freqs, window\_s, dwell\_s, thresholds).

**Exit Criteria**

* UI stable ≥10 minutes with constant flicker (no drift, no stutter).
* Replay feeds mock EEG chunks at real‑time pace (1× speed) with markers visible in logs.
* Mapped stimulus→frequency table printed at start and shown in UI “About”.

**Risks & Mitigation**

* **Vsync/flicker drift** → lock to frame callbacks and integer frame buckets; test both 60/50 Hz sets.
* **Visual fatigue** → brightness slider + pause button.

---

## Phase 2 — Online Signal Pipeline & SSVEP Decoder (CCA → FBCCA)

**Objective:**
Convert incoming multi‑channel EEG blocks into a **discrete intent** (one of 4) with a **confidence score**, meeting offline‑replay accuracy targets.

**Scope**

* **Preprocessing**: notch (50/60 Hz), band‑pass 5–40 Hz, CAR (Common Average Reference). Channels: **O1, Oz, O2** (+ PO3/PO4 optional).
* **Windowing**: rolling 3.0 s window (step 0.5–1.0 s).
* **CCA**: reference matrix per f with sin/cos for 1f & 2f harmonics.
* **FBCCA (if time)**: sub‑bands (e.g., 8–12, 12–16, 16–20, 20–28 Hz) and weighted fusion.
* **Confidence**: normalize scores (z‑score → softmax) and set **threshold τ ≈ 0.65**.

**Deliverables**

* `signal/preprocess.py` (filters, CAR).
* `decoder/ssvep_cca.py` (+ `decoder/fbcca.py` if time).
* `scripts/synthetic_ssvep.py` (unit‑test generator).
* `scripts/evaluate_confusion.py` (confusion matrix, accuracy, latency).

**Exit Criteria**

* **Replay accuracy ≥80%** (top‑1, 4 classes, 3 s window) on synthetic + one public dataset trial set.
* **Latency budget**: pipeline <100 ms per decision step (excluding 3 s accumulation).
* Stable confidence behavior (no oscillation) across at least 30 consecutive decisions.

**Risks & Mitigation**

* **Low SNR** → extend window to 3.5–4 s; add PO3/PO4; move to FBCCA weighting.

---

## Phase 3 — Live Bridge (CURRY 8 → Decoder/UI)

**Objective:**
Ingest **live EEG** from the **Compumedics Neuroscan + CURRY 8** acquisition PC into the decoder/UI machine (Mac) with **<4 s end‑to‑end** selection latency.

**Scope**

* **Live pipeline A (preferred)**: CURRY’s **online MATLAB hook** (1 s chunks) → MATLAB publisher over **TCP/LSL** → Mac client (`stream/source_lsl.py`).
* **Markers**: start/stop evaluation events aligned to UI phases (or time‑locked to stimulus onset).
* **Clocking**: timestamp EEG chunks; compensate for network jitter with small input buffer.
* **Fallback**: if live is unstable, use **record‑then‑replay** (EDF) for the demo path.

**Deliverables**

* `stream/source_lsl.py` (or `source_socket.py`) + MATLAB stub for CURRY online hook.
* Simple **link monitor** overlay in UI (green = live, yellow = delayed, red = dropped).
* Logs: arrival jitter, chunk rate, buffer occupancy.

**Exit Criteria**

* End‑to‑end live loop: **user looks → decoder selects → UI confirms** (dwell) → event emitted.
* **3 successful live selections in a row** with confidence ≥ τ, and **no packet loss >2%** in the session window.
* Measured **decision latency ≤4 s** (3 s window + processing + dwell).

**Risks & Mitigation**

* **Network hiccups** → local switch or crossover cable; increase buffer 0.5–1 s; fall back to replay for the public demo while showing live logs in a side panel.

---

## Phase 4 — Local Agent Integration (Offline gpt‑oss) + BrainBus

**Objective:**
Turn brain selections into **useful local actions** (no internet) via a clean JSON **BrainBus** contract and 4 deterministic tools.

**Scope**

* **BrainBus schema** (stdin/socket):

  ```json
  { "ts": "...", "decoder": {"type":"SSVEP","version":"0.1.0"},
    "intent": {"name":"SELECT","args":{"label":"SUMMARIZE","index":0}},
    "confidence": 0.81 }
  ```
* **Agent policy**: only act when `conf ≥ τ` **and** dwell completed.
* **Tools** (offline, sandboxed to `workspace/`):

  1. `summarize(file)` → `out/summary.md`
  2. `extract_todos(file)` → `out/todos.json`
  3. `flag_deadlines(file)` → `out/deadlines.md` (+ optional `.ics`)
  4. `compose_email(topic, attachments?)` → `out/email_draft.md`
* **UX**: toast with result paths; “undo/clear” hotkey for operator.

**Deliverables**

* `bus/brainbus.py` (publisher) + `agent/run_agent.py` (subscriber).
* `agent/tools_local.py` (deterministic, reproducible results).
* Example docs in `workspace/` for demos.

**Exit Criteria**

* Selecting each of the 4 tiles results in the expected artifact files in `workspace/out/`.
* **No network calls** (verified by stubbed network layer).
* Logged **intent → tool run** within **<500 ms** after dwell confirmation.

**Risks & Mitigation**

* **Ambiguous file context** → preload a known `workspace/in/` document set; show the current “active document” title in UI.

---

## Phase 5 — Hardening, UX Polish, Packaging & Demo

**Objective:**
Ship a reliable demo & repo: **robust UX**, reproducible **replay** path, and a **<3 min video** that showcases the full offline loop.

**Scope**

* **Stability**: run‑to‑failure tests (15–20 minutes continuous); stress logs; graceful error UI.
* **Calibration quick pass** (optional): per‑user gain/channel weighting to improve confidence spreads (no heavy training).
* **UX polish**: accessibility slider for flicker intensity; clear state transitions; progress toasts with file paths.
* **Metrics overlay**: accuracy, average confidence, effective ITR estimate, decision latency histogram.
* **Packaging**: README with one‑command run; sample data; video script; category mapping (“Best Local Agent”, “Weirdest Hardware”, “For Humanity”).

**Deliverables**

* Demo **video (<3 min)**: local‑mode ON → 4 selections → outputs → metrics overlay.
* Public **repo** with reproducible **replay** demo, logs, and BrainBus schema.
* **Submission text** (what/why/how, offline constraint, benefits).

**Exit Criteria**

* One‑command **replay** demo passes end‑to‑end on a clean machine.
* Live session trial (if available) recorded as supporting material.
* Submission assets complete and internally reviewed.

**Risks & Mitigation**

* **Visual fatigue in judges** → keep evaluation bursts brief; include pause; moderate brightness by default.
* **Hardware surprise** → ensure replay path is primary demo; live mode as bonus.

---

### Ownership & Interfaces (cross‑phase)

* **UI/Stimulus** ↔ **Decoder**: `stimulus_map`, `phase` events; confidence updates.
* **Decoder** ↔ **Agent**: BrainBus JSON over local socket/stdin.
* **Live bridge** ↔ **Decoder**: LSL/TCP client with chunked arrays + timestamps.
* **Roles**: UI (PySide6), Signal (filters & CCA/FBCCA), Integration (bridge & BrainBus), Agent (tools & sandbox), PM (demo/video/docs).

This plan keeps us laser‑focused on **Proposed Solution 1**: a **reliable, offline, 4‑choice SSVEP brain‑to‑agent** that’s useful, auditable, and demo‑ready.
----

# uv

> uv is an extremely fast Python package and project manager, written in Rust.

You can use uv to install Python dependencies, run scripts, manage virtual environments,
build and publish packages, and even install Python itself. uv is capable of replacing
`pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`, `twine`, `virtualenv`, and more.

uv includes both a pip-compatible CLI (prepend `uv` to a pip command, e.g., `uv pip install ruff`)
and a first-class project interface (e.g., `uv add ruff`) complete with lockfiles and
workspace support.


## Getting started

- [Features](https://docs.astral.sh/uv/getting-started/features/index.md)
- [First steps](https://docs.astral.sh/uv/getting-started/first-steps/index.md)
- [Installation](https://docs.astral.sh/uv/getting-started/installation/index.md)

## Guides

- [Installing Python](https://docs.astral.sh/uv/guides/install-python/index.md)
- [Publishing packages](https://docs.astral.sh/uv/guides/package/index.md)
- [Working on projects](https://docs.astral.sh/uv/guides/projects/index.md)
- [Running scripts](https://docs.astral.sh/uv/guides/scripts/index.md)
- [Using tools](https://docs.astral.sh/uv/guides/tools/index.md)

## Integrations

- [Alternative indexes](https://docs.astral.sh/uv/guides/integration/alternative-indexes/index.md)
- [AWS Lambda](https://docs.astral.sh/uv/guides/integration/aws-lambda/index.md)
- [Dependency bots](https://docs.astral.sh/uv/guides/integration/dependency-bots/index.md)
- [Docker](https://docs.astral.sh/uv/guides/integration/docker/index.md)
- [FastAPI](https://docs.astral.sh/uv/guides/integration/fastapi/index.md)
- [GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/index.md)
- [GitLab CI/CD](https://docs.astral.sh/uv/guides/integration/gitlab/index.md)
- [Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/index.md)
- [marimo](https://docs.astral.sh/uv/guides/integration/marimo/index.md)
- [Pre-commit](https://docs.astral.sh/uv/guides/integration/pre-commit/index.md)
- [PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/index.md)

## Projects

- [Building distributions](https://docs.astral.sh/uv/concepts/projects/build/index.md)
- [Configuring projects](https://docs.astral.sh/uv/concepts/projects/config/index.md)
- [Managing dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/index.md)
- [Creating projects](https://docs.astral.sh/uv/concepts/projects/init/index.md)
- [Structure and files](https://docs.astral.sh/uv/concepts/projects/layout/index.md)
- [Running commands](https://docs.astral.sh/uv/concepts/projects/run/index.md)
- [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/index.md)
- [Using workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/index.md)

## Features

- [Authentication](https://docs.astral.sh/uv/concepts/authentication/index.md)
- [Build backend](https://docs.astral.sh/uv/concepts/build-backend/index.md)
- [Caching](https://docs.astral.sh/uv/concepts/cache/index.md)
- [Configuration files](https://docs.astral.sh/uv/concepts/configuration-files/index.md)
- [Package indexes](https://docs.astral.sh/uv/concepts/indexes/index.md)
- [Preview features](https://docs.astral.sh/uv/concepts/preview/index.md)
- [Python versions](https://docs.astral.sh/uv/concepts/python-versions/index.md)
- [Resolution](https://docs.astral.sh/uv/concepts/resolution/index.md)
- [Tools](https://docs.astral.sh/uv/concepts/tools/index.md)

## The pip interface

- [Compatibility with pip](https://docs.astral.sh/uv/pip/compatibility/index.md)
- [Locking environments](https://docs.astral.sh/uv/pip/compile/index.md)
- [Declaring dependencies](https://docs.astral.sh/uv/pip/dependencies/index.md)
- [Using environments](https://docs.astral.sh/uv/pip/environments/index.md)
- [Inspecting environments](https://docs.astral.sh/uv/pip/inspection/index.md)
- [Managing packages](https://docs.astral.sh/uv/pip/packages/index.md)

## Reference

- [Commands](https://docs.astral.sh/uv/reference/cli/index.md)
- [Environment variables](https://docs.astral.sh/uv/reference/environment/index.md)
- [Installer](https://docs.astral.sh/uv/reference/installer/index.md)
- [Settings](https://docs.astral.sh/uv/reference/settings/index.md)


