# src/neurorelay/bus/brainbus.py
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal, QProcess


class AgentProcess(QObject):
    """Qt wrapper to run the local agent as a subprocess and exchange JSONL messages."""
    message = Signal(dict)          # parsed JSON from agent stdout
    error = Signal(str)
    started = Signal()

    def __init__(self, parent: Optional[QObject] = None, cwd: Optional[Path] = None):
        super().__init__(parent)
        self.proc = QProcess(self)
        # Keep stdout (JSON lines) and stderr (logs) separated for clean parsing
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self._on_read)
        self.proc.readyReadStandardError.connect(self._on_read_stderr)
        self.proc.errorOccurred.connect(self._on_error)
        if cwd:
            self.proc.setWorkingDirectory(str(cwd))
        self._buf = b""

    def start(self) -> None:
        # Prefer `python -m neurorelay.agent.run_agent` for reliability inside `uv run`
        program = sys.executable
        args = ["-m", "neurorelay.agent.run_agent"]
        self.proc.start(program, args)
        if not self.proc.waitForStarted(3000):
            self.error.emit("Failed to start neurorelay-agent")
        else:
            self.started.emit()

    def is_running(self) -> bool:
        return self.proc.state() == QProcess.ProcessState.Running

    def stop(self) -> None:
        try:
            self.proc.closeWriteChannel()
            self.proc.terminate()
            self.proc.waitForFinished(1000)
        except Exception:
            pass

    def send(self, payload: Dict[str, Any]) -> None:
        if not self.is_running():
            self.error.emit("Agent not running")
            return
        line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.proc.write(line)
        # Reduce buffering risk
        self.proc.waitForBytesWritten(50)

    # --- signals ---
    def _on_read(self) -> None:
        self._buf += self.proc.readAllStandardOutput().data()
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
                if isinstance(obj, dict):
                    self.message.emit(obj)
            except Exception:
                # pass through agent logs as errors
                self.error.emit(text)

    def _on_read_stderr(self) -> None:
        byte_array = self.proc.readAllStandardError()
        if byte_array:
            # Forward stderr text to error signal (no JSON parsing)
            try:
                text = str(byte_array.data(), "utf-8", errors="replace").strip()
                if text:
                    self.error.emit(text)
            except Exception:
                pass

    def _on_error(self, e) -> None:
        self.error.emit(f"Agent process error: {e}")