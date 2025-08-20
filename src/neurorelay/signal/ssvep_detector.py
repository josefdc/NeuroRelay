#src/neurorelay/signal/ssvep_detector.py
"""SSVEP detector using Canonical Correlation Analysis (CCA)."""

import numpy as np
from typing import List, Dict, Tuple, Optional, Literal
from dataclasses import dataclass
from scipy.signal import butter, filtfilt, iirnotch
from scipy.stats import zscore


@dataclass
class SSVEPConfig:
    """Configuration for SSVEP detection."""
    frequencies: List[float]  # Target frequencies (Hz)
    sample_rate: float
    window_seconds: float = 3.0
    channels: Optional[List[str]] = None  # If None, use all available
    bandpass_freq: Tuple[float, float] = (5.0, 40.0)  # Hz
    notch_freq: Optional[float] = None  # Hz (50 or 60)
    harmonics: int = 2  # Include up to 2nd harmonic
    method: Literal["cca", "power"] = "cca"


class SSVEPDetector:
    """SSVEP detector using CCA with reference signals."""
    
    def __init__(self, config: SSVEPConfig):
        self.config = config
        self.references = {}
        self._prepare_references()
        
        # Prepare filters
        self.bandpass_filter = None
        self.notch_filter = None
        self._prepare_filters()
    
    def _prepare_references(self):
        """Pre-compute reference signals for each target frequency."""
        self.references = {}
        
        for freq in self.config.frequencies:
            # Create time vector
            n_samples = int(self.config.window_seconds * self.config.sample_rate)
            t = np.linspace(0, self.config.window_seconds, n_samples, endpoint=False)
            
            # Generate sine/cosine references for fundamental + harmonics
            refs = []
            for h in range(1, self.config.harmonics + 1):
                refs.append(np.sin(2 * np.pi * h * freq * t))
                refs.append(np.cos(2 * np.pi * h * freq * t))
            
            self.references[freq] = np.array(refs).T  # Shape: (n_samples, n_refs)
    
    def _prepare_filters(self) -> None:
        """Prepare bandpass and notch filters for preprocessing."""
        nyquist = self.config.sample_rate / 2.0
        
        # Bandpass filter
        if self.config.bandpass_freq:
            low, high = self.config.bandpass_freq
            if low >= nyquist or high >= nyquist:
                raise ValueError(f"Bandpass frequencies {self.config.bandpass_freq} exceed Nyquist frequency {nyquist}")
            b, a = butter(4, [low / nyquist, high / nyquist], btype='band')
            self.bandpass_filter = (b, a)
        
        # Notch filter
        if self.config.notch_freq:
            if self.config.notch_freq >= nyquist:
                raise ValueError(f"Notch frequency {self.config.notch_freq} exceeds Nyquist frequency {nyquist}")
            b, a = iirnotch(self.config.notch_freq, Q=30, fs=self.config.sample_rate)
            self.notch_filter = (b, a)
    
    def min_padlen(self) -> int:
        """Calculate minimum samples needed for filtfilt operations to avoid padding errors."""
        lengths = []
        if self.bandpass_filter is not None:
            b, a = self.bandpass_filter
            lengths.append(3 * (max(len(a), len(b)) - 1))
        if self.notch_filter is not None:
            b, a = self.notch_filter
            lengths.append(3 * (max(len(a), len(b)) - 1))
        return max(lengths) if lengths else 0
    
    def preprocess(self, data: np.ndarray) -> np.ndarray:
        """Apply bandpass and notch filtering."""
        if data.size == 0:
            return data
        
        # Apply filters along time axis (axis=0)
        filtered = data.copy()
        
        # Bandpass
        if self.bandpass_filter is not None:
            b, a = self.bandpass_filter
            filtered = filtfilt(b, a, filtered, axis=0)
        
        # Notch
        if self.notch_filter is not None:
            b, a = self.notch_filter
            filtered = filtfilt(b, a, filtered, axis=0)
        
        return filtered
    
    def compute_cca(self, data: np.ndarray, reference: np.ndarray) -> float:
        """Compute CCA between data and reference."""
        if data.shape[0] != reference.shape[0]:
            return 0.0
        
        # Center the data
        data_centered = data - np.mean(data, axis=0, keepdims=True)
        ref_centered = reference - np.mean(reference, axis=0, keepdims=True)
        
        # Compute covariance matrices
        try:
            n = data_centered.shape[0]
            eps = 1e-6
            Cxx = (data_centered.T @ data_centered) / (n - 1) + eps * np.eye(data_centered.shape[1])
            Cyy = (ref_centered.T @ ref_centered) / (n - 1) + eps * np.eye(ref_centered.shape[1])
            Cxy = (data_centered.T @ ref_centered) / (n - 1)
            Cxx_inv = np.linalg.pinv(Cxx)
            Cyy_inv = np.linalg.pinv(Cyy)
            M = Cxx_inv @ Cxy @ Cyy_inv @ Cxy.T
            # Symmetrize for numerical stability
            M = 0.5 * (M + M.T)
            eigvals = np.linalg.eigvalsh(M)
            rho2 = float(np.clip(np.max(eigvals).real, 0.0, 1.0))
            return float(np.sqrt(rho2))
        except (np.linalg.LinAlgError, ValueError):
            return 0.0
    
    def compute_power_spectrum(self, data: np.ndarray, freq: float) -> float:
        """Simple power spectrum approach at target frequency."""
        if data.size == 0:
            return 0.0
        
        # FFT approach
        fft_data = np.fft.rfft(data, axis=0)
        freqs = np.fft.rfftfreq(data.shape[0], 1/self.config.sample_rate)
        
        # Find closest frequency bin
        freq_idx = np.argmin(np.abs(freqs - freq))
        
        # Average power across channels at target frequency
        power = np.mean(np.abs(fft_data[freq_idx, :]) ** 2)
        return float(power)
    
    def detect(self, data: np.ndarray, channel_names: Optional[List[str]] = None) -> Tuple[float, float, Dict[float, float]]:
        """
        Detect SSVEP frequency from EEG data.
        
        Args:
            data: EEG data (n_samples, n_channels)
            channel_names: Optional channel names
            
        Returns:
            (predicted_frequency, confidence, scores_dict)
        """
        if data.size == 0 or len(self.config.frequencies) == 0:
            return 0.0, 0.0, {}
        
        # Select channels if specified
        if self.config.channels and channel_names:
            channel_indices = []
            for ch_name in self.config.channels:
                if ch_name in channel_names:
                    channel_indices.append(channel_names.index(ch_name))
            
            if channel_indices:
                data = data[:, channel_indices]
            else:
                # Optional: warn once if no requested channels are found
                # For now, silently fall back to using all channels
                pass
        
        # Preprocess
        data_filtered = self.preprocess(data)
        
        # Compute scores for each frequency
        scores = {}
        
        for freq in self.config.frequencies:
            if self.config.method == "cca" and freq in self.references:
                reference = self.references[freq]
                # Trim reference to match data length
                min_len = min(data_filtered.shape[0], reference.shape[0])
                score = self.compute_cca(data_filtered[:min_len], reference[:min_len])
            else:
                # Fallback to power spectrum
                score = self.compute_power_spectrum(data_filtered, freq)
            
            scores[freq] = score
        
        if not scores:
            return 0.0, 0.0, {}
        
        # Find best frequency
        best_freq = max(scores.keys(), key=lambda f: scores[f])
        
        # Compute confidence (softmax of z-scored values)
        score_values = np.array(list(scores.values()))
        if np.std(score_values) > 1e-6:
            z_scores = zscore(score_values)
            confidences = np.exp(z_scores) / np.sum(np.exp(z_scores))
            best_idx = list(scores.keys()).index(best_freq)
            confidence = float(confidences[best_idx])
        else:
            confidence = 1.0 / len(scores)  # Uniform if all scores equal
        
        return best_freq, confidence, scores
    
    def update_config(self, **kwargs):
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # Regenerate references if frequencies changed
        if any(k in kwargs for k in ('frequencies', 'window_seconds', 'sample_rate', 'harmonics')):
            self._prepare_references()
        
        # Regenerate filters if needed
        if any(k in kwargs for k in ['sample_rate', 'bandpass', 'notch']):
            self._prepare_filters()


def generate_reference_signals(frequencies: List[float], sample_rate: float, duration: float, harmonics: int = 2) -> Dict[float, np.ndarray]:
    """Generate reference signals for SSVEP detection."""
    references = {}
    n_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    
    for freq in frequencies:
        refs = []
        for h in range(1, harmonics + 1):
            refs.append(np.sin(2 * np.pi * h * freq * t))
            refs.append(np.cos(2 * np.pi * h * freq * t))
        references[freq] = np.array(refs).T
    
    return references