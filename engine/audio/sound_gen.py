"""WAV sound generation utilities for creating simple sound effects."""

import wave
import struct
import math


def generate_sine_wave(frequency: float, duration: float,
                       sample_rate: int = 44100,
                       amplitude: float = 0.3) -> bytes:
    """Generate a sine wave as raw audio bytes."""
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        value = amplitude * math.sin(2 * math.pi * frequency * t)
        samples.append(struct.pack('<h', int(value * 32767)))
    return b''.join(samples)


def save_wav(filename: str, audio_data: bytes, sample_rate: int = 44100):
    """Save raw audio data to a WAV file."""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data)


def create_coin_sound(filename: str):
    """Create a coin collection sound effect."""
    sr = 44100
    audio = (generate_sine_wave(523, 0.05, sr, 0.3) +
             generate_sine_wave(659, 0.05, sr, 0.3) +
             generate_sine_wave(784, 0.05, sr, 0.2))
    save_wav(filename, audio, sr)


def create_jump_sound(filename: str):
    """Create a jump sound effect."""
    sr = 44100
    duration = 0.15
    num_samples = int(sr * duration)
    samples = []
    for i in range(num_samples):
        t = i / sr
        progress = i / num_samples
        frequency = 200 + progress * 400
        amplitude = 0.3 * (1 - progress)
        value = amplitude * math.sin(2 * math.pi * frequency * t)
        samples.append(struct.pack('<h', int(value * 32767)))
    save_wav(filename, b''.join(samples), sr)


def create_hit_sound(filename: str):
    """Create a hit/damage sound effect."""
    import random
    sr = 44100
    num_samples = int(sr * 0.1)
    samples = []
    for i in range(num_samples):
        t = i / sr
        progress = i / num_samples
        frequency = 100 - progress * 50
        noise = random.random() * 2 - 1
        tone = math.sin(2 * math.pi * frequency * t)
        value = 0.3 * (0.3 * tone + 0.7 * noise) * (1 - progress)
        samples.append(struct.pack('<h', int(value * 32767)))
    save_wav(filename, b''.join(samples), sr)


def create_explosion_sound(filename: str):
    """Create an explosion sound effect."""
    import random
    sr = 44100
    num_samples = int(sr * 0.3)
    samples = []
    for i in range(num_samples):
        t = i / sr
        progress = i / num_samples
        rumble = math.sin(2 * math.pi * 60 * t) * 0.4
        noise = random.random() * 2 - 1
        envelope = progress / 0.1 if progress < 0.1 else 1 - (progress - 0.1) / 0.9
        value = (rumble + noise * 0.6) * envelope * 0.3
        samples.append(struct.pack('<h', int(value * 32767)))
    save_wav(filename, b''.join(samples), sr)


def create_menu_select_sound(filename: str):
    save_wav(filename, generate_sine_wave(800, 0.05, amplitude=0.2))


def create_menu_move_sound(filename: str):
    save_wav(filename, generate_sine_wave(600, 0.03, amplitude=0.15))
