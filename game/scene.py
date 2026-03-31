"""Main gameplay scene for Bash Landing."""

import random
import math

from engine import Game, PixelBuffer, GameSceneBase
from game.lander import Lander, ThrustParticle
from game.terrain import LanderTerrain
from game.sound_manager import LanderSoundManager
from game.hud import draw_hud, draw_level_complete, draw_game_over
from utils.logger import create_game_logger

_logger = create_game_logger("game_scene")

SPACE_BG_COLOR = (0, 0, 8)


class TerminalLanderGameScene(GameSceneBase):
    """Main lunar lander gameplay scene."""

    def __init__(self, game: Game, config: dict, start_level: int = 1):
        display_config = config.get('display', {})
        super().__init__(game, sounds_dir=display_config.get('sounds_dir', 'sounds'))

        self.config = config
        self._start_level = start_level
        game_config = config['game']
        gameplay = config['gameplay']

        self.width = game_config['width']
        self.height = game_config['height']

        # Game state
        self.lander = None
        self.terrain = None
        self.gravity = gameplay['gravity']
        self.score = 0
        self.level = start_level
        self.lives = gameplay.get('starting_lives', 3)
        self.game_over = False
        self.level_complete = False
        self.level_complete_timer = 0.0
        self.level_complete_delay = gameplay.get('level_complete_delay', 2.0)
        self.landed_pad = None
        self._landing_bonus = 0

        # Crash animation
        self.crash_animating = False
        self.crash_anim_timer = 0.0
        self.crash_anim_duration = 1.2

        # Particles
        self.thrust_particles = []

        # Sound
        self.lander_sounds = LanderSoundManager(config)

        # Thrust hold timers for simultaneous keys via alternating terminal input
        self._thrust_hold = {'up': 0.0, 'left': 0.0, 'right': 0.0}
        self._thrust_hold_duration = 0.10

        # Cache control keys and frame dt to avoid per-frame dict lookups
        controls = config['controls']
        self._keys_up = controls.get('thrust_up', ['UP_ARROW', 'w'])
        self._keys_left = controls.get('thrust_left', ['LEFT_ARROW', 'a'])
        self._keys_right = controls.get('thrust_right', ['RIGHT_ARROW', 'd'])
        self._keys_confirm = controls.get('confirm', ['RETURN'])
        self._frame_dt = 1.0 / game_config['fps']

        self.create_level()

    def calculate_starting_fuel(self, level: int) -> float:
        gameplay = self.config['gameplay']
        initial = gameplay.get('initial_fuel', 150.0)
        minimum = gameplay.get('min_fuel', 30.0)
        decrease = gameplay.get('fuel_decrease_per_level', 2.0)
        return max(initial - (level - 1) * decrease, minimum)

    def create_level(self):
        gameplay = self.config['gameplay']
        self.terrain = LanderTerrain(self.width, self.height)
        self.terrain.generate_level(self.level, self.config)

        fuel = self.calculate_starting_fuel(self.level)
        start_x = random.randint(10, self.width - 20)
        start_y = 8

        if self.lander is None:
            self.lander = Lander(start_x, start_y, fuel=fuel, config=self.config)
        else:
            self.lander.reset(start_x, start_y, fuel)

        self.thrust_particles = []
        self.landed_pad = None
        self.crash_animating = False
        self.crash_anim_timer = 0.0

    def on_enter(self):
        self.score = 0
        self.level = self._start_level
        self.lives = self.config['gameplay'].get('starting_lives', 3)
        self.game_over = False
        self.level_complete = False
        self.level_complete_timer = 0.0
        self.create_level()

    def next_level(self):
        self.level += 1
        self.level_complete = False
        self.level_complete_timer = 0.0
        self.create_level()

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.game_over = True
        else:
            self.create_level()

    def _trigger_crash(self):
        self.lander.trigger_crash()
        self.crash_animating = True
        self.crash_anim_timer = 0.0
        self.lander_sounds.play_crash()

    def update(self, dt: float):
        self.lander_sounds.update(dt)

        if self.game_over:
            return

        if self.level_complete:
            self.level_complete_timer += dt
            if self.level_complete_timer >= self.level_complete_delay:
                self.next_level()
            return

        if self.crash_animating:
            self.crash_anim_timer += dt
            self.lander.update(dt, self.gravity)
            if self.crash_anim_timer >= self.crash_anim_duration:
                self.crash_animating = False
                self.lose_life()
            return

        self.lander.update(dt, self.gravity)
        self.lander.clear_thrust_state()

        # Off-screen checks
        if self.lander.x < -self.lander.width or self.lander.x > self.width:
            self._trigger_crash()
            return
        if self.lander.y > self.height:
            self._trigger_crash()
            return

        # Terrain collision
        if not self.lander.crashed and not self.lander.landed:
            lx, ly, lw, lh = self.lander.get_rect()
            collided, on_pad, pad = self.terrain.check_collision(lx, ly, lw, lh)

            if collided:
                if on_pad and self.lander.can_land_safely():
                    self.lander.landed = True
                    self.lander.stop()
                    self.lander.y = pad.y - self.lander.height
                    bonus = self.lander.get_landing_bonus()
                    self.score += pad.points + bonus
                    self.landed_pad = pad
                    self._landing_bonus = bonus
                    self.level_complete = True
                    self.lander_sounds.play_landing()
                else:
                    self._trigger_crash()
                    return

        fuel_warn = self.config['gameplay'].get('fuel_warning_threshold', 25)
        if self.lander.fuel < fuel_warn and self.lander.fuel > 0:
            self.lander_sounds.play_low_fuel_warning()

        self.thrust_particles = [p for p in self.thrust_particles if p.update(dt)]

    def handle_input(self, input_handler):
        if self.handle_pause_input(input_handler):
            return

        if self.game_over:
            self.lander_sounds.stop_all_thrust()
            self.handle_game_over_input(input_handler)
            return

        if self.level_complete:
            for key in self._keys_confirm:
                if input_handler.is_key_just_pressed(key):
                    self.next_level()
                    input_handler.release_key(key)
            return

        if self.crash_animating:
            self.lander_sounds.stop_all_thrust()
            return

        dt = self._frame_dt

        # Decay hold timers
        for action in self._thrust_hold:
            if self._thrust_hold[action] > 0:
                self._thrust_hold[action] -= dt

        # Detect key presses
        for key in self._keys_up:
            if input_handler.is_key_pressed(key):
                self._thrust_hold['up'] = self._thrust_hold_duration
        for key in self._keys_left:
            if input_handler.is_key_pressed(key):
                self._thrust_hold['left'] = self._thrust_hold_duration
        for key in self._keys_right:
            if input_handler.is_key_pressed(key):
                self._thrust_hold['right'] = self._thrust_hold_duration

        # Apply thrust
        if self._thrust_hold['up'] > 0:
            if self.lander.apply_main_thrust(dt):
                self.lander_sounds.play_thrust_main()
                for _ in range(3):
                    self.thrust_particles.append(ThrustParticle(
                        self.lander.x + self.lander.width / 2,
                        self.lander.y + self.lander.height,
                        self.lander.vx * 0.3,
                        abs(self.lander.vy) * 0.2
                    ))
        else:
            self.lander_sounds.stop_thrust_main()

        side_active = False
        if self._thrust_hold['left'] > 0:
            if self.lander.apply_left_thrust(dt):
                self.lander_sounds.play_thrust_side()
                side_active = True
                self.thrust_particles.append(ThrustParticle(
                    self.lander.x + self.lander.width,
                    self.lander.y + self.lander.height / 2,
                    10, self.lander.vy * 0.1
                ))

        if self._thrust_hold['right'] > 0:
            if self.lander.apply_right_thrust(dt):
                self.lander_sounds.play_thrust_side()
                side_active = True
                self.thrust_particles.append(ThrustParticle(
                    self.lander.x,
                    self.lander.y + self.lander.height / 2,
                    -10, self.lander.vy * 0.1
                ))

        if not side_active:
            self.lander_sounds.stop_thrust_side()

    def render(self, buffer: PixelBuffer):
        buffer.clear(SPACE_BG_COLOR)

        self.terrain.draw(buffer, draw_stars=True)
        self.terrain.draw_landing_pad_markers(buffer)

        for particle in self.thrust_particles:
            particle.draw(buffer)

        self.lander.draw(buffer)

        draw_hud(buffer, self.lander, self.terrain, self.config,
                 score=self.score, level=self.level, lives=self.lives)

        if self.level_complete:
            draw_level_complete(buffer, self.width, self.height,
                              self.landed_pad, self.lander, self._landing_bonus)

        if self.game_over:
            draw_game_over(buffer, self.width, self.height, self.score, self.level)
