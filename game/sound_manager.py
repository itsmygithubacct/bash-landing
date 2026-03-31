"""Lander-specific sound manager for thrust loops and one-shot effects."""

import os

from engine.audio import wav_player
from utils.paths import asset_path


class LanderSoundManager:
    """Sound manager for the lunar lander game.

    Thrust sounds loop continuously while active and stop when released.
    One-shot sounds (crash, landing, warnings) play once per trigger.
    """

    def __init__(self, config: dict = None):
        self.warning_cooldown = 0.0

        self._thrust_main_active = False
        self._thrust_side_active = False

        _all_paths = {
            'thrust_main': asset_path("sounds", "lander", "thrust_main.wav"),
            'thrust_side': asset_path("sounds", "lander", "thrust_side.wav"),
            'crash': asset_path("sounds", "lander", "crash_explosion.wav"),
            'landing': asset_path("sounds", "lander", "landing_success.wav"),
            'low_fuel': asset_path("sounds", "lander", "low_fuel_warning.wav"),
        }
        self.sound_paths = {k: v for k, v in _all_paths.items() if os.path.exists(v)}

    def update(self, dt: float):
        if self.warning_cooldown > 0:
            self.warning_cooldown -= dt

    def play_thrust_main(self):
        if not self._thrust_main_active:
            path = self.sound_paths.get('thrust_main')
            if path:
                wav_player.loop_start('thrust_main', path, volume=0.25)
                self._thrust_main_active = True

    def stop_thrust_main(self):
        if self._thrust_main_active:
            wav_player.loop_stop('thrust_main')
            self._thrust_main_active = False

    def play_thrust_side(self):
        if not self._thrust_side_active:
            path = self.sound_paths.get('thrust_side')
            if path:
                wav_player.loop_start('thrust_side', path, volume=0.20)
                self._thrust_side_active = True

    def stop_thrust_side(self):
        if self._thrust_side_active:
            wav_player.loop_stop('thrust_side')
            self._thrust_side_active = False

    def stop_all_thrust(self):
        self.stop_thrust_main()
        self.stop_thrust_side()

    def play_crash(self):
        self.stop_all_thrust()
        self._play('crash')

    def play_landing(self):
        self.stop_all_thrust()
        self._play('landing')

    def play_low_fuel_warning(self):
        if self.warning_cooldown <= 0:
            self._play('low_fuel')
            self.warning_cooldown = 1.0

    def _play(self, sound_name: str):
        path = self.sound_paths.get(sound_name)
        if path:
            wav_player.play(path)
