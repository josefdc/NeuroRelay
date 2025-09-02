#src/neurorelay/ui/ssvep_4buttons.py
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np

from PySide6.QtCore import Qt, QElapsedTimer, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPaintEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


@dataclass
class UiConfig:
    monitor_hz: float
    freqs_hz: List[float]
    window_sec: float
    dwell_sec: float
    tau: float
    flicker_mode: str = "sinusoidal"
    intensity: float = 0.85

    @staticmethod
    def from_json(path: Path) -> "UiConfig":
        cfg = json.loads(path.read_text())
        return UiConfig(
            monitor_hz=float(cfg.get("monitor_hz", 60.0)),
            freqs_hz=[float(x) for x in cfg.get("freqs_hz", [8.57, 10.0, 12.0, 15.0])],
            window_sec=float(cfg.get("window_sec", 3.0)),
            dwell_sec=float(cfg.get("dwell_sec", 1.2)),
            tau=float(cfg.get("tau", 0.65)),
            flicker_mode=str(cfg.get("flicker_mode", "sinusoidal")),
            intensity=float(cfg.get("ui_intensity", 0.85)),
        )


def apply_dark_theme(app) -> None:
    """Minimal dark Fusion palette; grayscale-only for stimuli, subtle accent for HUD."""
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(18, 18, 18))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.Base, QColor(24, 24, 24))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.Button, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(235, 235, 235))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(53, 132, 228))   # subtle accent (HUD only)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(pal)


def luminance_sinusoidal(t_sec: float, f_hz: float) -> float:
    return 0.5 + 0.5 * math.sin(2.0 * math.pi * f_hz * t_sec)


def luminance_square(t_sec: float, f_hz: float) -> float:
    s = math.sin(2.0 * math.pi * f_hz * t_sec)
    return 1.0 if s >= 0.0 else 0.0


class CenterPanel(QWidget):
    """A real center cell (not overlay) that keeps a small card centered within it."""
    def __init__(self, title="What do you want to do", subtitle="Objective", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("centerContainer")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("centerCard")
        self.card.setStyleSheet("""
            QFrame#centerCard { background:rgba(20,20,20,210); border:1px solid #333; border-radius:14px; }
            QLabel#centerTitle { color:#ECECEC; font-weight:600; }
            QLabel#centerSub   { color:#BDBDBD; }
        """)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(18, 14, 18, 14)
        card_lay.setSpacing(6)

        self.title = QLabel(title, self.card)
        self.title.setObjectName("centerTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub = QLabel(subtitle, self.card)
        self.sub.setObjectName("centerSub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_lay.addWidget(self.title)
        card_lay.addWidget(self.sub)
        lay.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, e):
        # Responsive typography based on available height of the center cell
        h = max(80, self.height())
        title_pt = max(18.0, min(28.0, h * 0.18))
        sub_pt   = max(12.0, min(18.0, h * 0.12))
        f1 = self.title.font(); f1.setPointSizeF(title_pt); self.title.setFont(f1)
        f2 = self.sub.font();   f2.setPointSizeF(sub_pt);   self.sub.setFont(f2)
        super().resizeEvent(e)


class FlickerTile(QWidget):
    def __init__(
        self,
        label: str,
        freq_hz: float,
        mode: str,
        intensity: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self.label = label
        self.freq_hz = float(freq_hz)
        self.mode = mode
        self.intensity = float(intensity)
        self.elapsed = QElapsedTimer()
        self.elapsed.start()
        
        # Optional: a lightweight timer that repaints just this tile.
        # Comment this in if you still don't see flicker with the window timer.
        # from PySide6.QtCore import QTimer, Qt
        # self._paint_timer = QTimer(self)
        # self._paint_timer.setTimerType(Qt.TimerType.PreciseTimer)
        # self._paint_timer.timeout.connect(self.update)
        # self._paint_timer.start(16)  # ~60 FPS; adjust if needed

        self.confidence: float = 0.0
        self.dwell: float = 0.0
        self.is_winner: bool = False

        self._font = QFont("Arial", 24, QFont.Weight.DemiBold)
        self._pen_border = QPen(QColor(40, 40, 40), 2.0)
        # Elegant rings: thin for non-winner, slightly thicker for winner
        self._pen_ring = QPen(QColor(0, 0, 0), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._pen_ring_high = QPen(QColor(0, 0, 0), 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._text_color = QColor(0, 0, 0)
        self._corner_radius = 16

    def minimumSizeHint(self) -> QSize:
        return QSize(260, 160)

    def sizeHint(self) -> QSize:
        return QSize(360, 220)

    def set_feedback(self, conf: float, dwell: float, is_winner: bool) -> None:
        self.confidence = max(0.0, min(1.0, conf))
        self.dwell = max(0.0, min(1.0, dwell))
        self.is_winner = is_winner

    def _luminance_now(self) -> float:
        """
        Return luminance in 0..1 with *constant mean ~0.5* and
        amplitude controlled by self.intensity in [0..1].
        """
        t = self.elapsed.elapsed() / 1000.0
        if self.mode == "square":
            # Map 0/1 to a symmetric square around 0.5 with amplitude=self.intensity*0.5
            base = 1.0 if math.sin(2.0 * math.pi * self.freq_hz * t) >= 0.0 else 0.0
            return 0.5 + (base - 0.5) * self.intensity
        # sinusoidal (preferred)
        return 0.5 + 0.5 * self.intensity * math.sin(2.0 * math.pi * self.freq_hz * t)

    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

        lum = self._luminance_now()
        value = max(0, min(255, int(lum * 255)))
        bg = QColor(value, value, value)

        # Rounded tile background
        r = self.rect().adjusted(1, 1, -1, -1)
        rr = self._corner_radius
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, rr, rr)

        # Minimal border
        p.setPen(self._pen_border)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, rr, rr)

        p.setFont(self._font)
        p.setPen(self._text_color if value > 128 else QColor(255, 255, 255))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.label)

        # Confidence underline: hairline under text, subtle and minimal
        underline_th = max(2, int(self.height() * 0.012))
        bar_w = int(self.width() * self.confidence)
        bar_rect = QRectF(r.x(), r.bottom() - underline_th, bar_w, underline_th)
        p.fillRect(bar_rect, QColor(0, 0, 0, 160) if value > 128 else QColor(255, 255, 255, 200))

        if self.dwell > 0.0:
            pad = 6
            arc_rect = r.adjusted(pad, pad, -pad, -pad)
            p.setPen(self._pen_ring_high if self.is_winner else self._pen_ring)
            start_angle = 90 * 16
            span_angle = -int(self.dwell * 360 * 16)
            p.drawArc(arc_rect, start_angle, span_angle)

        p.end()

    def resizeEvent(self, e):
        # Scale label responsively to tile height (capped)
        h = max(1, self.height())
        pt = max(18.0, min(48.0, h * 0.14))
        if abs(self._font.pointSizeF() - pt) > 0.5:
            self._font.setPointSizeF(pt)
        super().resizeEvent(e)


class NeuroRelayWindow(QMainWindow):
    LABELS = ("SUMMARIZE", "TODOS", "DEADLINES", "EMAIL")

    def __init__(
        self,
        cfg: UiConfig,
        config_path: Path,
        *,
        live: bool = False,
        lsl_type: str = "EEG",
        lsl_name: Optional[str] = None,
        lsl_timeout: float = 5.0,
        prediction_rate_hz: float = 4.0,
    ) -> None:
        super().__init__()
        title = "NeuroRelay — SSVEP 4-Option (Live)" if live else "NeuroRelay — SSVEP 4-Option (Phase 1)"
        self.setWindowTitle(title)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.cfg = cfg
        self.config_path = config_path
        self.state = "idle"
        self.is_paused = False
        self.live_enabled = bool(live)
        self.lsl_type = lsl_type
        self.lsl_name = lsl_name
        self.lsl_timeout = float(lsl_timeout)
        self.prediction_rate_hz = float(prediction_rate_hz)

        assert len(cfg.freqs_hz) == 4, "Expect 4 frequencies for 4 tiles"
        
        # --- 3×3 grid: corners = tiles, center = reserved gap for agent/LLM ---
        grid = QGridLayout()
        grid.setSpacing(12)  # small general spacing; center gap size handled separately
        self._grid = grid

        # Tiles
        self.tiles: List[FlickerTile] = []
        for i, label in enumerate(self.LABELS):
            tile = FlickerTile(label, cfg.freqs_hz[i], mode=cfg.flicker_mode, intensity=cfg.intensity)
            self.tiles.append(tile)

        # Place tiles in the four corners of a 3×3 grid
        grid.addWidget(self.tiles[0], 0, 0)  # SUMMARIZE (top-left)
        grid.addWidget(self.tiles[1], 0, 2)  # TODOS     (top-right)
        grid.addWidget(self.tiles[2], 2, 0)  # DEADLINES (bottom-left)
        grid.addWidget(self.tiles[3], 2, 2)  # EMAIL     (bottom-right)

        # Real center cell reserved for the agent placeholder (no overlay)
        self.center_panel = CenterPanel("What do you want to do", "Objective", self)
        grid.addWidget(self.center_panel, 1, 1)

        # Let outer cells expand; keep the center's size controlled by min width/height
        for r in (0, 2):
            grid.setRowStretch(r, 1)
        for c in (0, 2):
            grid.setColumnStretch(c, 1)
        grid.setRowStretch(1, 0)
        grid.setColumnStretch(1, 0)

        # Wrap grid so we can control margins independent of other widgets
        grid_wrap = QWidget()
        grid_wrap.setLayout(grid)
        self._grid_wrap = grid_wrap

        self.mode_label = QLabel(f"Mode: {self.state.upper()}")
        self.mode_label.setStyleSheet("font-weight:600;")
        self.hz_label = QLabel(
            f"Monitor (cfg): {cfg.monitor_hz:.2f} Hz | Flicker: {', '.join(str(f) for f in cfg.freqs_hz)} Hz"
        )
        self.cfg_label = QLabel(str(self.config_path))
        self.cfg_label.setStyleSheet("color:#666;")
        map_lines = [f"{lbl} → {freq:.2f} Hz" for lbl, freq in zip(self.LABELS, cfg.freqs_hz)]
        self.map_label = QLabel("Stimulus map: " + " | ".join(map_lines))
        self.map_label.setStyleSheet("color:#444;")

        self.btn_start = QPushButton("Start Evaluate")
        self.btn_start.clicked.connect(self._on_start)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self._on_pause)

        # Intensity (always visible, not part of HUD)
        self.lbl_intensity = QLabel("Intensity")
        self.lbl_intensity.setStyleSheet("color:#bbb;")
        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(25, 100)
        self.intensity_slider.setValue(int(cfg.intensity * 100))
        self.intensity_slider.valueChanged.connect(self._on_intensity)
        # Make the slider visually obvious
        self.intensity_slider.setMinimumWidth(320)
        self.intensity_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 6px; background:#3a3a3a; border-radius:3px; }
            QSlider::handle:horizontal { width:18px; background:#e6e6e6; border-radius:9px; margin:-6px 0; }
            QSlider::sub-page:horizontal { background:#e6e6e6; border-radius:3px; }
        """)

        # Agent Dock (placeholder) — future home for BrainBus→Agent results
        self.agent_dock = QFrame()
        self.agent_dock.setObjectName("agentDock")
        self.agent_dock.setStyleSheet("""
            QFrame#agentDock { background:#1e1e1e; border:1px solid #333; border-radius:10px; }
            QLabel#agentText { color:#bbb; }
        """)
        dock_layout = QHBoxLayout(self.agent_dock)
        dock_layout.setContentsMargins(10, 6, 10, 6)
        self.agent_label = QLabel("agent: waiting… (placeholder)")
        self.agent_label.setObjectName("agentText")
        dock_layout.addWidget(self.agent_label)

        # Live link status lamp + label
        self.link_dot = QFrame()
        self.link_dot.setFixedSize(14, 14)
        self.link_dot.setStyleSheet("background:#a33; border-radius:7px; border:1px solid #222;")
        self.link_label = QLabel("Live: disconnected")
        self.link_label.setStyleSheet("color:#bbb;")

        # Controls row 1: operator buttons (HUD), hidden by default
        ops = QHBoxLayout()
        ops.addWidget(self.btn_start)
        ops.addWidget(self.btn_pause)
        ops.addStretch()

        # Controls row 2: intensity (always visible) + agent dock on the right
        stim = QHBoxLayout()
        stim.addWidget(self.lbl_intensity)
        stim.addWidget(self.intensity_slider, 1)
        stim.addWidget(self.link_dot)
        stim.addWidget(self.link_label)
        stim.addStretch()
        stim.addWidget(self.agent_dock)

        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.mode_label)
        v.addWidget(self.hz_label)
        v.addWidget(grid_wrap, 1)     # make grid expand; other rows take minimal space
        v.addLayout(stim)             # visible always
        v.addLayout(ops)              # HUD row
        v.addWidget(self.map_label)
        v.addWidget(self.cfg_label)
        self.setCentralWidget(root)
        
        # Minimal by default (HUD hidden) — intensity row remains visible
        self._hud_visible = False
        for w in (self.mode_label, self.hz_label, self.map_label, self.cfg_label, self.btn_start, self.btn_pause):
            w.setVisible(self._hud_visible)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        # Aim for one update per display refresh (50/60/75 Hz etc.)
        interval_ms = max(1, int(round(1000.0 / max(1.0, self.cfg.monitor_hz))))
        self._timer.start(interval_ms)

        self._tick_clock = QElapsedTimer()
        self._tick_clock.start()
        self._winner_idx = 0
        self._winner_hold_ms = 0
        self.installEventFilter(self)

        # Live predictor state (Phase 3)
        self.live_predictor = None
        self._last_prediction_ts = 0.0
        self._display_conf = [0.0, 0.0, 0.0, 0.0]
        self._current_top_idx: Optional[int] = None
        self._stable_idx: Optional[int] = None
        self._stable_count = 0
        self._dwell_winner_idx: Optional[int] = None
        self._dwell_start_ts: Optional[float] = None
        self._last_commit_ts: float = 0.0
        self._commit_cooldown_sec: float = 0.75  # ~3 prediction ticks @ 4 Hz
        self._last_commit_ts: float = 0.0
        self._commit_cooldown_sec: float = 0.75  # ~3 prediction ticks @ 4 Hz

        # Apply initial gutters around/within the grid
        self._apply_gutters()

        # Start live mode automatically if requested
        if self.live_enabled:
            self._start_live_mode()

    def _simulate_feedback(self) -> Tuple[int, float, float]:
        # Real dt (ms) since last tick for dwell/conf ramps
        dt_ms = max(1, self._tick_clock.restart())
        if self.state == "evaluate" and not self.is_paused:
            self._winner_hold_ms += dt_ms
        else:
            self._winner_hold_ms = max(0, self._winner_hold_ms - 3 * dt_ms)

        dwell = min(1.0, self._winner_hold_ms / int(self.cfg.dwell_sec * 1000))
        conf = min(1.0, self._winner_hold_ms / int(0.7 * self.cfg.dwell_sec * 1000))
        return self._winner_idx, conf, dwell

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_1):
                self._set_winner(0)
            elif key in (Qt.Key.Key_Right, Qt.Key.Key_2):
                self._set_winner(1)
            elif key in (Qt.Key.Key_Down, Qt.Key.Key_3):
                self._set_winner(2)
            elif key in (Qt.Key.Key_4,):
                self._set_winner(3)
            elif key == Qt.Key.Key_Space:
                self._on_pause()
            elif key == Qt.Key.Key_Escape:
                self.close()
            elif key == Qt.Key.Key_H:
                self._toggle_hud()
            elif key in (Qt.Key.Key_F11,):
                self._toggle_fullscreen()
            elif key == Qt.Key.Key_A:
                self.agent_dock.setVisible(not self.agent_dock.isVisible())
            elif key == Qt.Key.Key_P:
                self.center_panel.setVisible(not self.center_panel.isVisible())
        return super().eventFilter(obj, event)

    def _set_winner(self, idx: int) -> None:
        if idx != self._winner_idx:
            self._winner_idx = idx
            self._winner_hold_ms = 0

    def _on_intensity(self, value: int) -> None:
        scale = float(value) / 100.0
        for t in self.tiles:
            t.intensity = scale

    def _on_start(self) -> None:
        self.state = "evaluate"
        self.mode_label.setText(f"Mode: {self.state.upper()}")
        self._winner_hold_ms = 0

    def _on_pause(self) -> None:
        self.is_paused = not self.is_paused
        self.btn_pause.setText("Resume" if self.is_paused else "Pause")

    def _toggle_hud(self) -> None:
        self._hud_visible = not self._hud_visible
        for w in (self.mode_label, self.hz_label, self.map_label, self.cfg_label, self.btn_start, self.btn_pause):
            w.setVisible(self._hud_visible)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_tick(self) -> None:
        now = time.monotonic()

        if self.live_enabled and self._last_prediction_ts > 0.0:
            # Update link lamp
            self._update_link_lamp(now)

            # Compute dwell progress continuously between prediction callbacks
            dwell_prog = 0.0
            if self._dwell_start_ts is not None and self.state == "evaluate" and not self.is_paused:
                dwell_prog = min(1.0, max(0.0, (now - self._dwell_start_ts) / max(1e-3, self.cfg.dwell_sec)))

            top_idx = self._current_top_idx if self._current_top_idx is not None else 0
            # Push feedback & repaint
            for i, tile in enumerate(self.tiles):
                tile.set_feedback(
                    self._display_conf[i],
                    dwell_prog if (self._dwell_winner_idx == i) else 0.0,
                    i == top_idx,
                )
                if not self.is_paused:
                    tile.update()
        else:
            # Phase 1 simulator path
            idx, conf, dwell = self._simulate_feedback()
            for i, tile in enumerate(self.tiles):
                tile.set_feedback(
                    conf if i == idx else max(0.0, conf - 0.3),
                    dwell if i == idx else 0.0,
                    i == idx,
                )
                if not self.is_paused:
                    tile.update()

    # --- Layout helpers ---
    def _apply_gutters(self) -> None:
        """
        Outer gutters + a fixed-size central gap cell.
        - Outer margins scale with window
        - Center row/col get explicit minimum sizes so the agent panel has a home
        """
        min_dim = max(1, min(self.width(), self.height()))
        outer = max(24, int(min_dim * 0.035))        # outer margin
        spacing = max(10, int(min_dim * 0.012))      # general inter-cell spacing
        center_gap = max(120, int(min_dim * 0.16))   # central cell size

        self._grid.setContentsMargins(outer, outer, outer, outer)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)

        # Reserve the middle row/column for the central gap (and our center_panel)
        self._grid.setRowMinimumHeight(1, center_gap)
        self._grid.setColumnMinimumWidth(1, center_gap)

    def resizeEvent(self, e):
        self._apply_gutters()
        return super().resizeEvent(e)

    # --- Live mode (Phase 3) ---
    def _start_live_mode(self) -> None:
        """Instantiate and start the LivePredictor (lazy imports to keep Phase 1 clean)."""
        # Load extended config keys from JSON (channels, bandpass, notch)
        try:
            raw_cfg = json.loads(self.config_path.read_text())
        except Exception:
            raw_cfg = {}
        channels = raw_cfg.get("channels", None)
        band = tuple(raw_cfg.get("bandpass_hz", [5, 40]))
        notch = raw_cfg.get("notch_hz", None)

        try:
            from ..bridge.qt_live_bridge import LivePredictor
            from ..stream.lsl_source import LSLConfig
            from ..signal.ssvep_detector import SSVEPConfig
        except Exception as e:
            self._status(f"Live init error: {e}. Install extras with: uv sync -E ui -E stream")
            return

        lsl_cfg = LSLConfig(
            stream_type=self.lsl_type,
            stream_name=self.lsl_name,
            timeout=self.lsl_timeout,
            buffer_seconds=self.cfg.window_sec + 2.0,
        )
        ssvep_cfg = SSVEPConfig(
            frequencies=self.cfg.freqs_hz,
            sample_rate=250.0,  # updated from LSL on connect
            window_seconds=self.cfg.window_sec,
            channels=channels,
            bandpass_freq=(float(band[0]), float(band[1])),
            notch_freq=float(notch) if (notch is not None) else None,
            harmonics=2,
            method="cca",
        )
        self.live_predictor = LivePredictor(lsl_cfg, ssvep_cfg)
        self.live_predictor.update_prediction_rate(self.prediction_rate_hz)
        self.live_predictor.prediction.connect(self._on_live_prediction)  # type: ignore
        self.live_predictor.status_changed.connect(self._status)  # type: ignore
        self.live_predictor.data_received.connect(lambda n: None)  # type: ignore

        if self.live_predictor.start():
            self._status("Live SSVEP mode active")
            self._on_start()  # enter evaluate state
        else:
            self._status("Failed to start live mode (LSL)")

    def _status(self, msg: str) -> None:
        try:
            self.statusBar().showMessage(msg, 3000)
        except Exception:
            pass
        self.link_label.setText(f"Live: {msg}")

    def _update_link_lamp(self, now: float) -> None:
        age = now - self._last_prediction_ts if self._last_prediction_ts > 0 else 1e9
        if age < 0.5:
            color = "#2ea043"   # green
            txt = "connected"
        elif age < 2.0:
            color = "#d29922"   # yellow
            txt = "delayed"
        else:
            color = "#a33"      # red
            txt = "no data"
        self.link_dot.setStyleSheet(f"background:{color}; border-radius:7px; border:1px solid #222;")
        # Keep human-readable text short; status bar shows details
        self.link_label.setText(f"Live: {txt}")

    def _on_live_prediction(self, frequency: float, confidence: float, scores: dict) -> None:
        """Handle live predictions: stability, dwell, commit."""
        now = time.monotonic()
        self._last_prediction_ts = now

        # Map scores to tile order (nearest frequency matching for robustness)
        tile_scores = []
        freqs = list(scores.keys())
        for f in self.cfg.freqs_hz:
            j = int(np.argmin([abs(f - g) for g in freqs]))
            tile_scores.append(float(scores[freqs[j]]))

        # Normalize to confidences (softmax over z-scores)
        vals = np.asarray(tile_scores, dtype=float)
        if np.std(vals) > 1e-6:
            z = (vals - np.mean(vals)) / max(1e-9, float(np.std(vals)))
            ex = np.exp(z - np.max(z))
            confs = ex / np.sum(ex)
        else:
            confs = np.ones_like(vals) / max(1, len(vals))

        self._display_conf = [float(c) for c in confs.tolist()]
        top_idx = int(np.argmax(confs))
        top_conf = float(confs[top_idx])
        second_conf = float(np.partition(confs, -2)[-2]) if len(confs) >= 2 else 0.0
        self._current_top_idx = top_idx

        # Stability (winner unchanged across last 3 predictions)
        if self._stable_idx == top_idx:
            self._stable_count += 1
        else:
            self._stable_idx = top_idx
            self._stable_count = 1

        stable_enough = self._stable_count >= 3  # ~0.75 s @ 4 Hz
        clear_margin = (top_conf - second_conf) >= 0.05
        threshold_ok = top_conf >= self.cfg.tau

        can_dwell = stable_enough and clear_margin and threshold_ok

        if self.state == "evaluate" and not self.is_paused and can_dwell:
            if self._dwell_winner_idx != top_idx:
                self._dwell_winner_idx = top_idx
                self._dwell_start_ts = now
            # Check commit (with cooldown to prevent immediate repeat commits)
            if (self._dwell_start_ts is not None
                and (now - self._dwell_start_ts) >= self.cfg.dwell_sec
                and (now - self._last_commit_ts) >= self._commit_cooldown_sec):
                self._commit_selection(top_idx, top_conf)
        else:
            # Reset dwell when evidence is insufficient or paused/idle
            self._dwell_start_ts = None
            self._dwell_winner_idx = None

    def _commit_selection(self, idx: int, conf: float) -> None:
        self._last_commit_ts = time.monotonic()
        label = self.LABELS[idx]
        self.agent_label.setText(f"agent: {label.lower()} • conf={conf:.2f} (Phase 3 commit)")
        self._status(f"Committed: {label} (conf={conf:.2f})")
        # Reset dwell for next selection
        self._dwell_start_ts = None
        self._dwell_winner_idx = None
        # Optionally return to idle; keep evaluate for repeated selections
        # self.state = "idle"

    def closeEvent(self, e):
        if self.live_predictor:
            try:
                self.live_predictor.stop()
            except Exception:
                pass
        return super().closeEvent(e)


def main(argv: List[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="NeuroRelay SSVEP 2×2 UI (Phase 1)")
    parser.add_argument("--config", default="config/default.json", help="Path to config JSON")
    parser.add_argument("--mode", choices=["sinusoidal", "square"], default="sinusoidal", help="Flicker mode")
    parser.add_argument("--auto-freqs", action="store_true", help="Use monitor_hz/[7,6,5,4] instead of config freqs")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen")
    # Phase 3 live flags
    parser.add_argument("--live", action="store_true", help="Enable live LSL detection")
    parser.add_argument("--lsl-type", default="EEG", help="LSL stream type (default: EEG)")
    parser.add_argument("--lsl-name", default=None, help="LSL stream name (optional)")
    parser.add_argument("--lsl-timeout", type=float, default=5.0, help="LSL discovery timeout (s)")
    parser.add_argument("--prediction-rate", type=float, default=4.0, help="Live prediction rate (Hz)")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    cfg = UiConfig.from_json(config_path)
    cfg.flicker_mode = args.mode
    if args.auto_freqs:
        mhz = max(1.0, cfg.monitor_hz)
        if 45.0 <= mhz <= 55.0:
            divisors = (6.0, 5.0, 4.0, 3.0)   # 50 Hz → 8.33, 10, 12.5, 16.67
        else:
            divisors = (7.0, 6.0, 5.0, 4.0)   # 60 Hz → 8.57, 10, 12, 15
        cfg.freqs_hz = [mhz / d for d in divisors]
        print(f"Auto frequencies for {mhz:.2f} Hz: {cfg.freqs_hz}")

    app = QApplication([])
    apply_dark_theme(app)
    win = NeuroRelayWindow(
        cfg,
        config_path=config_path,
        live=args.live,
        lsl_type=args.lsl_type,
        lsl_name=args.lsl_name,
        lsl_timeout=args.lsl_timeout,
        prediction_rate_hz=args.prediction_rate,
    )
    for t in win.tiles:
        t.mode = cfg.flicker_mode
    win.resize(1120, 760)
    win.showFullScreen() if args.fullscreen else win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
