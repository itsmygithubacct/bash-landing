"""Sound manager that auto-generates missing menu sounds."""

import os

from engine.audio import wav_player
from engine.audio import sound_gen
from utils.paths import PROJECT_ROOT


class SoundManager:
    """Manages sound playback with auto-generated defaults."""

    def __init__(self, sounds_dir: str = "sounds"):
        self.sounds_dir = os.path.join(PROJECT_ROOT, sounds_dir)
        os.makedirs(self.sounds_dir, exist_ok=True)
        self._ensure_sounds()
        # Cache resolved paths for sounds that exist
        self._paths = {}
        for f in os.listdir(self.sounds_dir):
            if f.endswith('.wav'):
                self._paths[f] = os.path.join(self.sounds_dir, f)

    def _ensure_sounds(self):
        creators = {
            'menu_select.wav': sound_gen.create_menu_select_sound,
            'menu_move.wav': sound_gen.create_menu_move_sound,
        }
        for filename, creator in creators.items():
            filepath = os.path.join(self.sounds_dir, filename)
            if not os.path.exists(filepath):
                creator(filepath)

    def play(self, sound_name: str):
        if not sound_name.endswith('.wav'):
            sound_name = sound_name + '.wav'
        path = self._paths.get(sound_name)
        if path:
            wav_player.play(path)

    def play_menu_select(self):
        self.play('menu_select.wav')

    def play_menu_move(self):
        self.play('menu_move.wav')
