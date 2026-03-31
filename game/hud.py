"""HUD rendering for the lunar lander game."""

import math

from engine.pixel_buffer import PixelBuffer
from engine.font import draw_text


def _draw_mini_ship(buffer: PixelBuffer, x: int, y: int):
    """Draw a tiny 5x5 lander icon for the lives indicator."""
    # Cockpit
    buffer.set_pixel(x + 2, y, (120, 200, 255))
    buffer.set_pixel(x + 1, y, (80, 140, 180))
    buffer.set_pixel(x + 3, y, (80, 140, 180))
    # Body
    for dx in range(1, 4):
        buffer.set_pixel(x + dx, y + 1, (200, 200, 220))
        buffer.set_pixel(x + dx, y + 2, (200, 200, 220))
    # Legs
    buffer.set_pixel(x, y + 3, (140, 140, 140))
    buffer.set_pixel(x + 4, y + 3, (140, 140, 140))
    buffer.set_pixel(x, y + 4, (180, 180, 180))
    buffer.set_pixel(x + 4, y + 4, (180, 180, 180))
    # Nozzle
    buffer.set_pixel(x + 2, y + 3, (100, 100, 120))


def draw_hud(buffer: PixelBuffer, lander, terrain, config: dict,
             score: int = 0, level: int = 1, lives: int = 3):
    """Draw the heads-up display."""
    ui = config.get('ui', {})
    gameplay = config.get('gameplay', {})
    width = config['game']['width']
    height = config['game']['height']
    hud_color = tuple(ui.get('hud_color', [255, 255, 255]))

    draw_text(buffer, f"SCORE:{score}", 2, 2, hud_color)
    draw_text(buffer, f"LVL:{level}", width - 28, 2, hud_color)

    # Lives: mini ship icon + white count
    lives_x = width - 16
    _draw_mini_ship(buffer, lives_x, 8)
    draw_text(buffer, f"x{lives}", lives_x + 6, 9, (255, 255, 255))

    # Fuel bar
    draw_text(buffer, f"FUEL:{int(lander.fuel)}", 2, 8, (255, 255, 0))
    fuel_bar_width = ui.get('fuel_bar_width', 20)
    fuel_bar_x = 35
    fuel_bar_y = 8
    fuel_pct = lander.fuel / lander.max_fuel
    fuel_amount = int(fuel_pct * fuel_bar_width)

    buffer.draw_rect(fuel_bar_x, fuel_bar_y, fuel_bar_width, 4, (60, 60, 60), filled=True)
    buffer.draw_rect(fuel_bar_x, fuel_bar_y, fuel_bar_width, 4, (100, 100, 100), filled=False)
    if fuel_amount > 0:
        fuel_threshold = ui.get('fuel_low_threshold', 25)
        if lander.fuel > fuel_threshold:
            fuel_color = tuple(ui.get('fuel_ok_color', [255, 255, 0]))
        else:
            fuel_color = tuple(ui.get('fuel_low_color', [255, 0, 0]))
        buffer.draw_rect(fuel_bar_x + 1, fuel_bar_y + 1, max(0, fuel_amount - 1), 2, fuel_color, filled=True)

    # Speed
    speed = lander.get_speed()
    max_safe_speed = gameplay.get('max_safe_speed', 12.0)
    speed_color = tuple(ui.get('safe_speed_color', [0, 255, 0])) if speed <= max_safe_speed else tuple(ui.get('danger_speed_color', [255, 0, 0]))
    draw_text(buffer, f"SPD:{int(speed)}", 2, 14, speed_color)

    # Speed bar
    speed_bar_width = ui.get('speed_bar_width', 20)
    speed_bar_x = 30
    speed_bar_y = 14
    max_display_speed = 40.0
    speed_amount = min(int((speed / max_display_speed) * speed_bar_width), speed_bar_width)

    buffer.draw_rect(speed_bar_x, speed_bar_y, speed_bar_width, 4, (60, 60, 60), filled=True)
    buffer.draw_rect(speed_bar_x, speed_bar_y, speed_bar_width, 4, (100, 100, 100), filled=False)
    if speed_amount > 0:
        buffer.draw_rect(speed_bar_x + 1, speed_bar_y + 1, max(0, speed_amount - 1), 2, speed_color, filled=True)

    # Safe speed marker
    safe_marker_x = speed_bar_x + int((max_safe_speed / max_display_speed) * speed_bar_width)
    if 0 <= safe_marker_x < buffer.width:
        for dy in range(4):
            py = speed_bar_y + dy
            if 0 <= py < buffer.height:
                buffer.set_pixel(safe_marker_x, py, (255, 255, 255))

    # Altitude and angle
    if not lander.crashed and not lander.landed:
        terrain_h = terrain.get_height_at(int(lander.x + lander.width / 2))
        altitude = max(0, lander.get_altitude(terrain_h))
        alt_color = (0, 255, 0) if altitude > 20 else ((255, 255, 0) if altitude > 10 else (255, 0, 0))
        draw_text(buffer, f"ALT:{int(altitude)}", 2, 20, alt_color)

        vy = lander.vy
        if vy > 0:
            descent_color = (255, 100, 100) if vy > max_safe_speed * 0.7 else (255, 200, 100)
            draw_text(buffer, f"V:{int(vy)}", 42, 20, descent_color)
            arrow_x = 60
            for dy in range(3):
                px, py = arrow_x, 21 + dy
                if 0 <= px < buffer.width and 0 <= py < buffer.height:
                    buffer.set_pixel(px, py, descent_color)
        elif vy < -1:
            draw_text(buffer, f"V:{int(vy)}", 42, 20, (100, 255, 100))

        angle_deg = int(math.degrees(lander.angle))
        max_landing_angle = gameplay.get('max_landing_angle', 0.2)
        if abs(lander.angle) <= max_landing_angle:
            ang_color = (0, 255, 0)
        elif abs(lander.angle) <= max_landing_angle * 3:
            ang_color = (255, 255, 0)
        else:
            ang_color = (255, 0, 0)
        draw_text(buffer, f"ANG:{angle_deg}", 2, 26, ang_color)

    draw_text(buffer, "ARROWS/WASD", 2, height - 6, (60, 60, 60))


def draw_level_complete(buffer: PixelBuffer, width: int, height: int,
                        landed_pad, lander, landing_bonus: int):
    """Draw level complete message."""
    cx = width // 2
    cy = height // 2

    buffer.draw_rect(cx - 33, cy - 13, 66, 32, (0, 0, 20), filled=True)

    draw_text(buffer, "LANDED!", cx - 20, cy - 10, (0, 255, 0))

    if landed_pad:
        quality = lander.get_landing_quality()
        quality_colors = {
            "PERFECT!": (255, 255, 0),
            "GREAT!": (200, 255, 100),
            "GOOD": (150, 200, 100),
            "OK": (200, 200, 200)
        }
        draw_text(buffer, quality, cx - 22, cy - 4, quality_colors.get(quality, (255, 255, 0)))
        draw_text(buffer, f"+{landed_pad.points} PTS", cx - 22, cy + 2, (255, 255, 0))
        if landing_bonus > 0:
            draw_text(buffer, f"+{landing_bonus} BONUS", cx - 28, cy + 8, (0, 255, 200))

    draw_text(buffer, "PRESS ENTER", cx - 30, cy + 14, (200, 200, 200))


def draw_game_over(buffer: PixelBuffer, width: int, height: int,
                   score: int, level: int):
    """Draw game over message."""
    cx = width // 2
    cy = height // 2

    # Box sized to wrap the text block with 3px padding
    buffer.draw_rect(cx - 33, cy - 8, 66, 30, (15, 0, 0), filled=True)

    draw_text(buffer, "GAME OVER", cx - 26, cy - 5, (255, 0, 0))
    draw_text(buffer, f"SCORE:{score}", cx - 28, cy + 2, (255, 255, 255))
    draw_text(buffer, f"LEVEL:{level}", cx - 26, cy + 8, (255, 255, 255))
    draw_text(buffer, "PRESS ENTER", cx - 30, cy + 14, (200, 200, 200))
