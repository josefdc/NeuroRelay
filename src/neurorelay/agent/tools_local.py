# src/neurorelay/agent/tools_local.py
from __future__ import annotations
import os
import re
import time
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Callable, Any

from dateutil import parser as dparser
from icalendar import Calendar, Event

# Optional imports for file parsing
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
except Exception:
    pdf_extract_text = None

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

# Optional LLM backends
_LLM_ERR = None
try:
    import lmstudio as lms
except Exception as e:
    lms = None
    _LLM_ERR = e

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import pyttsx3  # offline TTS
except Exception:
    pyttsx3 = None


# New, pragmatic 4-option set (keep legacy labels accepted too)
LABELS = (
    "HELP", "READ", "PLAN", "MESSAGE",
    "SUMMARIZE", "TODOS", "DEADLINES", "EMAIL",
)

SAFE_EXTS = {".txt", ".md", ".pdf", ".docx"}


@dataclass
class AgentConfig:
    sandbox_root: Path = Path("workspace")
    out_dir: Path = Path("workspace/out")
    in_dir: Path = Path("workspace/in")
    model_name: str = os.environ.get("NEURORELAY_GPT_MODEL", "openai/gpt-oss-20b")
    lm_url: str = os.environ.get("NEURORELAY_LMSTUDIO_URL", "http://localhost:1234/v1")
    llm_timeout: float = float(os.environ.get("NEURORELAY_LLM_TIMEOUT", "30"))


def ensure_dirs(cfg: AgentConfig) -> None:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)


def in_sandbox(cfg: AgentConfig, p: Path) -> bool:
    try:
        rp = p.resolve()
        root = cfg.sandbox_root.resolve()
        # Python 3.11+: safe relative check
        if hasattr(rp, "is_relative_to"):
            return rp.is_relative_to(root)
        # Fallback
        return str(rp).startswith(str(root))
    except Exception:
        return False


def pick_active_document(cfg: AgentConfig) -> Optional[Path]:
    """Pick the most recent file in workspace/in with a safe extension."""
    if not cfg.in_dir.exists():
        return None
    best = None
    best_m = -1
    for p in cfg.in_dir.glob("**/*"):
        if p.is_file() and p.suffix.lower() in SAFE_EXTS:
            m = p.stat().st_mtime
            if m > best_m:
                best_m = m
                best = p
    return best


# -----------------------------
# Text extraction
# -----------------------------

def read_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return path.read_text(errors="replace")
    if ext == ".pdf":
        if pdf_extract_text is None:
            return f"[pdfminer.six not installed; cannot read {path.name}]"
        try:
            return pdf_extract_text(str(path))
        except Exception as e:
            return f"[error reading PDF: {e!r}]"
    if ext == ".docx":
        if DocxDocument is None:
            return f"[python-docx not installed; cannot read {path.name}]"
        try:
            doc = DocxDocument(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            return f"[error reading DOCX: {e!r}]"
    # Fallback binary-safe
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return path.read_text(errors="replace")


def chunk_text(s: str, chunk_chars: int = 6000, overlap: int = 400) -> List[str]:
    s = s.strip()
    if not s:
        return []
    if len(s) <= chunk_chars:
        return [s]
    chunks = []
    i = 0
    while i < len(s):
        chunks.append(s[i:i+chunk_chars])
        if i + chunk_chars >= len(s):
            break
        i += (chunk_chars - overlap)
    return chunks


# -----------------------------
# LLM wrapper (LM Studio local)
# -----------------------------

class LocalLLM:
    """Try LM Studio via lmstudio SDK; fallback to OpenAI SDK pointing at LM Studio; else disabled."""
    def __init__(self, model: str, base_url: str, timeout: float = 30.0):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._mode = None
        self._client = None
        self._boot()

    def _boot(self):
        if lms is not None:
            try:
                self._client = lms.llm(self.model)
                self._mode = "lmstudio"
                return
            except Exception:
                pass
        if OpenAI is not None:
            try:
                self._client = OpenAI(base_url=self.base_url, api_key="not-needed", timeout=self.timeout)
                self._mode = "openai"
                return
            except Exception:
                pass
        self._mode = "none"

    def available(self) -> bool:
        return self._mode in ("lmstudio", "openai")

    @property
    def mode(self) -> str:
        return self._mode or "none"

    def chat(self, system: str, user: str) -> str:
        if self._mode == "lmstudio":
            try:
                chat = lms.Chat(system)
                chat.add_user_message(user)
                buf: List[str] = []
                self._client.act(
                    chat,
                    [],  # no tools in this wrapper
                    # final message appending to chat is not required for our return value
                    on_message=lambda msg: None,
                    on_prediction_fragment=lambda frag, round_index=0: buf.append(frag.content),
                )
                return "".join(buf).strip()
            except Exception:
                return ""
        elif self._mode == "openai":
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception:
                return ""
        return ""

# -----------------------------
# Helpers
# -----------------------------
def _now_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

# -----------------------------
# Tools
# -----------------------------

def tool_summarize(cfg: AgentConfig, file: Path) -> Path:
    ensure_dirs(cfg)
    text = read_text(file)
    out = cfg.out_dir / f"{file.stem}_summary.md"

    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    if llm.available() and len(text) > 0:
        chunks = chunk_text(text)
        notes: List[str] = []
        sys_prompt = (
            "You are a precise offline writing assistant on a local machine. "
            "Summarize the document concisely, starting with bullet points, then a short paragraph. "
            "Keep facts, dates, figures; avoid speculation; preserve section structure if obvious."
        )
        for i, ch in enumerate(chunks):
            msg = (
                f"Document chunk {i+1}/{len(chunks)} (raw text):\n"
                f"{ch}\n\n"
                "Write a concise chunk summary (bullets + 3-5 sentence paragraph):"
            )
            try:
                response = llm.chat(sys_prompt, msg)
                if response:  # Only append non-empty responses
                    notes.append(response)
            except Exception:
                pass  # Skip chunks that fail
        
        if notes:  # Only if we got some LLM responses
            try:
                final = llm.chat(
                    sys_prompt,
                    "Combine the chunk summaries below into a single coherent summary with:\n"
                    "1) 5–10 bullets (most important first),\n"
                    "2) short narrative (≤150 words),\n"
                    "3) any deadlines or action items if present.\n\n"
                    + "\n\n---\n\n".join(notes)
                )
                if final:  # If LLM final summarization worked, use it
                    out.write_text(final, encoding="utf-8")
                    return out
            except Exception:
                pass  # Fall through to heuristic
    
    # Heuristic fallback
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = lines[:40]
    bullets = [ln for ln in head if ln[:2] in ("- ", "* ")]
    para = " ".join(head)[:1200]
    final = (
        "## Summary (heuristic)\n\n"
        + ("\n".join(bullets[:8]) + "\n\n" if bullets else "")
        + para
    )

    out.write_text(final, encoding="utf-8")
    return out


_IMP_VERB = re.compile(r"^\s*(?:-|\*|\d+[.)]|•)?\s*(?:please\s+)?([A-Za-z][a-z]+)\b", re.I)
_DUE_KEY = re.compile(r"\b(due|deadline|deliver|submit|by|on|eta|eod|cob)\b", re.I)

def tool_todos(cfg: AgentConfig, file: Path) -> Path:
    ensure_dirs(cfg)
    text = read_text(file)
    out = cfg.out_dir / f"{file.stem}_todos.md"

    lines = [ln.rstrip() for ln in text.splitlines()]
    todos: List[str] = []
    for ln in lines:
        if len(ln) < 6:
            continue
        if ln.strip().startswith(("#", ">")):
            continue
        if _IMP_VERB.search(ln) or ln.strip().startswith(("- ", "* ", "• ")):
            # Capture owner-ish tokens
            owner = ""
            if "@" in ln:
                m = re.search(r"@([A-Za-z0-9_\-\.]+)", ln)
                if m:
                    owner = f" @{m.group(1)}"
            due = " ⏰" if _DUE_KEY.search(ln) else ""
            todos.append(f"- [ ] {ln.strip()}{owner}{due}")

    if not todos:
        todos = ["- [ ] (No action items detected)"]

    md = "# Extracted TODOs\n\n" + "\n".join(todos) + "\n"
    out.write_text(md, encoding="utf-8")
    return out


_DATE_WINDOW = (dparser.parserinfo(),)

def _find_dates(text: str) -> List[Tuple[str, Optional[str]]]:
    hits: List[Tuple[str, Optional[str]]] = []
    # simple date/relative phrases
    patt = re.compile(
        r"(?P<frag>(?:due|deadline|deliver|submit|by|on)\s+(?:\w+\s+){0,4}?(?:\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?|\w+\s+\d{1,2}(?:,\s*\d{2,4})?|next\s+\w+|tomorrow|today|eod|cob))",
        re.I,
    )
    for m in patt.finditer(text):
        frag = m.group("frag")
        try:
            dt = dparser.parse(frag, fuzzy=True, dayfirst=False)
            iso = dt.isoformat() if dt else None
        except Exception:
            iso = None
        hits.append((frag.strip(), iso))
    return hits


def tool_deadlines(cfg: AgentConfig, file: Path) -> Path:
    ensure_dirs(cfg)
    text = read_text(file)
    out_md = cfg.out_dir / f"{file.stem}_deadlines.md"
    out_ics = cfg.out_dir / f"{file.stem}_deadlines.ics"

    found = _find_dates(text)
    if not found:
        out_md.write_text("# Deadlines\n\n(No deadlines detected)\n", encoding="utf-8")
        # No ICS if nothing
        return out_md

    # Markdown
    md = ["# Deadlines\n"]
    for frag, iso in found:
        md.append(f"- {frag}" + (f" → {iso}" if iso else ""))
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    # ICS
    cal = Calendar()
    cal.add("prodid", "-//NeuroRelay//Deadlines//EN")
    cal.add("version", "2.0")
    for frag, iso in found:
        if not iso:
            continue
        try:
            dt = dparser.parse(iso)
            ev = Event()
            ev.add("summary", frag[:120])
            ev.add("dtstart", dt)
            ev.add("dtend", dt)  # all-day / instant markers
            ev.add("description", frag)
            cal.add_component(ev)
        except Exception:
            pass
    out_ics.write_bytes(cal.to_ical())
    return out_md


def tool_email(cfg: AgentConfig, topic: str, attachments: Optional[List[Path]] = None) -> Path:
    ensure_dirs(cfg)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = cfg.out_dir / f"draft_{ts}.md"
    att_list = [p.name for p in (attachments or []) if p.exists()]

    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    body = ""
    if llm.available():
        system = (
            "You are a concise professional email assistant running entirely offline on a local machine. "
            "Write clear, friendly emails. Prefer short paragraphs and bullets when appropriate."
        )
        user = (
            f"Draft an email about: {topic}\n\n"
            f"Include a subject line and a brief body. Keep it under 150 words.\n"
            f"Attachments available: {', '.join(att_list) if att_list else '(none)'}"
        )
        try:
            body = llm.chat(system, user).strip()
        except Exception:
            pass
    
    if not body:  # LLM failed or not available, use heuristic
        body = (
            f"**Subject:** {topic}\n\n"
            "Hi NAME,\n\n"
            f"Just a quick note regarding {topic.lower()}.\n\n"
            "- Context here\n"
            "- Next steps here\n\n"
            "Best,\nYour Name\n"
        )
    out.write_text(body, encoding="utf-8")
    return out


# -----------------------------
# New pragmatic tools
# -----------------------------
def tool_help(cfg: AgentConfig) -> Tuple[Path, str]:
    """Create a HELP card text and write a small log file."""
    ensure_dirs(cfg)
    ts = _now_stamp()
    out = cfg.out_dir / f"HELP_{ts}.md"
    # Try LLM for a friendly, accessible help message
    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    overlay = ""
    if llm.available():
        system = (
            "You write very short, high-contrast on-screen help cards for a nearby caregiver. "
            "The user can only use eye-gaze. Keep it calm, clear, large-font friendly."
        )
        user = "Write one line asking for immediate help, and a second line showing the current time."
        try:
            overlay = llm.chat(system, user).strip()
        except Exception:
            pass
    if not overlay:
        overlay = f"PLEASE HELP ME\n{time.strftime('%H:%M:%S')}"
    out.write_text(overlay + "\n", encoding="utf-8")
    return out, overlay

def tool_read_aloud(cfg: AgentConfig, file: Path) -> Tuple[Path, str]:
    """LLM speech summary + offline TTS (pyttsx3)."""
    ensure_dirs(cfg)
    text = read_text(file)
    ts = _now_stamp()
    out = cfg.out_dir / f"{file.stem}_read_{ts}.md"

    # Ask LLM for a speech-friendly 150–200 word summary
    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    speech = ""
    if llm.available() and text.strip():
        try:
            speech = llm.chat(
                "You are an assistive reading aid. Create a 150–200 word speech-friendly summary. "
                "Use short sentences and plain language.",
                f"Document text:\n{text[:8000]}\n\nWrite the speech now:"
            )
        except Exception:
            pass
    if not speech:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        speech = " ".join(lines[:60])[:1200] or "(Nothing to read.)"
    out.write_text(speech, encoding="utf-8")

    # Offline TTS
    if pyttsx3 is not None:
        try:
            engine = pyttsx3.init()
            engine.say(speech)
            engine.runAndWait()
        except Exception:
            pass
    return out, "Speaking…"

def tool_plan(cfg: AgentConfig, file: Path) -> Path:
    """Step-by-step plan from the active doc (LLM-first; falls back to TODOs)."""
    ensure_dirs(cfg)
    text = read_text(file)
    out = cfg.out_dir / f"{file.stem}_plan.md"
    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    plan = ""
    if llm.available() and text.strip():
        try:
            plan = llm.chat(
                "You create short practical action plans. Return 5–8 numbered steps,"
                " each ≤18 words, and a 2‑sentence overview.",
                f"Make a plan for this document:\n{text[:8000]}"
            )
        except Exception:
            pass
    if not plan:
        # fallback: reuse TODO extraction
        tmp = tool_todos(cfg, file)
        plan = "# Plan (heuristic)\n\n" + tmp.read_text(encoding="utf-8")
    out.write_text(plan, encoding="utf-8")
    return out

def tool_message(cfg: AgentConfig, topic: Optional[str], attachment: Optional[Path]) -> Tuple[Path, str]:
    """Compose a short caregiver message and return overlay text."""
    ensure_dirs(cfg)
    ts = _now_stamp()
    out = cfg.out_dir / f"draft_{ts}.md"
    llm = LocalLLM(cfg.model_name, cfg.lm_url, cfg.llm_timeout)
    att = attachment.name if (attachment and attachment.exists()) else None
    body = ""
    if llm.available():
        try:
            body = llm.chat(
                "You are a concise caregiver-messaging assistant. Produce a short, friendly message with a clear ask.",
                f"Topic: {topic or 'general update'}\nAttachment: {att or '(none)'}"
            )
        except Exception:
            pass
    if not body:
        body = f"**Message:** Could you please help me with {topic or 'this'}?\n\nThank you."
    out.write_text(body, encoding="utf-8")
    # Overlay: large-print first line(s)
    overlay = body.splitlines()[0][:120]
    return out, overlay


# Top-level dispatcher

def handle_selection(
    label: str,
    cfg: AgentConfig,
    file: Optional[Path] = None,
    topic: Optional[str] = None,
) -> Dict[str, str]:
    label = label.upper()
    if label not in LABELS:
        return {"status": "error", "error": f"unknown label: {label}"}

    if label in ("READ", "PLAN", "SUMMARIZE", "TODOS", "DEADLINES"):
        if file is None or not file.exists():
            # Try to pick one
            file = pick_active_document(cfg)
            if file is None:
                return {"status": "error", "error": "no input document found in workspace/in/"}
        if not in_sandbox(cfg, file):
            return {"status": "error", "error": f"file {file} not in sandbox"}
        if label == "READ":
            out, note = tool_read_aloud(cfg, file)
            return {"status": "ok", "tool": "read", "out": str(out), "overlay": ""}  # overlay not needed
        elif label == "PLAN":
            out = tool_plan(cfg, file)
            return {"status": "ok", "tool": "plan", "out": str(out)}
        elif label == "SUMMARIZE":
            out = tool_summarize(cfg, file)
        elif label == "TODOS":
            out = tool_todos(cfg, file)
        else:
            out = tool_deadlines(cfg, file)
        return {"status": "ok", "tool": label.lower(), "out": str(out)}

    if label == "HELP":
        out, overlay = tool_help(cfg)
        return {"status": "ok", "tool": "help", "out": str(out), "overlay": overlay}

    # MESSAGE (LLM draft + large-print overlay) or legacy EMAIL
    t = topic or (file.name if file else "an update")
    if label == "EMAIL":
        # Legacy support
        attachments = [file] if (file and file.exists()) else []
        out = tool_email(cfg, t, attachments)
        return {"status": "ok", "tool": "email", "out": str(out)}
    else:
        # MESSAGE
        out, overlay = tool_message(cfg, t, file if (file and file.exists()) else None)
        return {"status": "ok", "tool": "message", "out": str(out), "overlay": overlay}