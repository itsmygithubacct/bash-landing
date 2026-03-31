"""Procedurally generated lunar terrain with landing pads."""

import random
import math
from typing import List, Tuple, Optional

from engine.pixel_buffer import PixelBuffer

TERRAIN_SURFACE_COLOR = (160, 160, 150)
TERRAIN_FILL_COLOR = (90, 85, 80)
EARTH_POS = (-15, 8)
EARTH_RADIUS = 4

# Max terrain depth for fill color lookup table
_MAX_FILL_DEPTH = 40

# Star indices for list-based storage (mutable x for drift)
_SX, _SY, _SBRIGHT, _SSPEED, _SPHASE, _SSIZE, _SDRIFT = range(7)


def _build_fill_lut(fill_color, max_depth=_MAX_FILL_DEPTH):
    """Precompute gradient fill colors indexed by depth."""
    lut = []
    for depth in range(max_depth):
        darken = max(0.4, 1.0 - depth * 0.03)
        lut.append((int(fill_color[0]*darken), int(fill_color[1]*darken), int(fill_color[2]*darken)))
    return lut


def _prerender_earth(width, height):
    """Pre-render earth pixels once as a list of (px, py, color) tuples."""
    cx = width + EARTH_POS[0]
    cy = EARTH_POS[1]
    r = EARTH_RADIUS
    pixels = []
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            dist_sq = dx * dx + dy * dy
            if dist_sq > r * r:
                continue
            px, py = cx + dx, cy + dy
            if not (0 <= px < width and 0 <= py < height):
                continue
            dist = math.sqrt(dist_sq)
            if dist <= r * 0.9:
                if (dx + dy) % 3 == 0 and dist > r * 0.3:
                    color = (30, 120, 40)
                else:
                    color = (30, 60, 180)
                if abs(dy) > r * 0.7:
                    color = (220, 220, 230)
            else:
                color = (80, 130, 220)
            pixels.append((px, py, color))
    return pixels


class LandingPad:
    """A landing pad on the terrain surface."""

    def __init__(self, x: int, y: int, width: int, points: int = 50):
        self.x = x
        self.y = y
        self.width = width
        self.height = 2
        self.points = points
        self.color = (0, 255, 0) if points >= 100 else (255, 255, 0)

    def check_collision(self, obj_x: int, obj_y: int, obj_width: int, obj_height: int,
                        tolerance: int = 2) -> bool:
        obj_bottom = obj_y + obj_height
        obj_left = obj_x
        obj_right = obj_x + obj_width

        if abs(obj_bottom - self.y) <= tolerance:
            if obj_left >= self.x and obj_right <= self.x + self.width:
                return True
        return False


class TerrainGenerator:
    """Generates terrain heightmaps with landing pads."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.terrain_points: List[Tuple[int, int]] = []
        self.landing_pads: List[LandingPad] = []

    def generate(self, base_height: int, roughness: int, num_pads: int,
                 pad_width_range: Tuple[int, int], pad_points_range: Tuple[int, int]):
        self.terrain_points = []
        self.landing_pads = []
        current_x = 0

        if num_pads > 0:
            segment_width = self.width // (num_pads + 1)
            for pad_index in range(num_pads):
                target_x = segment_width * (pad_index + 1)
                while current_x < target_x - 15:
                    y = base_height + random.randint(-roughness, roughness)
                    self.terrain_points.append((current_x, y))
                    current_x += random.randint(3, 8)

                pad_width = random.randint(pad_width_range[0], pad_width_range[1])
                pad_y = base_height + random.randint(-roughness // 2, roughness // 2)

                if pad_width <= (pad_width_range[0] + pad_width_range[1]) // 2:
                    points = pad_points_range[1]
                else:
                    points = pad_points_range[0]

                if not self.terrain_points or self.terrain_points[-1][0] < current_x:
                    self.terrain_points.append((current_x, pad_y))

                self.landing_pads.append(LandingPad(current_x, pad_y, pad_width, points))
                self.terrain_points.append((current_x, pad_y))
                current_x += pad_width
                self.terrain_points.append((current_x, pad_y))

        while current_x < self.width:
            y = base_height + random.randint(-roughness, roughness)
            self.terrain_points.append((current_x, y))
            current_x += random.randint(3, 8)

        if self.terrain_points and self.terrain_points[-1][0] < self.width:
            self.terrain_points.append((self.width, self.terrain_points[-1][1]))

    def add_overhangs(self, count: int, max_height: int):
        """Insert sharp overhang spikes into the terrain, avoiding landing pads.

        Each overhang is a narrow upward protrusion (3-6px wide) that juts
        above the surrounding terrain, creating lips the lander can crash into.
        """
        if len(self.terrain_points) < 4:
            return

        # Build exclusion zones around pads (pad area + margin on each side)
        pad_zones = []
        for pad in self.landing_pads:
            pad_zones.append((pad.x - 8, pad.x + pad.width + 8))

        def in_pad_zone(x):
            return any(lo <= x <= hi for lo, hi in pad_zones)

        # Collect candidate segment indices (not at edges, not near pads)
        candidates = []
        for i in range(1, len(self.terrain_points) - 2):
            x1 = self.terrain_points[i][0]
            x2 = self.terrain_points[i + 1][0]
            mid_x = (x1 + x2) // 2
            if not in_pad_zone(mid_x) and (x2 - x1) >= 4:
                candidates.append(i)

        random.shuffle(candidates)
        inserted = 0

        for seg_idx in candidates:
            if inserted >= count:
                break

            x1, y1 = self.terrain_points[seg_idx]
            x2, y2 = self.terrain_points[seg_idx + 1]

            # Overhang position: random point within the segment
            overhang_width = random.randint(3, 6)
            ox = random.randint(x1 + 1, max(x1 + 1, x2 - overhang_width))
            if in_pad_zone(ox) or in_pad_zone(ox + overhang_width):
                continue

            # Interpolate base height at overhang position
            if x2 != x1:
                t = (ox - x1) / (x2 - x1)
                base_y = int(y1 + t * (y2 - y1))
            else:
                base_y = y1

            # Overhang rises above the surface then drops back
            rise = random.randint(4, max_height)
            peak_y = base_y - rise

            # Insert 4 points: approach, peak-left, peak-right, return
            new_points = [
                (ox, base_y),
                (ox + 1, peak_y),
                (ox + overhang_width - 1, peak_y),
                (ox + overhang_width, base_y),
            ]

            # Insert after seg_idx (shift index for each insertion)
            insert_pos = seg_idx + 1 + (inserted * 4)
            for j, pt in enumerate(new_points):
                self.terrain_points.insert(insert_pos + j, pt)

            inserted += 1

    def get_height_at(self, x: int) -> float:
        for i in range(len(self.terrain_points) - 1):
            x1, y1 = self.terrain_points[i]
            x2, y2 = self.terrain_points[i + 1]
            if x1 <= x <= x2:
                if x2 != x1:
                    t = (x - x1) / (x2 - x1)
                    return y1 + t * (y2 - y1)
                return y1
        if self.terrain_points:
            return self.terrain_points[-1][1]
        return self.height

    def check_collision(self, obj_x: int, obj_y: int, obj_width: int, obj_height: int):
        for pad in self.landing_pads:
            if pad.check_collision(obj_x, obj_y, obj_width, obj_height):
                return (True, True, pad)

        corners = [
            (obj_x, obj_y + obj_height), (obj_x + obj_width, obj_y + obj_height),
            (obj_x, obj_y), (obj_x + obj_width, obj_y)
        ]
        for corner_x, corner_y in corners:
            if corner_x < 0 or corner_x >= self.width:
                continue
            if corner_y >= self.get_height_at(corner_x):
                return (True, False, None)

        return (False, False, None)

    def draw(self, buffer: PixelBuffer, terrain_color: Tuple[int, int, int],
             fill_color: Tuple[int, int, int], fill_lut=None):
        if fill_lut is None:
            fill_lut = _build_fill_lut(fill_color)
        max_depth = len(fill_lut)
        set_fast = buffer.set_pixel_fast
        buf_w = buffer.width
        buf_h = buffer.height

        for i in range(len(self.terrain_points) - 1):
            x1, y1 = self.terrain_points[i]
            x2, y2 = self.terrain_points[i + 1]
            buffer.draw_line(x1, y1, x2, y2, terrain_color)

            for x in range(max(0, x1), min(x2 + 1, self.width, buf_w)):
                if x2 != x1:
                    t = (x - x1) / (x2 - x1)
                    y = int(y1 + t * (y2 - y1))
                else:
                    y = y1
                for fill_y in range(max(0, y), min(self.height, buf_h)):
                    set_fast(x, fill_y, fill_lut[min(fill_y - y, max_depth - 1)])

        for pad in self.landing_pads:
            if pad.x >= 0 and pad.x + pad.width <= buffer.width:
                buffer.draw_rect(pad.x, pad.y, pad.width, pad.height, pad.color, filled=True)
                for i in range(0, pad.width, 3):
                    px = pad.x + i
                    if 0 <= px < buffer.width and 0 <= pad.y < buffer.height:
                        buffer.set_pixel(px, pad.y, (255, 255, 255))


class LanderTerrain:
    """Complete terrain system with stars, Earth, and landing pads."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.terrain_generator = TerrainGenerator(width, height)
        self.stars = []
        self._generate_stars(40)
        self._frame = 0
        self._earth_pixels = _prerender_earth(width, height)
        self._fill_lut = _build_fill_lut(TERRAIN_FILL_COLOR)

    def _generate_stars(self, count: int):
        """Generate stars with slow horizontal drift (parallax effect).

        Dimmer/smaller stars drift slower, giving depth.
        """
        self.stars = []
        for _ in range(count):
            brightness = random.choice([80, 120, 160, 200, 240])
            # Drift speed scales with brightness: dim stars ~0.3 px/s, bright ~1.5 px/s
            drift = random.uniform(0.2, 0.6) * (brightness / 240.0) + 0.1
            # Random direction
            if random.random() < 0.5:
                drift = -drift
            self.stars.append([
                float(random.randint(0, self.width - 1)),  # x (float for sub-pixel drift)
                random.randint(0, self.height // 2),        # y
                brightness,
                random.uniform(1.0, 4.0),                   # twinkle_speed
                random.uniform(0, 2 * math.pi),             # twinkle_phase
                1 if random.random() > 0.1 else 2,          # size
                drift,                                       # drift_speed (px/s)
            ])

    def generate_level(self, level: int, config: dict):
        gameplay = config.get('gameplay', {})

        pad_width = self._calculate_pad_width(level, config)
        roughness = self._calculate_roughness(level, config)
        base_height = gameplay.get('terrain_base_height', self.height - 15)

        base_points = gameplay.get('base_landing_points', 50)
        bonus_points = gameplay.get('bonus_landing_points', 50)

        lander_width = gameplay.get('lander_width', 5)
        points = base_points + bonus_points if pad_width <= lander_width + 3 else base_points

        self.terrain_generator.generate(
            base_height=base_height, roughness=roughness, num_pads=1,
            pad_width_range=(pad_width, pad_width),
            pad_points_range=(points, points)
        )

        # After level 20, add increasingly treacherous overhangs
        if level > 20:
            overhang_levels = level - 20
            count = min(1 + overhang_levels // 3, 6)
            max_height = min(4 + overhang_levels // 2, 14)
            self.terrain_generator.add_overhangs(count, max_height)

    def _calculate_pad_width(self, level: int, config: dict) -> int:
        gameplay = config.get('gameplay', {})
        lander_width = gameplay.get('lander_width', 5)
        initial_width = gameplay.get('initial_pad_width', 15)
        min_width = lander_width + gameplay.get('min_pad_margin', 2)

        levels_to_min = initial_width - min_width
        if level <= levels_to_min:
            return initial_width - (level - 1)
        else:
            levels_past = level - levels_to_min
            additional_decrease = (levels_past - 1) // 10
            return max(lander_width, min_width - additional_decrease)

    def _calculate_roughness(self, level: int, config: dict) -> int:
        gameplay = config.get('gameplay', {})
        base = gameplay.get('base_roughness', 8)
        rate = gameplay.get('roughness_increase_rate', 2)
        return base + (level - 1) // rate

    def check_collision(self, obj_x, obj_y, obj_width, obj_height):
        return self.terrain_generator.check_collision(obj_x, obj_y, obj_width, obj_height)

    def get_landing_pads(self):
        return self.terrain_generator.landing_pads

    def get_height_at(self, x: int) -> float:
        return self.terrain_generator.get_height_at(x)

    def draw(self, buffer: PixelBuffer, draw_stars: bool = True):
        self._frame += 1
        dt = 1.0 / 60.0  # fixed timestep for star drift

        if draw_stars:
            t = self._frame / 60.0
            w = self.width
            for star in self.stars:
                # Drift horizontally, wrap around screen edges
                star[_SX] += star[_SDRIFT] * dt
                if star[_SX] < -1:
                    star[_SX] += w + 1
                elif star[_SX] > w:
                    star[_SX] -= w + 1

                sx = int(star[_SX])
                sy = star[_SY]
                if 0 <= sx < buffer.width and 0 <= sy < buffer.height:
                    twinkle = math.sin(t * star[_SSPEED] + star[_SPHASE])
                    brightness = max(40, min(255, int(star[_SBRIGHT] + twinkle * 40)))
                    if star[_SBRIGHT] > 180:
                        color = (brightness, brightness, min(255, brightness + 20))
                    else:
                        color = (brightness, brightness, brightness)
                    buffer.set_pixel(sx, sy, color)
                    if star[_SSIZE] > 1 and brightness > 150:
                        dim = int(brightness * 0.4)
                        for ddx, ddy in [(1, 0), (0, 1), (1, 1)]:
                            px, py = sx + ddx, sy + ddy
                            if 0 <= px < buffer.width and 0 <= py < buffer.height:
                                buffer.set_pixel(px, py, (dim, dim, dim))

        # Pre-rendered earth -- just blit stored pixels
        for px, py, color in self._earth_pixels:
            buffer.set_pixel(px, py, color)

        self.terrain_generator.draw(buffer, TERRAIN_SURFACE_COLOR, TERRAIN_FILL_COLOR,
                                    fill_lut=self._fill_lut)

    def draw_landing_pad_markers(self, buffer: PixelBuffer):
        blink = (self._frame // 15) % 2

        for pad in self.terrain_generator.landing_pads:
            light_y = pad.y - 3
            if light_y >= 0:
                light_color = (255, 255, 0) if blink else (100, 100, 0)
                for px in [pad.x - 1, pad.x + pad.width]:
                    if 0 <= px < buffer.width:
                        buffer.set_pixel(px, light_y, light_color)

            if blink:
                for guide_y in range(max(0, pad.y - 8), pad.y - 3, 2):
                    dim_light = (80, 80, 0)
                    for px in [pad.x - 1, pad.x + pad.width]:
                        if 0 <= px < buffer.width and 0 <= guide_y < buffer.height:
                            buffer.set_pixel(px, guide_y, dim_light)

            if pad.points >= 100:
                for i in range(0, pad.width, 2):
                    px = pad.x + i
                    if 0 <= px < buffer.width and pad.y >= 0:
                        buffer.set_pixel(px, pad.y, (0, 255, 0))
