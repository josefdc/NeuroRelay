# NeuroRelay Accessibility Demo Brief — Local, Offline

**Persona:** User can *see* the screen and select with gaze (SSVEP). No keyboard, no mouse.  
**Goal:** The four actions should help the user get through the day quickly: summarize a doc, extract todos, flag deadlines to calendar, and draft a short email.

---

## Context (for the assistant)

The user is preparing a short demo for the OpenAI Open Model Hackathon and managing daily care tasks. Keep outputs concise, high‑contrast friendly, and easy to read aloud.

**Key preferences**
- Short lists first, then a compact paragraph.
- Avoid jargon.
- Use times in local format (HH:MM am/pm).

---

## Tasks for Today (raw notes)

- Turn the written demo script into a one‑page **summary** for judges.
- Create a **checklist** of setup steps for the live demo; @operator will run it.
- Book wheelchair taxi **by 11:00am** for the PT session.
- Print large‑font labels for the four tiles (or announce them via TTS).
- Prepare a short **email** to the hackathon organizers confirming accessibility needs.
- Charge EEG amp and laptop **by EOD**.
- Bring hydration, eye‑rest timer set to 15 min intervals.

### Extra notes
I need the agent to be safe and fully offline. If LM Studio is running, use it; otherwise use heuristics. The demo should show a clear commit (dwell ring) and then a file created in `workspace/out/`.

---

## Deadlines (explicit phrases to parse)

- **Submission** is *due on Sep 11, 2025 at 7:00 PM GMT-5* (OpenAI Open Model Hackathon).
- **PT session** is *on Sep 8, 2025 at 9:30 AM* (wheelchair taxi needed).
- **Medication pickup** is *due by tomorrow at 5:00 PM*.
- **Accessibility email** is *due by EOD Friday*.
- **Rent** is *due on Sep 5, 2025 by EOD*.

---

## Material for Summarization

### Draft Demo Script (rough)
NeuroRelay is a local, offline brain‑to‑agent demo using SSVEP with four high‑value choices. The user looks at a flickering tile to select an action. We decode with CCA over O1/Oz/O2 in a 3‑second window, then confirm with a 1.2‑second dwell. On commit, a local agent writes the result into `workspace/out/`. If LM Studio is available, gpt‑oss generates higher quality outputs via a /v1/chat/completions‑compatible endpoint; if not, the agent falls back to deterministic heuristics for safety and reproducibility.

The interface is designed for users who can see visual stimuli but may not be able to type or speak. It emphasizes large targets, high‑contrast visuals, adjustable intensity, and clear neurofeedback (confidence bar + dwell ring). The four actions map to realistic daily needs: summarize a document, extract todos, flag deadlines (and emit ICS), and draft an email. Everything runs without internet.

### What a good 3‑minute demo shows
1. Launch UI (simulation or live).
2. Drop this file into `workspace/in/`.
3. Gaze at **SUMMARIZE** → summary file appears.  
4. Gaze at **TODOS** → checklist appears.  
5. Gaze at **DEADLINES** → markdown + ICS file appears.  
6. Gaze at **EMAIL** → short draft referencing the active document.

---

## Email Draft Hints (topic & tone)
**Topic idea:** “Accessibility confirmation for demo session”  
Tone: friendly, brief, helpful. Mention the PT appointment time conflict if any and request a slot with minimal flicker exposure if possible.

---

## Appendix: Operator Run Sheet (checklist style)
- [ ] Start LM Studio; load `openai/gpt-oss-20b` and enable the local server at `http://localhost:1234/v1`.
- [ ] Place this file into `workspace/in/` so it becomes the active document.
- [ ] Start UI in simulation first: `uv run neurorelay-ui` (use **1..4** to simulate).
- [ ] If doing live: start LSL EEG source, then `uv run neurorelay-ui --live --auto-freqs --prediction-rate 4`.
- [ ] Verify dwell commit and check `workspace/out/` for results.
- [ ] Keep brightness moderate; allow eye rest between selections.
