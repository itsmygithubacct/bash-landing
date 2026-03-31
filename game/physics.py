"""Angular physics model for the lander ship."""

import math


class ShipPhysics:
    """Angular physics model for the lander.

    State:
        x, y       - position
        vx, vy     - linear velocity
        angle      - ship tilt in radians (0 = upright, positive = CW)
        angular_velocity - rad/s
    """

    def __init__(self, x: float, y: float, config: dict = None):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0
        self.angular_velocity = 0.0

        gameplay = config.get('gameplay', {}) if config else {}
        self.thrust_power = gameplay.get('thrust_power', 18.0)
        self.angular_thrust_power = gameplay.get('angular_thrust_power', 3.0)
        self.angular_damping = gameplay.get('angular_damping', 0.92)
        self.max_angle = gameplay.get('max_angle', 1.5708)
        self.max_landing_angle = gameplay.get('max_landing_angle', 0.2)
        self.max_safe_speed = gameplay.get('max_safe_speed', 12.0)
        self.drag_coefficient = gameplay.get('drag_coefficient', 0.998)

    def apply_main_thrust(self, dt: float):
        """Push along the ship's up axis."""
        self.vx += self.thrust_power * math.sin(self.angle) * dt
        self.vy -= self.thrust_power * math.cos(self.angle) * dt

    def apply_rotate_left(self, dt: float):
        self.angular_velocity -= self.angular_thrust_power * dt

    def apply_rotate_right(self, dt: float):
        self.angular_velocity += self.angular_thrust_power * dt

    def update(self, dt: float, gravity: float, side_thrust_active: bool = False):
        """Advance physics by dt seconds."""
        self.vy += gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        if not side_thrust_active:
            self.angular_velocity *= self.angular_damping

        self.angle += self.angular_velocity * dt

        if self.angle > self.max_angle:
            self.angle = self.max_angle
            self.angular_velocity = 0.0
        elif self.angle < -self.max_angle:
            self.angle = -self.max_angle
            self.angular_velocity = 0.0

        self.vx *= self.drag_coefficient
        self.vy *= self.drag_coefficient

    def get_speed(self) -> float:
        return math.sqrt(self.vx ** 2 + self.vy ** 2)

    def can_land_safely(self) -> bool:
        return (self.get_speed() <= self.max_safe_speed
                and abs(self.angle) <= self.max_landing_angle)

    def stop(self):
        self.vx = 0.0
        self.vy = 0.0
        self.angular_velocity = 0.0

    def reset(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0
        self.angular_velocity = 0.0
