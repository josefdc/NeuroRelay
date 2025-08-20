#src/neurorelay/stream/lsl_source.py
"""LSL source for live EEG streaming with ring buffer."""

import threading
import time
from collections import deque
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import numpy as np

try:
    import pylsl as lsl
except ImportError:
    lsl = None


@dataclass
class LSLConfig:
    """Configuration for LSL stream connection."""
    stream_type: str = "EEG"
    stream_name: Optional[str] = None
    timeout: float = 5.0
    buffer_seconds: float = 10.0
    max_chunk_size: int = 1024


class RingBuffer:
    """Thread-safe ring buffer for EEG data."""
    
    def __init__(self, max_samples: int, n_channels: int):
        self.max_samples = max_samples
        self.n_channels = n_channels
        self.buffer = np.zeros((max_samples, n_channels), dtype=np.float32)
        self.timestamps = np.zeros(max_samples, dtype=np.float64)
        self.head = 0
        self.count = 0
        self.lock = threading.RLock()
    
    def append(self, data: np.ndarray, timestamps: np.ndarray):
        """Append new data to the ring buffer (vectorized)."""
        with self.lock:
            n = int(data.shape[0])
            if n == 0:
                return
            head = self.head
            maxn = self.max_samples
            remain = maxn - head
            if n <= remain:
                self.buffer[head:head + n] = data
                self.timestamps[head:head + n] = timestamps
            else:
                first = remain
                self.buffer[head:] = data[:first]
                self.timestamps[head:] = timestamps[:first]
                over = n - first
                self.buffer[:over] = data[first:first + over]
                self.timestamps[:over] = timestamps[first:first + over]
            self.head = (head + n) % maxn
            self.count = min(self.count + n, maxn)
    
    def get_latest(self, n_samples: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get the latest n_samples from the buffer."""
        with self.lock:
            if self.count == 0:
                return None, None
            k = int(min(n_samples, self.count))
            start = (self.head - k) % self.max_samples
            if start + k <= self.max_samples:
                return (self.buffer[start:start + k].copy(),
                        self.timestamps[start:start + k].copy())
            else:
                first = self.max_samples - start
                data = np.vstack((self.buffer[start:], self.buffer[:k - first]))
                ts = np.hstack((self.timestamps[start:], self.timestamps[:k - first]))
                return data, ts
    
    def get_latest_seconds(self, duration: float, sample_rate: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get the latest duration seconds of data."""
        n_samples = int(duration * sample_rate)
        return self.get_latest(n_samples)


class LSLSource:
    """LSL stream source with background thread and ring buffer."""
    
    def __init__(self, config: LSLConfig):
        if lsl is None:
            raise ImportError("pylsl not available. Install with: uv sync -E stream")
        
        self.config = config
        self.inlet: Optional[lsl.StreamInlet] = None
        self.info: Optional[lsl.StreamInfo] = None
        self.buffer: Optional[RingBuffer] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.sample_rate: Optional[float] = None
        self.n_channels: Optional[int] = None
        self.channel_names: List[str] = []
    
    def connect(self) -> bool:
        """Connect to LSL stream."""
        print(f"Looking for LSL streams of type '{self.config.stream_type}'...")
        
        # Find streams - use resolve_streams for newer pylsl versions
        try:
            streams = lsl.resolve_streams(wait_time=self.config.timeout)
            # Filter by type
            streams = [s for s in streams if s.type() == self.config.stream_type]
        except (AttributeError, TypeError):
            # Fallback for older pylsl versions
            try:
                streams = lsl.resolve_byprop('type', self.config.stream_type, timeout=self.config.timeout)
            except AttributeError:
                # Last fallback
                streams = []
        
        if not streams:
            print(f"No LSL streams found for type '{self.config.stream_type}'")
            return False
        
        # Pick first stream (or by name if specified)
        info = streams[0]
        if self.config.stream_name:
            for stream_info in streams:
                if stream_info.name() == self.config.stream_name:
                    info = stream_info
                    break
            else:
                print(f"Stream '{self.config.stream_name}' not found, using first available")
        
        # Create inlet
        self.inlet = lsl.StreamInlet(info, max_chunklen=self.config.max_chunk_size)
        self.info = info
        
        # Get stream info
        self.sample_rate = info.nominal_srate()
        self.n_channels = info.channel_count()
        
        # Get channel names
        self.channel_names = []
        channels = info.desc().child("channels")
        if not channels.empty():
            ch = channels.child("channel")
            for _ in range(self.n_channels):
                if not ch.empty():
                    label = ch.child_value("label")
                    self.channel_names.append(label if label else f"Ch{len(self.channel_names)}")
                    ch = ch.next_sibling()
                else:
                    self.channel_names.append(f"Ch{len(self.channel_names)}")
        else:
            self.channel_names = [f"Ch{i}" for i in range(self.n_channels)]
        
        # Initialize ring buffer
        max_samples = int(self.config.buffer_seconds * self.sample_rate)
        self.buffer = RingBuffer(max_samples, self.n_channels)
        
        print(f"Connected to LSL stream: {info.name()}")
        print(f"  Sample rate: {self.sample_rate} Hz")
        print(f"  Channels: {self.n_channels} ({', '.join(self.channel_names[:5])}{'...' if len(self.channel_names) > 5 else ''})")
        
        return True
    
    def start(self) -> bool:
        """Start background acquisition thread."""
        if not self.inlet:
            return False
        if self.running:
            return True
        
        self.running = True
        self.thread = threading.Thread(target=self._acquisition_loop, daemon=True)
        self.thread.start()
        print("LSL acquisition started")
        return True
    
    def stop(self):
        """Stop background acquisition."""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1.0)
            print("LSL acquisition stopped")
    
    def _acquisition_loop(self):
        """Background thread for data acquisition."""
        if not self.inlet or not self.buffer:
            return
        
        while self.running:
            try:
                # Pull chunk from LSL
                data, timestamps = self.inlet.pull_chunk(timeout=0.1, max_samples=256)
                
                if data:
                    data_array = np.array(data, dtype=np.float32)
                    ts_array = np.array(timestamps, dtype=np.float64)
                    self.buffer.append(data_array, ts_array)
                
            except Exception as e:
                print(f"LSL acquisition error: {e}")
                self.running = False
                break
    
    def get_latest_data(self, duration: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[Dict[str, Any]]]:
        """Get latest data from buffer."""
        if not self.buffer or not self.sample_rate:
            return None, None, None
        
        data, timestamps = self.buffer.get_latest_seconds(duration, self.sample_rate)
        
        if data is None:
            return None, None, None
        
        metadata = {
            'sample_rate': self.sample_rate,
            'channel_names': self.channel_names,
            'duration': duration,
            'n_samples': len(data)
        }
        
        return data, timestamps, metadata
    
    def is_connected(self) -> bool:
        """Check if connected and running."""
        return self.running and self.inlet is not None and self.buffer is not None
    
    def get_info(self) -> Dict[str, Any]:
        """Get stream information."""
        if not self.info or not self.sample_rate:
            return {}
        
        return {
            'name': self.info.name(),
            'type': self.info.type(),
            'sample_rate': self.sample_rate,
            'n_channels': self.n_channels,
            'channel_names': self.channel_names
        }