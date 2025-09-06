# edf_to_lsl.py
import time, numpy as np, pyedflib
from pylsl import StreamInfo, StreamOutlet

EDF = "session.edf"
BLK_S = 1.0

f = pyedflib.EdfReader(EDF)
nch = f.signals_in_file
fs  = int(round(f.getSampleFrequency(0)))
ns  = min(f.getNSamples())  # por si difiere entre canales
labels = f.getSignalLabels()

info = StreamInfo('EDFRelay', 'EEG', nch, fs, 'float32', 'edf-relay')
out  = StreamOutlet(info, chunk_size=int(fs*BLK_S))

# Carga completa por canal una sola vez (más eficiente)
signals = [f.readSignal(c).astype('float32', copy=False) for c in range(nch)]
f.close()

step = int(fs * BLK_S)
for i in range(0, ns, step):
    end = min(ns, i + step)
    chunk = np.stack([sig[i:end] for sig in signals], axis=1)
    out.push_chunk(chunk.tolist())
    time.sleep(BLK_S)
