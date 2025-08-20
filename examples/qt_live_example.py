#examples/qt_live_example.py
"""
Example: Minimal Qt application with live SSVEP prediction.
This shows how to integrate the LivePredictor with any Qt app.

Usage:
    # If you have LSL library installed:
    uv run --extra stream --extra ui python examples/qt_live_example.py

    # This will fail gracefully if no LSL stream is available
"""

import sys
from typing import Dict

try:
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
    from PySide6.QtCore import Qt
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    print("PySide6 not available. Install with: uv sync --extra ui")
    sys.exit(1)

try:
    from neurorelay.bridge.qt_live_bridge import create_live_predictor
    LSL_AVAILABLE = True
except Exception as e:
    LSL_AVAILABLE = False
    print(f"LSL not available: {e}")
    print("This is expected if you don't have the LSL library installed.")


class SSVEPDemo(QWidget):
    """Minimal demo showing live SSVEP predictions in Qt."""
    
    def __init__(self):
        super().__init__()
        self.predictor = None
        self.init_ui()
        
        if LSL_AVAILABLE:
            self.setup_predictor()
    
    def init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("NeuroRelay Live SSVEP Demo")
        self.setGeometry(100, 100, 400, 300)
        
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Status: Initializing...")
        layout.addWidget(self.status_label)
        
        # Current prediction
        self.prediction_label = QLabel("Prediction: --")
        self.prediction_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.prediction_label)
        
        # Confidence
        self.confidence_label = QLabel("Confidence: --")
        layout.addWidget(self.confidence_label)
        
        # Start/stop button
        self.toggle_button = QPushButton("Start Prediction")
        self.toggle_button.clicked.connect(self.toggle_prediction)
        layout.addWidget(self.toggle_button)
        
        # Log area
        self.log = QTextEdit()
        self.log.setMaximumHeight(150)
        layout.addWidget(self.log)
        
        self.setLayout(layout)
        
        if not LSL_AVAILABLE:
            self.toggle_button.setEnabled(False)
            self.log.append("LSL not available - demo mode only")
            self.status_label.setText("Status: LSL not available")
    
    def setup_predictor(self):
        """Set up the live predictor."""
        try:
            self.predictor = create_live_predictor(
                stream_type="EEG",
                frequencies=[8.57, 10.0, 12.0, 15.0],
                window_seconds=3.0,
                channels=["O1", "Oz", "O2"]  # Optional
            )
            
            # Connect signals
            self.predictor.prediction.connect(self.on_prediction)
            self.predictor.status_changed.connect(self.on_status_change)
            self.predictor.data_received.connect(self.on_data_received)
            
            self.log.append("LivePredictor created successfully")
            self.status_label.setText("Status: Ready")
            
        except Exception as e:
            self.log.append(f"Failed to create predictor: {e}")
            self.toggle_button.setEnabled(False)
    
    def toggle_prediction(self):
        """Start or stop live prediction."""
        if not self.predictor:
            return
        
        if self.predictor.running:
            self.predictor.stop()
            self.toggle_button.setText("Start Prediction")
        else:
            if self.predictor.start():
                self.toggle_button.setText("Stop Prediction")
            else:
                self.log.append("Failed to start prediction")
    
    def on_prediction(self, frequency: float, confidence: float, scores: Dict[float, float]):
        """Handle prediction updates."""
        self.prediction_label.setText(f"Prediction: {frequency:.1f} Hz")
        self.confidence_label.setText(f"Confidence: {confidence:.3f}")
        
        # Log detailed scores occasionally
        if confidence > 0.7:
            score_str = ", ".join(f"{f}Hz:{s:.3f}" for f, s in scores.items())
            self.log.append(f"High confidence: {frequency:.1f}Hz ({confidence:.3f}) | {score_str}")
    
    def on_status_change(self, message: str):
        """Handle status updates."""
        self.status_label.setText(f"Status: {message}")
        self.log.append(f"Status: {message}")
    
    def on_data_received(self, n_samples: int):
        """Handle data reception updates."""
        # Only log occasionally to avoid spam (~every 8 updates)
        if not hasattr(self, "_rx_cnt"):
            self._rx_cnt = 0
        self._rx_cnt = (self._rx_cnt + 1) % 8
        if self._rx_cnt == 0:
            self.log.append(f"Window size ~{n_samples} samples")
    
    def closeEvent(self, event):
        """Clean up when closing."""
        if self.predictor and self.predictor.running:
            self.predictor.stop()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    
    demo = SSVEPDemo()
    demo.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()