

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

# Phase 4 — Local Agent Integration (LM Studio + BrainBus) ✅

NeuroRelay now turns brain selections into **useful, offline actions** via a local agent powered by **LM Studio** running **gpt‑oss‑20b/120b**. The UI sends **BrainBus JSON** to a subprocess agent; the agent runs one of four tools inside your `workspace/` sandbox and logs auditable JSONL.

## One‑time setup

```bash
# Install Phase 1–3 + agent extras
uv sync --extra ui --extra agent
```

### Install & run LM Studio (optional, but recommended)

LM Studio exposes a local **/v1/chat/completions** endpoint that the agent can call **offline**.

1. Install LM Studio (Windows/macOS/Linux)
2. Download & load a gpt‑oss model

   * `openai/gpt-oss-20b` (fits on good consumer GPUs / Apple Silicon)
   * `openai/gpt-oss-120b` (≥60GB VRAM)
3. Start the local server (`Settings → Developer → Enable local server`) so it listens on `http://localhost:1234/v1`.

> The agent automatically detects LM Studio. If it's not running, it falls back to **heuristic** summaries/emails.

Environment overrides (optional):

```bash
export NEURORELAY_LMSTUDIO_URL="http://localhost:1234/v1"
export NEURORELAY_GPT_MODEL="openai/gpt-oss-20b"
export NEURORELAY_LLM_TIMEOUT=30
```

## Run the live demo

```bash
# Start your EEG LSL stream (OpenBCI, Neuroscan via CURRY→MATLAB, etc.)

# Launch the UI in live mode (or omit --live to use Phase-1 simulator)
uv run neurorelay-ui --live --auto-freqs --prediction-rate 4
```

What happens:

* Gaze → SSVEP detection (CCA) → dwell confirm → UI **commits** selection.
* UI posts a **BrainBus JSON** event to the local agent.
* Agent executes the tool **inside `workspace/`** and writes outputs to **`workspace/out/`**.
* Agent Dock shows:
  `agent: summarize → workspace/out/report_summary.md • conf=0.82`

### Folder conventions

```
workspace/
├─ in/        # put input docs here (pdf/txt/md/docx)
└─ out/       # results (summary/todos/deadlines/email drafts)
```

If you don't specify a file, the agent uses the **most recent** file from `workspace/in`.

## Tools

1. **summarize(file)** → `out/<basename>_summary.md`
   LM Studio‑backed chunked summary, fallback heuristic if LM Studio not running.
2. **extract\_todos(file)** → `out/<basename>_todos.md`
   Imperative lines, `@owner` detection, deadline markers → checkboxes.
3. **flag\_deadlines(file)** → `out/<basename>_deadlines.md` (+ `.ics`)
   Extracts due/deliver/submit/by/on phrases, parses dates, writes optional calendar.
4. **compose\_email(topic, attachments?)** → `out/draft_<ts>.md`
   Concise email (Subject + body). Attaches the active file name in the prompt.

## BrainBus events (examples)

UI → Agent:

```json
{
  "ts": "auto",
  "decoder": {"type":"SSVEP","version":"0.1.0"},
  "intent": {"name":"SELECT","args":{"label":"SUMMARIZE","index":0}},
  "confidence": 0.81,
  "context": { "file": "workspace/in/report_q3.pdf" }
}
```

Agent → UI:

```json
{
  "type": "agent_result",
  "ts": "2025-09-02T12:34:56.123Z",
  "label": "SUMMARIZE",
  "confidence": 0.81,
  "status": "ok",
  "tool": "summarize",
  "out": "workspace/out/report_q3_summary.md"
}
```

## Logs

* `logs/agent.jsonl` — every event & result (rotating is easy to add)
* `logs/*.jsonl` from the rest of the system remain unchanged

## Safety & Privacy

* **Offline**: No internet usage. LM Studio, if used, is **local only** (`localhost`).
* **Sandboxed**: Reads from `workspace/in/`, writes to `workspace/out/`.
* **Non‑destructive**: Draft files only; **no email is actually sent**.

---

## uv

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


=================================

Perfect—your code looks great and the UI polish is in. Here’s a clean, copy-paste-ready block you can drop into the README to document how to run it, the settings, and all keyboard controls.

---

---

---

# Phase Status Summary

## ✅ Phase 1 Complete: Stimulus/UI + Replay Harness
* **PySide6 2×2 SSVEP stimulus** with frame-locked flicker (8.57, 10, 12, 15 Hz)
* **Neurofeedback UI**: confidence bars, dwell rings, intensity controls
* **Synthetic data generation**: `neurorelay-gen-synth` for testing
* **Replay harness**: Ready for EDF/CSV playback (Phase 2+)

## ✅ Phase 2 Complete: Live LSL Bridge + Online SSVEP Detector  
* **LSL stream receiver** with thread-safe ring buffer (`neurorelay.stream.lsl_source`)
* **CCA-based SSVEP detector** with preprocessing (`neurorelay.signal.ssvep_detector`)
* **Qt live bridge** for PySide6 integration (`neurorelay.bridge.qt_live_bridge`)
* **Console demo**: `neurorelay-stream-demo` for testing with live EEG streams
* **Performance optimized**: Vectorized filters, ring buffer, and CCA computation
* **Robust numerics**: Safe filter bounds, regularized CCA, improved error handling
* **Tested**: Synthetic signals correctly detected, all tests pass, 19/19 ✓

## 🚧 Phase 3 Complete: UI Integration + Live Demo ✅
* **Live SSVEP detection** fully integrated into 4-button UI
* **Status lamp**: Green (connected), yellow (delayed), red (no data)
* **Real-time confidence** updates from live EEG predictions
* **Stability + dwell policy**: Winner stays stable for ≥3 predictions, conf ≥ τ=0.65, dwell fills over 1.2s
* **Live commit**: Selection committed to Agent Dock with confidence score
* **Dual mode**: `--live` for real EEG streams, Phase 1 simulator when not specified
* **End-to-end**: User gazes at tile → real-time frequency detection → dwell confirmation → commit

## 📋 Phase 4 Planned: Local Agent Integration
* Wire `LivePredictor` into existing 4-button UI
* Replace simulator confidence updates with real SSVEP predictions  
* Add LSL connection status and stream info display
* Live demo: user gazes at tiles → real-time frequency detection → UI feedback
* **Goal**: End-to-end live SSVEP selection with <4s latency

## 📋 Phase 4 Planned: Local Agent Integration
* BrainBus JSON protocol for intent→action mapping
* 4 offline tools: summarize, extract TODOs, flag deadlines, compose email
* Agent sandbox (`workspace/` → `workspace/out/`)

---

---

# NeuroRelay — Phase 3 (UI Integration + Live Demo) ✅

## Quick start (live SSVEP → UI)

```bash
# 0) Install UI + streaming extras
uv sync -E ui -E stream

# 1) Install liblsl (required for pylsl)
# Option A: conda
conda install -c conda-forge liblsl
# Option B: download from releases and ensure pylsl can find it
# https://github.com/sccn/liblsl/releases

# 2) Start your EEG LSL stream (e.g., OpenBCI GUI, CURRY→MATLAB bridge)

# 3) Launch the live UI
uv run neurorelay-ui --live --auto-freqs --lsl-type EEG --prediction-rate 4
```

**What you'll see**

* The same 2×2 **flicker tiles** (SUMMARIZE / TODOS / DEADLINES / EMAIL).
* A **status dot** near the bottom: **green** = healthy, **yellow** = delayed, **red** = no data.
* **Confidence underlines** update from *live* scores.
* A **dwell ring** fills once the winner stays stable and above threshold; when full, a "selection committed" toast appears in the Agent Dock (Phase 4 will execute tools).

### Controls

* **H** — Toggle HUD (operator info & buttons)
* **Space** — Pause/Resume feedback (dwell pauses)
* **ESC** — Exit
* **F11** — Fullscreen
* **1/2/3/4** — (Dev) Simulate winner (unchanged from Phase 1)

### Recommended settings

* Match your display refresh with `--auto-freqs` **or** set `monitor_hz` in `config/default.json`.

  * At \~**60 Hz** the app uses **8.57, 10, 12, 15 Hz**; at \~**50 Hz** it uses **8.33, 10, 12.5, 16.67 Hz**.
* Keep flicker **below 20 Hz** for comfort; if your monitor is **120 Hz**, prefer `--auto-freqs` only if it yields acceptable freqs or set freqs manually in the config.

### Live policy (P0 defaults)

* **Threshold** `τ = 0.65` (softmax of z‑scored scores)
* **Stability**: winner must remain top‑1 for **≥3 consecutive predictions** (with default prediction rate **4 Hz** ≈ 0.75 s)
* **Dwell**: **1.2 s** of continuous stability + threshold to **commit**
* **Tie guard**: if top‑1 – top‑2 < **0.05**, dwell doesn't accumulate ("need more evidence")

### CLI (new Phase‑3 flags)

```bash
uv run neurorelay-ui --live \
  --auto-freqs \
  --lsl-type EEG \
  --lsl-name "OpenBCI_EEG" \
  --lsl-timeout 5.0 \
  --prediction-rate 4.0 \
  --fullscreen
```

**Notes**

* If you see **"pylsl not available"**, run `uv sync -E stream` and install **liblsl**.
* The UI will show **"Live SSVEP mode active"** in the status bar when connected.
* The **Agent Dock** shows commits (file actions come in Phase 4).

---

## Quick start

```bash
# 0) Install stream dependencies
uv sync -E stream

# 1) Install LSL library (required for pylsl)
# Option A: Using conda
conda install -c conda-forge liblsl

# Option B: Download from releases and set PYLSL_LIB
# https://github.com/sccn/liblsl/releases

# 2) Start your EEG LSL stream (OpenBCI, Neuroscan, etc.)

# 3) Run the live console demo
uv run neurorelay-stream-demo --stream-type EEG --window 3.0 --step 0.5 --bandpass "6,40" --notch 60

# Or specify custom frequencies
uv run neurorelay-stream-demo --freqs "8.57,10,12,15" --window 3.0 --step 0.5 --bandpass "6,40" --notch 60
```

You'll see rolling predictions like:
```
Prediction: 10.0 Hz | Confidence: 0.82
Prediction: 12.0 Hz | Confidence: 0.75
Prediction: 10.0 Hz | Confidence: 0.91
```

## Key Improvements in Phase 2
* **Robust numerics**: CCA uses direct covariance computation with regularization and `eigvalsh` for stability
* **Vectorized performance**: Filters applied across all channels at once, ring buffer uses slice operations
* **Safe bounds checking**: Bandpass frequencies clamped to valid ranges, notch frequency validation
* **Qt parent management**: Timer properly parented to avoid memory leaks
* **Default frequencies**: Console demo works out-of-box without requiring `--freqs` argument

## Integration with PySide6 UI

```bash
# Install both stream + ui dependencies
uv sync -E stream -E ui

# In your Python code:
from neurorelay.bridge.qt_live_bridge import create_live_predictor

predictor = create_live_predictor(
    stream_type="EEG",
    frequencies=[8.57, 10.0, 12.0, 15.0],
    window_seconds=3.0,
    channels=["O1", "Oz", "O2"],  # Optional channel selection
    bandpass=(6.0, 40.0),
    notch=60.0
)

# Connect Qt signal
predictor.prediction.connect(lambda freq, conf, scores: print(f"Detected: {freq} Hz, conf: {conf:.3f}"))

# Start live prediction
if predictor.start():
    print("Live SSVEP detection started!")
```

## What's included

### Core Components

* **`neurorelay.stream.lsl_source`** — LSL receiver with thread-safe ring buffer
* **`neurorelay.signal.ssvep_detector`** — CCA-based SSVEP detector with preprocessing
* **`neurorelay.bridge.qt_live_bridge`** — Qt integration for PySide6 applications

### Features

* **Real-time LSL streaming** with configurable buffer (default 10s)
* **CCA detection** using sine/cosine references with harmonics
* **Preprocessing**: bandpass filter (5-40 Hz default) + optional notch (50/60 Hz)
* **Channel selection**: specify channels like `["O1", "Oz", "O2"]` or use all available
* **Confidence estimation**: z-score normalized softmax across frequencies
* **Qt signals**: `prediction(freq, confidence, scores)`, `status_changed(message)`

### Console Demo Options

```bash
# Basic usage
uv run neurorelay-stream-demo --freqs "8,10,12,15"

# Full configuration
uv run neurorelay-stream-demo \
  --stream-type EEG \
  --stream-name "OpenBCI_EEG" \
  --freqs "8.57,10,12,15" \
  --window 3.0 \
  --step 0.25 \
  --channels "O1,Oz,O2" \
  --bandpass "6,40" \
  --notch 60 \
  --method cca \
  --verbose

# Auto-stop after N predictions (for testing)
uv run neurorelay-stream-demo --freqs "10,12" --max-predictions 20
```

### Method Options

* **`--method cca`** (default): Canonical Correlation Analysis with sine/cosine references
* **`--method power`**: Simple power spectrum approach (FFT-based)

---

## LSL Stream Requirements

Your EEG device should publish an LSL stream with:
- **Type**: `"EEG"` (or specify with `--stream-type`)
- **Sampling rate**: ≥200 Hz (250+ Hz recommended)
- **Channels**: Include occipital channels (O1, Oz, O2) for best SSVEP detection

### Tested LSL Sources
- OpenBCI GUI (Cyton/Daisy boards)
- Neuroscan CURRY 8 (via MATLAB online bridge)
- LSL simulation tools

---

## Integration with Phase 1 UI

To wire live predictions into the existing 4-button UI:

```python
# In your ssvep_4buttons.py modifications:
from neurorelay.bridge.qt_live_bridge import create_live_predictor

class SSVEPWidget(QWidget):
    def __init__(self):
        super().__init__()
        # ... existing UI setup ...
        
        # Add live predictor
        self.live_predictor = create_live_predictor(
            frequencies=[8.57, 10.0, 12.0, 15.0],
            window_seconds=3.0,
            channels=["O1", "Oz", "O2"]
        )
        
        # Connect signals
        self.live_predictor.prediction.connect(self._on_live_prediction)
        self.live_predictor.status_changed.connect(self._on_status_change)
    
    def _on_live_prediction(self, frequency: float, confidence: float, scores: dict):
        """Handle live SSVEP predictions."""
        if confidence > 0.65:  # Threshold
            # Update UI confidence bars and trigger dwell logic
            self._update_confidence_display(frequency, confidence, scores)
    
    def start_live_mode(self):
        """Enable live SSVEP detection."""
        if self.live_predictor.start():
            self.status_bar.showMessage("Live SSVEP mode active")
```

---

## Tests and Standalone Usage

```bash
# Run SSVEP detection tests (works without LSL)
uv run pytest tests/test_ssvep.py -v

# Test SSVEP detector directly in Python:
uv run python -c "
from neurorelay.signal.ssvep_detector import SSVEPDetector, SSVEPConfig
import numpy as np

# Create detector
config = SSVEPConfig(
    frequencies=[8.0, 10.0, 12.0, 15.0],
    sample_rate=250.0,
    window_seconds=3.0
)
detector = SSVEPDetector(config)

# Generate synthetic SSVEP at 10 Hz
t = np.linspace(0, 3, 750)  # 3s at 250 Hz
signal = np.sin(2 * np.pi * 10.0 * t) + 0.1 * np.random.randn(750)
data = np.column_stack([signal, signal, signal])  # 3 channels

# Detect
freq, conf, scores = detector.detect(data)
print(f'Detected: {freq} Hz, confidence: {conf:.3f}')
print(f'Scores: {scores}')
"

# Run all tests
uv run pytest
```

---

## Architecture Notes

### Threading Model
- **LSL acquisition**: Background thread fills ring buffer
- **Qt predictions**: Timer-based predictions at 4 Hz (configurable)
- **Thread safety**: Ring buffer uses `threading.RLock()`

### Latency Budget
- LSL chunk reception: ~20-50ms
- Ring buffer access: ~1ms  
- CCA computation: ~10-40ms (3s window, 3 channels)
- Qt signal emission: ~1ms
- **Total**: ~30-100ms processing latency (excluding EEG window accumulation)

### Memory Usage
- Ring buffer: ~10s * 250 Hz * 32 channels * 4 bytes = ~320KB default
- CCA references: Negligible (~few KB)
- Filter states: ~few KB

---

# NeuroRelay — Phase 1 (Stimulus/UI + Replay Harness) ✅

## Quick start

```bash
# 0) Install UI deps
uv sync -E ui

# 1) (Optional) generate a synthetic session CSV for future replay/tests
uv run neurorelay-gen-synth --out data/sim_session.csv --seed 42 --freqs "8.57,10,12,15"

# 2) Launch the 2×2 SSVEP stimulus UI
uv run neurorelay-ui --config config/default.json --mode sinusoidal --fullscreen
```

### Useful variants

```bash
# Auto-pick frequencies from monitor refresh (50 Hz → 8.33/10/12.5/16.67; 60 Hz → 8.57/10/12/15)
uv run neurorelay-ui --config config/default.json --auto-freqs

# Visual debugging (high-contrast flicker)
uv run neurorelay-ui --config config/default.json --mode square

# Windowed (no fullscreen)
uv run neurorelay-ui --config config/default.json
```

> Tip: For real sessions, prefer `--mode sinusoidal`. Use `--mode square` only for quick visual checks.

---

## What you’ll see

* **2×2 grid** of flickering tiles (SUMMARIZE / TODOS / DEADLINES / EMAIL) with generous **gaze gutters**.
* **Intensity bar** (always visible) at the bottom left — adjust luminance for comfort.
* **Agent Dock (placeholder)** at the bottom right — reserved for future BrainBus→Agent messages.
* **HUD** (hidden by default): mode, monitor Hz, stimulus map, and operator buttons.

---

## Keyboard controls (operator)

* **H** — Toggle HUD (show/hide operator info & buttons)
* **F11** — Fullscreen ↔ windowed
* **Space** — Pause / Resume flicker & feedback
* **ESC** — Exit

**Phase-1 simulator controls (to preview neurofeedback UI):**

* **1** or **← / ↑** — set “winner” to **SUMMARIZE**
* **2** or **→** — set “winner” to **TODOS**
* **3** or **↓** — set “winner” to **DEADLINES**
* **4** — set “winner” to **EMAIL**
* **A** — Toggle Agent Dock visibility

---

## Operator flow

1. Launch the UI (fullscreen recommended).
2. Adjust the **Intensity** slider for comfort.
3. Press **H** if you want to see the HUD and the **Start Evaluate** button.
4. Press **Start Evaluate** (or just use the simulator keys 1–4) to watch the **confidence underline** fill and the **dwell ring** animate.
5. **Space** to pause anytime.

---

## Config (defaults in `config/default.json`)

```json
{
  "monitor_hz": 60,                      // Display refresh rate (used for timer pacing)
  "freqs_hz": [8.57, 10.0, 12.0, 15.0],  // Per-tile flicker frequencies (Hz)
  "window_sec": 3.0,                     // Decision window (for Phase 2+)
  "step_sec": 0.5,                       // Sliding step (for Phase 2+)
  "dwell_sec": 1.2,                      // Dwell time to confirm (UI visualization)
  "tau": 0.65,                           // Confidence threshold (Phase 2+)
  "channels": ["O1", "Oz", "O2"],        // EEG channels (Phase 2+)
  "bandpass_hz": [5, 40],                // Preproc band (Phase 2+)
  "notch_hz": 60,                        // Notch (env matched; Phase 2+)
  "decoder": "CCA",                      // "CCA" or "FBCCA" (Phase 2+)
  "artifact_guard": true,                // Blink/EMG guard (Phase 2+)
  "sandbox_root": "workspace",           // Agent sandbox root (Phase 4)
  "out_dir": "workspace/out",
  "flicker_mode": "sinusoidal",          // UI default flicker
  "ui_intensity": 0.85                   // Initial UI intensity (0..1)
}
```

**Auto frequencies:** If you pass `--auto-freqs`, the app derives the four freqs from `monitor_hz`:

* \~**50 Hz** displays → `[Hz/6, Hz/5, Hz/4, Hz/3]` → `8.33, 10, 12.5, 16.67 Hz`
* otherwise → `[Hz/7, Hz/6, Hz/5, Hz/4]` → `8.57, 10, 12, 15 Hz` for 60 Hz

---

## Agent placeholder

* The **Agent Dock** (bottom-right) shows `agent: waiting… (placeholder)` now.
* In Phase 4, post events/messages there, e.g.:

  ```
  agent: summarize → out/report_q3_summary.md  •  conf=0.82
  ```
* You can toggle it with **A**.

---

## Synthetic data (for replay/tests)

Generate a CSV with labeled, noisy sinusoids (O1/Oz/O2):

```bash
uv run neurorelay-gen-synth --out data/sim_session.csv \
  --sr 250 --monitor-hz 60 --seed 123 --freqs "8.57,10,12,15"
# or let it compute from the monitor:
uv run neurorelay-gen-synth --out data/sim_session.csv --freqs auto --monitor-hz 50
```

*(Replay into a decoder comes in Phase 2 — the harness is ready in `neurorelay.stream.source_replay.ReplayConfig` and `replay_chunks()`.)*

---

## Tests

```bash
uv run pytest
```

---

## Tuning notes

* **Gutters** (tile spacing) scale with window size (`~4%` of the smaller dimension, min `24 px`).
  To widen: change `0.04` → `0.05` in `_apply_gutters()` in `ssvep_4buttons.py`.
* For quick visual debugging, use `--mode square` and set the intensity slider near **100%**.

---

