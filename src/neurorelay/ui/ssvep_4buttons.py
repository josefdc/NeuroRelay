#src/neurorelay/ui/ssvep_4buttons.py
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import Qt, QElapsedTimer, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
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


def luminance_sinusoidal(t_sec: float, f_hz: float) -> float:
    return 0.5 + 0.5 * math.sin(2.0 * math.pi * f_hz * t_sec)


def luminance_square(t_sec: float, f_hz: float) -> float:
    s = math.sin(2.0 * math.pi * f_hz * t_sec)
    return 1.0 if s >= 0.0 else 0.0


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

        self.confidence: float = 0.0
        self.dwell: float = 0.0
        self.is_winner: bool = False

        self._font = QFont("Arial", 20, QFont.Weight.DemiBold)
        self._pen_border = QPen(QColor(30, 30, 30), 2.0)
        self._pen_ring = QPen(QColor(0, 0, 0), 6.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._pen_ring_high = QPen(QColor(0, 0, 0), 10.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._text_color = QColor(0, 0, 0)

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

        p.fillRect(self.rect(), bg)

        p.setPen(self._pen_border)
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))

        p.setFont(self._font)
        p.setPen(self._text_color if value > 128 else QColor(255, 255, 255))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.label)

        bar_h = max(6, int(self.height() * 0.04))
        bar_w = int(self.width() * self.confidence)
        bar_rect = QRectF(0, self.height() - bar_h, bar_w, bar_h)
        p.fillRect(bar_rect, QColor(0, 0, 0, 180))

        if self.dwell > 0.0:
            pad = 6
            arc_rect = self.rect().adjusted(pad, pad, -pad, -pad)
            p.setPen(self._pen_ring_high if self.is_winner else self._pen_ring)
            start_angle = 90 * 16
            span_angle = -int(self.dwell * 360 * 16)
            p.drawArc(arc_rect, start_angle, span_angle)

        p.end()


class NeuroRelayWindow(QMainWindow):
    LABELS = ("SUMMARIZE", "TODOS", "DEADLINES", "EMAIL")

    def __init__(self, cfg: UiConfig, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("NeuroRelay — SSVEP 4-Option (Phase 1)")
        self.cfg = cfg
        self.config_path = config_path
        self.state = "idle"
        self.is_paused = False

        assert len(cfg.freqs_hz) == 4, "Expect 4 frequencies for 4 tiles"
        self.tiles: List[FlickerTile] = []

        grid = QGridLayout()
        grid.setSpacing(12)
        for i, label in enumerate(self.LABELS):
            tile = FlickerTile(label, cfg.freqs_hz[i], mode=cfg.flicker_mode, intensity=cfg.intensity)
            self.tiles.append(tile)
            grid.addWidget(tile, i // 2, i % 2)

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

        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(25, 100)
        self.intensity_slider.setValue(int(cfg.intensity * 100))
        self.intensity_slider.valueChanged.connect(self._on_intensity)

        controls = QHBoxLayout()
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_pause)
        controls.addWidget(QLabel("Intensity"))
        controls.addWidget(self.intensity_slider)

        root = QWidget()
        v = QVBoxLayout(root)
        v.addWidget(self.mode_label)
        v.addWidget(self.hz_label)
        v.addLayout(grid)
        v.addLayout(controls)
        v.addWidget(self.map_label)
        v.addWidget(self.cfg_label)
        self.setCentralWidget(root)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        # Aim for one update per display refresh (50/60/75 Hz etc.)
        interval_ms = max(1, int(round(1000.0 / max(1.0, self.cfg.monitor_hz))))
        self._timer.start(interval_ms)

        self._sim_elapsed = QElapsedTimer()
        self._sim_elapsed.start()
        self._winner_idx = 0
        self._winner_hold_ms = 0
        self.installEventFilter(self)

    def _simulate_feedback(self) -> Tuple[int, float, float]:
        dt_ms = 16
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

    def _on_tick(self) -> None:
        if not self.is_paused:
            self.update()
        idx, conf, dwell = self._simulate_feedback()
        for i, t in enumerate(self.tiles):
            t.set_feedback(conf if i == idx else max(0.0, conf - 0.3), dwell if i == idx else 0.0, i == idx)


def main(argv: List[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="NeuroRelay SSVEP 2×2 UI (Phase 1)")
    parser.add_argument("--config", default="config/default.json", help="Path to config JSON")
    parser.add_argument("--mode", choices=["sinusoidal", "square"], default="sinusoidal", help="Flicker mode")
    parser.add_argument("--auto-freqs", action="store_true", help="Use monitor_hz/[7,6,5,4] instead of config freqs")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    cfg = UiConfig.from_json(config_path)
    cfg.flicker_mode = args.mode
    if args.auto_freqs:
        mhz = max(1.0, cfg.monitor_hz)
        cfg.freqs_hz = [mhz / d for d in (7.0, 6.0, 5.0, 4.0)]
        print(f"Auto frequencies for {mhz} Hz: {cfg.freqs_hz}")

    app = QApplication([])
    win = NeuroRelayWindow(cfg, config_path=config_path)
    for t in win.tiles:
        t.mode = cfg.flicker_mode
    win.resize(960, 720)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
