import socket, time, argparse
import numpy as np
from pylsl import StreamInfo, StreamOutlet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["client","server"], default="client")
    ap.add_argument("--host", default="169.254.189.77")  # IP CURRY si client
    ap.add_argument("--port", type=int, default=4000)
    ap.add_argument("--fs", type=int, default=1000)
    ap.add_argument("--nch", type=int, default=32)
    ap.add_argument("--blk", type=float, default=1.0)
    ap.add_argument("--name", default="NeuroscanEEG")
    args = ap.parse_args()

    samples = int(round(args.fs*args.blk))
    bytes_blk = samples*args.nch*4  # float32

    info = StreamInfo(args.name, 'EEG', args.nch, args.fs, 'float32', 'neurorelay-bridge')
    outlet = StreamOutlet(info, chunk_size=samples, max_buffered=360)

    buf = bytearray()
    if args.mode == "client":
        s = socket.create_connection((args.host, args.port), timeout=5)
        s.settimeout(0.1)
        print(f"[TCP] Conectado a {args.host}:{args.port}")
        while True:
            try:
                chunk = s.recv(65536)
                if not chunk:
                    time.sleep(0.005); continue
                buf.extend(chunk)
                while len(buf) >= bytes_blk:
                    raw = bytes(buf[:bytes_blk]); del buf[:bytes_blk]
                    x = np.frombuffer(raw, dtype=np.float32).reshape(samples, args.nch)
                    outlet.push_chunk(x)
            except socket.timeout:
                continue
    else:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", args.port)); srv.listen(1)
        print(f"[TCP] Esperando cliente en 0.0.0.0:{args.port} ...")
        conn, addr = srv.accept(); conn.settimeout(0.1)
        print(f"[TCP] Cliente conectado: {addr}")
        while True:
            try:
                chunk = conn.recv(65536)
                if not chunk:
                    time.sleep(0.005); continue
                buf.extend(chunk)
                while len(buf) >= bytes_blk:
                    raw = bytes(buf[:bytes_blk]); del buf[:bytes_blk]
                    x = np.frombuffer(raw, dtype=np.float32).reshape(samples, args.nch)
                    outlet.push_chunk(x)
            except socket.timeout:
                continue

if __name__ == "__main__":
    main()
