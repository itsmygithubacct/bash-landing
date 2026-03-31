"""Lander spacecraft with angular physics, thrust, and rendering."""

import random
import math

from engine.pixel_buffer import PixelBuffer
from game.physics import ShipPhysics

# Constant flame colors for main thrust rendering
FLAME_COLORS = [
    (255, 255, 200), (255, 255, 0), (255, 180, 0),
    (255, 80, 0), (200, 30, 0),
]


class Lander:
    """The lunar lander spacecraft using angular ship physics."""

    def __init__(self, x: float, y: float, fuel: float = 150.0, config: dict = None):
        gameplay = config.get('gameplay', {}) if config else {}

        self.ship_physics = ShipPhysics(x, y, config)

        self.width = gameplay.get('lander_width', 5)
        self.height = gameplay.get('lander_height', 5)

        self.fuel = fuel
        self.max_fuel = fuel
        self.fuel_main_rate = gameplay.get('fuel_main_rate', 10.0)
        self.fuel_side_rate = gameplay.get('fuel_side_rate', 4.0)
        self.side_thrust_power = gameplay.get('side_thrust_power', 12.0)

        self.crashed = False
        self.landed = False

        self.main_thrust_active = False
        self.left_thrust_active = False
        self.right_thrust_active = False

        self.crash_timer = 0.0
        self.crash_duration = 1.5
        self.explosion_particles = []

        self._flame_frame = 0

    # Property proxies for ship_physics
    @property
    def x(self):
        return self.ship_physics.x

    @x.setter
    def x(self, value):
        self.ship_physics.x = value

    @property
    def y(self):
        return self.ship_physics.y

    @y.setter
    def y(self, value):
        self.ship_physics.y = value

    @property
    def vx(self):
        return self.ship_physics.vx

    @vx.setter
    def vx(self, value):
        self.ship_physics.vx = value

    @property
    def vy(self):
        return self.ship_physics.vy

    @vy.setter
    def vy(self, value):
        self.ship_physics.vy = value

    @property
    def angle(self):
        return self.ship_physics.angle

    @angle.setter
    def angle(self, value):
        self.ship_physics.angle = value

    def get_speed(self) -> float:
        return self.ship_physics.get_speed()

    def get_rect(self):
        return (int(self.x), int(self.y), self.width, self.height)

    def get_center(self):
        return (self.x + self.width / 2, self.y + self.height / 2)

    def stop(self):
        self.ship_physics.stop()

    # Thrust methods

    def apply_main_thrust(self, dt: float) -> bool:
        if self.fuel > 0 and not self.crashed and not self.landed:
            self.ship_physics.apply_main_thrust(dt)
            self.fuel -= self.fuel_main_rate * dt
            self.fuel = max(0, self.fuel)
            self.main_thrust_active = True
            return True
        self.main_thrust_active = False
        return False

    def apply_left_thrust(self, dt: float) -> bool:
        if self.fuel > 0 and not self.crashed and not self.landed:
            self.ship_physics.apply_rotate_left(dt)
            self.vx -= self.side_thrust_power * dt
            self.fuel -= self.fuel_side_rate * dt
            self.fuel = max(0, self.fuel)
            self.left_thrust_active = True
            return True
        self.left_thrust_active = False
        return False

    def apply_right_thrust(self, dt: float) -> bool:
        if self.fuel > 0 and not self.crashed and not self.landed:
            self.ship_physics.apply_rotate_right(dt)
            self.vx += self.side_thrust_power * dt
            self.fuel -= self.fuel_side_rate * dt
            self.fuel = max(0, self.fuel)
            self.right_thrust_active = True
            return True
        self.right_thrust_active = False
        return False

    def clear_thrust_state(self):
        self.main_thrust_active = False
        self.left_thrust_active = False
        self.right_thrust_active = False

    def update(self, dt: float, gravity: float):
        if self.landed:
            return

        if self.crashed:
            self.crash_timer += dt
            for p in self.explosion_particles:
                p['x'] += p['vx'] * dt
                p['y'] += p['vy'] * dt
                p['vy'] += gravity * 0.3 * dt
                p['life'] -= dt
            self.explosion_particles = [p for p in self.explosion_particles if p['life'] > 0]
            return

        side_thrust_active = self.left_thrust_active or self.right_thrust_active
        self.ship_physics.update(dt, gravity, side_thrust_active)
        self._flame_frame += 1

    def trigger_crash(self):
        self.crashed = True
        self.crash_timer = 0.0
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        for _ in range(25):
            a = random.uniform(0, 2 * math.pi)
            speed = random.uniform(5, 30)
            self.explosion_particles.append({
                'x': cx + random.uniform(-2, 2),
                'y': cy + random.uniform(-2, 2),
                'vx': math.cos(a) * speed,
                'vy': math.sin(a) * speed - random.uniform(5, 15),
                'life': random.uniform(0.3, 1.2),
                'max_life': random.uniform(0.3, 1.2),
                'color_type': random.choice(['fire', 'debris', 'spark'])
            })

    def can_land_safely(self) -> bool:
        return self.ship_physics.can_land_safely()

    def get_landing_quality(self) -> str:
        speed = self.get_speed()
        max_safe = self.ship_physics.max_safe_speed
        if speed <= max_safe * 0.25:
            return "PERFECT!"
        elif speed <= max_safe * 0.5:
            return "GREAT!"
        elif speed <= max_safe * 0.75:
            return "GOOD"
        return "OK"

    def get_landing_bonus(self) -> int:
        speed = self.get_speed()
        max_safe = self.ship_physics.max_safe_speed
        if speed <= max_safe * 0.25:
            return 100
        elif speed <= max_safe * 0.5:
            return 50
        elif speed <= max_safe * 0.75:
            return 25
        return 0

    def get_altitude(self, terrain_height_at_x: float) -> float:
        return terrain_height_at_x - (self.y + self.height)

    def reset(self, x: float, y: float, fuel: float):
        self.ship_physics.reset(x, y)
        self.fuel = fuel
        self.max_fuel = fuel
        self.crashed = False
        self.landed = False
        self.crash_timer = 0.0
        self.explosion_particles = []
        self.clear_thrust_state()

    # Drawing

    def _tilt_offset(self, row: int) -> int:
        dist = (self.height - 1) - row
        return int(math.sin(self.angle) * dist)

    def draw(self, buffer: PixelBuffer):
        lx, ly = int(self.x), int(self.y)

        if self.crashed:
            self._draw_explosion(buffer)
            return

        self._draw_thrust_flames(buffer, lx, ly)

        lander_color = (200, 200, 220) if not self.landed else (100, 255, 100)

        # Main body (3x3 center, rows 1-3)
        for dy in range(1, 4):
            off = self._tilt_offset(dy)
            for dx in range(1, 4):
                px, py = lx + dx + off, ly + dy
                if 0 <= px < buffer.width and 0 <= py < buffer.height:
                    buffer.set_pixel(px, py, lander_color)

        # Cockpit (top row)
        off0 = self._tilt_offset(0)
        px, py = lx + 2 + off0, ly
        if 0 <= px < buffer.width and 0 <= py < buffer.height:
            buffer.set_pixel(px, py, (120, 200, 255))
        for dx in [1, 3]:
            px, py = lx + dx + off0, ly
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, (80, 140, 180))

        # Landing legs (row 4)
        off4 = self._tilt_offset(4)
        leg_color = (180, 180, 180)
        for dx in [0, 4]:
            px, py = lx + dx + off4, ly + 4
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, leg_color)

        # Leg struts (row 3)
        off3 = self._tilt_offset(3)
        for dx in [0, 4]:
            px, py = lx + dx + off3, ly + 3
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, (140, 140, 140))

        # Engine nozzle
        px, py = lx + 2 + off4, ly + 4
        if 0 <= px < buffer.width and 0 <= py < buffer.height:
            buffer.set_pixel(px, py, (100, 100, 120))

        # Rotation indicator lights
        if self.angle < -0.1:
            off1 = self._tilt_offset(1)
            px, py = lx + off1, ly + 1
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, (255, 255, 0))
        elif self.angle > 0.1:
            off1 = self._tilt_offset(1)
            px, py = lx + 4 + off1, ly + 1
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, (255, 255, 0))

        # Landed glow
        if self.landed:
            for dx in range(5):
                px, py = lx + dx, ly + 5
                if 0 <= px < buffer.width and 0 <= py < buffer.height:
                    buffer.set_pixel(px, py, (0, 100, 0))

    def _draw_thrust_flames(self, buffer: PixelBuffer, lx: int, ly: int):
        flicker = self._flame_frame % 3

        if self.main_thrust_active:
            sin_a = math.sin(self.angle)
            cos_a = math.cos(self.angle)
            off4 = self._tilt_offset(4)

            flame_height = 3 + (flicker % 2)
            nozzle_x = lx + 2 + off4
            nozzle_y = ly + self.height

            for i in range(flame_height):
                fx = nozzle_x - int(sin_a * (i + 1))
                fy = nozzle_y + int(cos_a * (i + 1))
                if 0 <= fy < buffer.height:
                    color = FLAME_COLORS[min(i, len(FLAME_COLORS) - 1)]

                    if 0 <= fx < buffer.width:
                        buffer.set_pixel(fx, fy, color)

                    if i < 3:
                        for dx in [-1, 1]:
                            sx = fx + dx
                            if 0 <= sx < buffer.width:
                                dim = 0.7
                                edge_color = (int(color[0]*dim), int(color[1]*dim), int(color[2]*dim))
                                buffer.set_pixel(sx, fy, edge_color)

                    if i == 0:
                        for dx in [-2, 2]:
                            sx = fx + dx
                            if 0 <= sx < buffer.width:
                                buffer.set_pixel(sx, fy, (200, 150, 50))

            if random.random() > 0.4:
                spark_dist = flame_height + random.randint(0, 1)
                spark_x = nozzle_x - int(sin_a * spark_dist) + random.randint(-1, 1)
                spark_y = nozzle_y + int(cos_a * spark_dist)
                if 0 <= spark_x < buffer.width and 0 <= spark_y < buffer.height:
                    buffer.set_pixel(spark_x, spark_y, (255, random.randint(100, 200), 0))

        if self.left_thrust_active:
            self._draw_side_flame(buffer, lx, ly, flicker, direction=1)

        if self.right_thrust_active:
            self._draw_side_flame(buffer, lx, ly, flicker, direction=-1)

    def _draw_side_flame(self, buffer: PixelBuffer, lx: int, ly: int,
                         flicker: int, direction: int):
        """Draw a side thruster flame. direction: 1=left thruster (flame right), -1=right (flame left)."""
        colors = [(255, 200, 50), (255, 140, 0)]
        off2 = self._tilt_offset(2)
        # Left thruster: flame extends from right edge; right thruster: from left edge
        base_x = (lx + self.width + off2) if direction == 1 else (lx - 1 + off2)

        for i, color in enumerate(colors):
            px = base_x + i * direction
            py = ly + 2
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                buffer.set_pixel(px, py, color)
            if i == 0 and flicker != 2:
                for dy in [-1, 1]:
                    py2 = ly + 2 + dy
                    if 0 <= base_x < buffer.width and 0 <= py2 < buffer.height:
                        buffer.set_pixel(base_x, py2, (200, 120, 0))

    def _draw_explosion(self, buffer: PixelBuffer):
        progress = min(self.crash_timer / self.crash_duration, 1.0)

        for p in self.explosion_particles:
            px, py = int(p['x']), int(p['y'])
            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                life_ratio = max(0, p['life'] / p['max_life'])
                if p['color_type'] == 'fire':
                    r = int(255 * life_ratio)
                    g = int(random.randint(50, 180) * life_ratio)
                    b = 0
                elif p['color_type'] == 'spark':
                    r = int(255 * life_ratio)
                    g = int(255 * life_ratio)
                    b = int(random.randint(100, 200) * life_ratio)
                else:
                    gray = int(random.randint(80, 180) * life_ratio)
                    r, g, b = gray, gray, gray
                color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
                buffer.set_pixel(px, py, color)

        if progress < 0.15:
            flash_intensity = 1.0 - (progress / 0.15)
            cx, cy = int(self.x + self.width / 2), int(self.y + self.height / 2)
            flash_radius = int(3 + progress * 10)
            radius_sq = flash_radius * flash_radius
            for dx in range(-flash_radius, flash_radius + 1):
                for dy in range(-flash_radius, flash_radius + 1):
                    dist_sq = dx * dx + dy * dy
                    if dist_sq <= radius_sq:
                        px, py = cx + dx, cy + dy
                        if 0 <= px < buffer.width and 0 <= py < buffer.height:
                            # Fast approximate intensity (avoid sqrt)
                            intensity = flash_intensity * (1 - dist_sq / radius_sq)
                            buffer.set_pixel(px, py, (int(255*intensity), int(200*intensity), int(50*intensity)))


class ThrustParticle:
    """A particle effect from thrust exhaust."""

    def __init__(self, x: float, y: float, vx: float, vy: float):
        self.x = x
        self.y = y
        self.vx = vx + random.uniform(-8, 8)
        self.vy = vy + random.uniform(5, 20)
        self.life = random.uniform(0.3, 0.7)
        self.max_life = self.life
        self.color_type = random.choice(['hot', 'warm', 'cool'])

    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 3.0 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, buffer: PixelBuffer):
        px, py = int(self.x), int(self.y)
        if 0 <= px < buffer.width and 0 <= py < buffer.height:
            alpha = max(0, self.life / self.max_life)
            if self.color_type == 'hot':
                color = (int(255 * alpha), int(255 * alpha), int(100 * alpha))
            elif self.color_type == 'warm':
                color = (int(255 * alpha), int(150 * alpha), 0)
            else:
                color = (int(200 * alpha), int(80 * alpha), 0)
            buffer.set_pixel(px, py, color)
