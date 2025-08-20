#src/neurorelay/bridge/qt_live_bridge.py
"""Qt bridge for live SSVEP predictions."""

from typing import List, Dict, Optional, Any

try:
    from PySide6.QtCore import QObject, Signal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    # Dummy classes for type hints
    class QObject:
        pass
    class Signal:
        def __init__(self, *args):
            pass
        def emit(self, *args):
            pass

from ..stream.lsl_source import LSLSource, LSLConfig
from ..signal.ssvep_detector import SSVEPDetector, SSVEPConfig


class LivePredictor(QObject):
    """Qt-based live SSVEP predictor with signals."""
    
    # Qt signals
    prediction = Signal(float, float, dict)  # (frequency, confidence, scores)
    status_changed = Signal(str)  # Status message
    data_received = Signal(int)  # Number of samples received
    
    def __init__(self, lsl_config: LSLConfig, ssvep_config: SSVEPConfig):
        if not QT_AVAILABLE:
            raise ImportError("PySide6 not available. Install with: uv sync -E ui")
        
        super().__init__()
        self.lsl_config = lsl_config
        self.ssvep_config = ssvep_config
        
        self.lsl_source = LSLSource(lsl_config)
        self.detector = SSVEPDetector(ssvep_config)
        
        # Prediction timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._predict)
        self.prediction_interval_ms = 250  # 4 Hz prediction rate
        
        self.running = False
    
    def start(self) -> bool:
        """Start live prediction."""
        if self.running:
            return True
        
        # Connect to LSL
        if not self.lsl_source.connect():
            self.status_changed.emit("Failed to connect to LSL stream")
            return False
        
        # Update detector sample rate from LSL info
        if self.lsl_source.sample_rate:
            self.detector.update_config(sample_rate=self.lsl_source.sample_rate)
        
        # Start LSL acquisition
        if not self.lsl_source.start():
            self.status_changed.emit("Failed to start LSL acquisition")
            return False
        
        # Start prediction timer
        self.timer.start(self.prediction_interval_ms)
        self.running = True
        self.status_changed.emit("Live prediction started")
        return True
    
    def stop(self):
        """Stop live prediction."""
        if not self.running:
            return
        
        self.timer.stop()
        self.lsl_source.stop()
        self.running = False
        self.status_changed.emit("Live prediction stopped")
    
    def _predict(self) -> None:
        """Make a prediction and emit results."""
        if not self.running:
            return
        
        try:
            # Get recent data from LSL source
            data, timestamps, info = self.lsl_source.get_latest_data(self.ssvep_config.window_seconds)
            
            min_needed = max(10, self.detector.min_padlen() + 8)  # small safety margin
            if data is None or data.shape[0] < min_needed:
                return
            
            # Detect SSVEP and emit results
            best_freq, confidence, scores = self.detector.detect(data)
            
            # Emit prediction signal
            self.prediction.emit(best_freq, confidence, scores)
            
            # Emit data received signal
            self.data_received.emit(data.shape[0])
            
        except Exception as e:
            self.status_changed.emit(f"Prediction error: {str(e)}")
            print(f"LivePredictor prediction error: {e}")
    
    def update_frequencies(self, frequencies: List[float]):
        """Update target frequencies."""
        self.detector.update_config(frequencies=frequencies)
        self.ssvep_config.frequencies = frequencies
    
    def update_prediction_rate(self, rate_hz: float):
        """Update prediction rate (Hz)."""
        if rate_hz <= 0:
            self.status_changed.emit("Invalid prediction rate (must be > 0)")
            return
        self.prediction_interval_ms = max(50, int(1000 / rate_hz))
        self.timer.setInterval(self.prediction_interval_ms)
        if not self.running:
            return
        # Timer automatically uses the new interval on next timeout
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information."""
        status = {
            'running': self.running,
            'lsl_connected': self.lsl_source.is_connected() if self.lsl_source else False,
            'prediction_rate_hz': 1000 / self.prediction_interval_ms if self.prediction_interval_ms > 0 else 0,
            'frequencies': self.ssvep_config.frequencies,
            'window_seconds': self.ssvep_config.window_seconds
        }
        
        if self.lsl_source and self.lsl_source.is_connected():
            status.update(self.lsl_source.get_info())
        
        return status


def create_live_predictor(
    stream_type: str = "EEG",
    frequencies: Optional[List[float]] = None,
    window_seconds: float = 3.0,
    channels: Optional[List[str]] = None,
    bandpass: tuple = (5.0, 40.0),
    notch: Optional[float] = None
) -> LivePredictor:
    """Convenience function to create a LivePredictor with common settings."""
    
    lsl_config = LSLConfig(
        stream_type=stream_type,
        timeout=5.0,
        buffer_seconds=10.0
    )
    
    ssvep_config = SSVEPConfig(
        frequencies=frequencies or [8.57, 10.0, 12.0, 15.0],
        sample_rate=250.0,  # Will be updated from LSL
        window_seconds=window_seconds,
        channels=channels,
        bandpass_freq=bandpass,
        notch_freq=notch,
        harmonics=2,
        method="cca"
    )
    
    return LivePredictor(lsl_config, ssvep_config)