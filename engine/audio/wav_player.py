"""WAV file player with threading and looping support."""

import wave
import os
import sys
import logging
from typing import Optional
import threading
import subprocess
import ctypes

logger = logging.getLogger(__name__)


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


# Global player instance
_player: Optional[WavPlayer] = None


def get_player() -> WavPlayer:
    global _player
    if _player is None:
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
