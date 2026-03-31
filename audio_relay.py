#!/usr/bin/env python3
"""Local audio relay server for playing game sounds over SSH.

Run this on your local machine, then SSH with a reverse tunnel so the
remote game can stream WAV data back for local playback.

Usage:
    python3 audio_relay.py [--port 7700]

Protocol (per message):
    4 bytes: big-endian uint32 payload length
    1 byte:  command (0x01 = play, 0x02 = loop_start, 0x03 = loop_stop, 0x04 = close)
    For play/loop_start:
        1 byte:  name length
        N bytes: loop name (utf-8)
        4 bytes: volume as float32 big-endian
        remaining: WAV data
    For loop_stop:
        1 byte:  name length
        N bytes: loop name (utf-8)
"""

import socket
import struct
import threading
import wave
import io
import sys
import argparse

try:
    import pyaudio
except ImportError:
    print("pyaudio required: pip install pyaudio", file=sys.stderr)
    sys.exit(1)


CMD_PLAY = 0x01
CMD_LOOP_START = 0x02
CMD_LOOP_STOP = 0x03
CMD_CLOSE = 0x04


class LocalPlayer:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self._loops = {}
        self._lock = threading.Lock()

    def play(self, wav_data: bytes, volume: float = 1.0):
        t = threading.Thread(target=self._play_sync, args=(wav_data, volume), daemon=True)
        t.start()

    def _play_sync(self, wav_data: bytes, volume: float):
        try:
            wf = wave.open(io.BytesIO(wav_data), 'rb')
            stream = self.pa.open(
                format=self.pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                if volume != 1.0:
                    data = _apply_volume(data, volume)
                stream.write(data)
                data = wf.readframes(chunk)
            stream.stop_stream()
            stream.close()
            wf.close()
        except Exception as e:
            print(f"  play error: {e}", file=sys.stderr)

    def loop_start(self, name: str, wav_data: bytes, volume: float = 1.0):
        self.loop_stop(name)
        stop_event = threading.Event()
        self._loops[name] = stop_event
        t = threading.Thread(target=self._loop_run, args=(name, wav_data, volume, stop_event), daemon=True)
        t.start()

    def _loop_run(self, name: str, wav_data: bytes, volume: float, stop_event: threading.Event):
        try:
            wf = wave.open(io.BytesIO(wav_data), 'rb')
            fmt = self.pa.get_format_from_width(wf.getsampwidth())
            channels = wf.getnchannels()
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            wf.close()
            if volume != 1.0:
                raw = _apply_volume(raw, volume)

            stream = self.pa.open(format=fmt, channels=channels, rate=rate, output=True)
            chunk_size = 1024 * channels * 2
            while not stop_event.is_set():
                offset = 0
                while offset < len(raw) and not stop_event.is_set():
                    end = min(offset + chunk_size, len(raw))
                    stream.write(raw[offset:end])
                    offset = end
            stream.stop_stream()
            stream.close()
        except Exception:
            pass

    def loop_stop(self, name: str):
        ev = self._loops.pop(name, None)
        if ev:
            ev.set()

    def close(self):
        for ev in self._loops.values():
            ev.set()
        self._loops.clear()
        self.pa.terminate()


def _apply_volume(data: bytes, volume: float) -> bytes:
    import array
    samples = array.array('h', data)
    for i in range(len(samples)):
        samples[i] = int(samples[i] * volume)
    return samples.tobytes()


def _recv_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def handle_client(conn, player):
    try:
        while True:
            hdr = _recv_exact(conn, 4)
            if not hdr:
                break
            length = struct.unpack('>I', hdr)[0]
            payload = _recv_exact(conn, length)
            if not payload:
                break

            cmd = payload[0]

            if cmd == CMD_PLAY:
                name_len = payload[1]
                name = payload[2:2 + name_len].decode()
                vol = struct.unpack('>f', payload[2 + name_len:6 + name_len])[0]
                wav_data = payload[6 + name_len:]
                player.play(wav_data, vol)

            elif cmd == CMD_LOOP_START:
                name_len = payload[1]
                name = payload[2:2 + name_len].decode()
                vol = struct.unpack('>f', payload[2 + name_len:6 + name_len])[0]
                wav_data = payload[6 + name_len:]
                player.loop_start(name, wav_data, vol)

            elif cmd == CMD_LOOP_STOP:
                name_len = payload[1]
                name = payload[2:2 + name_len].decode()
                player.loop_stop(name)

            elif cmd == CMD_CLOSE:
                break

    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        player.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Audio relay for SSH game sessions")
    parser.add_argument("--port", type=int, default=7700)
    args = parser.parse_args()

    player = LocalPlayer()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(1)
    print(f"Audio relay listening on 127.0.0.1:{args.port}")

    try:
        while True:
            conn, addr = srv.accept()
            print(f"  connected: {addr}")
            t = threading.Thread(target=handle_client, args=(conn, LocalPlayer()), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\nRelay stopped.")
    finally:
        srv.close()
        player.close()


if __name__ == "__main__":
    main()
