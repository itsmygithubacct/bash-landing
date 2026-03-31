"""WAV file player with threading and looping support.

Supports local playback via PyAudio or remote relay via AUDIO_RELAY env var.
Set AUDIO_RELAY=host:port to stream sound over TCP (for SSH sessions).
"""

import wave
import os
import sys
import logging
import struct
import socket
from typing import Optional
import threading
import subprocess
import ctypes

logger = logging.getLogger(__name__)

# Relay protocol commands
_CMD_PLAY = 0x01
_CMD_LOOP_START = 0x02
_CMD_LOOP_STOP = 0x03
_CMD_CLOSE = 0x04


def _suppress_alsa_errors():
    """Suppress ALSA error messages via C-level error handler."""
    try:
        asound = ctypes.cdll.LoadLibrary('libasound.so.2')
        c_error_handler = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_char_p)
        @c_error_handler
        def _noop_handler(filename, line, function, err, fmt):
            pass
        _suppress_alsa_errors._handler = _noop_handler
        asound.snd_lib_error_set_handler(_noop_handler)
    except Exception:
        pass


_suppress_alsa_errors()


def _ensure_pyaudio():
    try:
        import pyaudio
        return pyaudio
    except ImportError:
        try:
            subprocess.run(
                ['uv', 'pip', 'install', 'pyaudio'],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            import pyaudio
            return pyaudio
        except Exception:
            return None


pyaudio = _ensure_pyaudio()


def _apply_volume(data: bytes, volume: float) -> bytes:
    """Scale 16-bit PCM audio data by volume (0.0-1.0)."""
    import array
    samples = array.array('h', data)
    for i in range(len(samples)):
        samples[i] = int(samples[i] * volume)
    return samples.tobytes()


class WavPlayer:
    """WAV file player with background threading."""

    def __init__(self):
        self.pa: Optional[object] = None
        self._lock = threading.Lock()
        self._loops: dict = {}
        self._init_pyaudio()

    def _init_pyaudio(self):
        if pyaudio is None:
            return
        try:
            self.pa = pyaudio.PyAudio()
        except Exception:
            self.pa = None

    def play(self, filename: str, volume: float = 1.0):
        if self.pa is None:
            return
        thread = threading.Thread(target=self._play_sync, args=(filename, volume))
        thread.daemon = True
        thread.start()

    def _play_sync(self, filename: str, volume: float = 1.0):
        if pyaudio is None:
            return
        stream = None
        wf = None
        try:
            if not os.path.exists(filename):
                return
            wf = wave.open(filename, 'rb')
            with self._lock:
                stream = self.pa.open(
                    format=self.pa.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while data:
                if volume != 1.0:
                    data = _apply_volume(data, volume)
                stream.write(data)
                data = wf.readframes(chunk_size)
        except Exception:
            pass
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    with self._lock:
                        stream.close()
                except Exception:
                    pass
            if wf is not None:
                wf.close()

    def loop_start(self, name: str, filename: str, volume: float = 1.0):
        if self.pa is None:
            return
        if name in self._loops and self._loops[name].alive:
            return
        loop = _LoopingSound(self, filename, volume)
        self._loops[name] = loop
        loop.start()

    def loop_stop(self, name: str):
        loop = self._loops.pop(name, None)
        if loop is not None:
            loop.stop()

    def close(self):
        for loop in list(self._loops.values()):
            loop.stop()
        self._loops.clear()
        if self.pa is not None:
            try:
                self.pa.terminate()
            except Exception:
                pass


class _LoopingSound:
    """Plays a WAV file in a loop on a single stream until stopped."""

    def __init__(self, player: WavPlayer, filename: str, volume: float = 1.0):
        self.player = player
        self.filename = filename
        self.volume = volume
        self.alive = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self.alive = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.alive = False

    def _run(self):
        stream = None
        try:
            wf = wave.open(self.filename, 'rb')
            fmt = self.player.pa.get_format_from_width(wf.getsampwidth())
            channels = wf.getnchannels()
            rate = wf.getframerate()
            raw_data = wf.readframes(wf.getnframes())
            wf.close()

            if self.volume != 1.0:
                raw_data = _apply_volume(raw_data, self.volume)

            with self.player._lock:
                stream = self.player.pa.open(
                    format=fmt, channels=channels, rate=rate, output=True
                )

            chunk_size = 1024 * channels * 2
            while self.alive:
                offset = 0
                while offset < len(raw_data) and self.alive:
                    end = min(offset + chunk_size, len(raw_data))
                    stream.write(raw_data[offset:end])
                    offset = end
        except Exception:
            pass
        finally:
            self.alive = False
            if stream is not None:
                try:
                    stream.stop_stream()
                    with self.player._lock:
                        stream.close()
                except Exception:
                    pass


class RelayPlayer:
    """Sends WAV data over TCP to an audio_relay.py instance."""

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._wav_cache: dict[str, bytes] = {}
        self._connect()

    def _connect(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self._host, self._port))
        except Exception:
            self._sock = None

    def _send_msg(self, payload: bytes):
        if self._sock is None:
            return
        msg = struct.pack('>I', len(payload)) + payload
        with self._lock:
            try:
                self._sock.sendall(msg)
            except Exception:
                self._sock = None

    def _read_wav(self, filename: str) -> bytes:
        cached = self._wav_cache.get(filename)
        if cached is not None:
            return cached
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            self._wav_cache[filename] = data
            return data
        except Exception:
            return b''

    def play(self, filename: str, volume: float = 1.0):
        wav_data = self._read_wav(filename)
        if not wav_data:
            return
        name = os.path.basename(filename).encode()
        payload = (bytes([_CMD_PLAY, len(name)]) + name +
                   struct.pack('>f', volume) + wav_data)
        self._send_msg(payload)

    def loop_start(self, name: str, filename: str, volume: float = 1.0):
        wav_data = self._read_wav(filename)
        if not wav_data:
            return
        name_b = name.encode()
        payload = (bytes([_CMD_LOOP_START, len(name_b)]) + name_b +
                   struct.pack('>f', volume) + wav_data)
        self._send_msg(payload)

    def loop_stop(self, name: str):
        name_b = name.encode()
        payload = bytes([_CMD_LOOP_STOP, len(name_b)]) + name_b
        self._send_msg(payload)

    def close(self):
        if self._sock:
            try:
                self._send_msg(bytes([_CMD_CLOSE]))
                self._sock.close()
            except Exception:
                pass
            self._sock = None


# Global player instance
_player = None


def get_player():
    global _player
    if _player is None:
        relay = os.environ.get('AUDIO_RELAY')
        if relay:
            try:
                host, port = relay.rsplit(':', 1)
                _player = RelayPlayer(host, int(port))
                return _player
            except Exception:
                pass
        _player = WavPlayer()
    return _player


def play(filename: str, volume: float = 1.0):
    get_player().play(filename, volume)


def loop_start(name: str, filename: str, volume: float = 1.0):
    get_player().loop_start(name, filename, volume)


def loop_stop(name: str):
    get_player().loop_stop(name)


def close():
    global _player
    if _player is not None:
        _player.close()
        _player = None
