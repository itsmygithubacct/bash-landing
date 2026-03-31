"""Pixel buffer with ANSI half-block rendering.

Uses half-block characters to achieve double vertical resolution.
An 80x40 terminal provides an 80x80 pixel canvas.
"""

from typing import Tuple, Optional, List
import sys


class PixelBuffer:
    """A pixel buffer that renders using half-block characters.

    Each terminal character represents 2 vertical pixels using the
    upper half-block character (U+2580).
    """

    def __init__(self, width: int = 80, height: int = 80):
        if height % 2 != 0:
            raise ValueError("Height must be even for half-block rendering")

        self.width = width
        self.height = height
        self.char_height = height // 2

        self._pixels: List[List[Tuple[int, int, int]]] = [
            [(0, 0, 0) for _ in range(width)] for _ in range(height)
        ]
        self._color_cache: dict = {}

    @property
    def pixels(self):
        return self._pixels

    def clear(self, color: Tuple[int, int, int] = (0, 0, 0)):
        """Clear the buffer to a specific color."""
        template = [color] * self.width
        for y in range(self.height):
            self._pixels[y] = template[:]

    def set_pixel(self, x: int, y: int, color: Tuple[int, int, int]):
        """Set a pixel to a specific color (bounds-checked)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._pixels[y][x] = color

    def set_pixel_fast(self, x: int, y: int, color: Tuple[int, int, int]):
        """Set a pixel without bounds checking."""
        self._pixels[y][x] = color

    def get_pixel(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """Get the color of a pixel, or None if out of bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self._pixels[y][x]
        return None

    def render(self) -> str:
        """Render the pixel buffer to an ANSI string."""
        output = []
        line_parts = []
        pixels = self._pixels
        width = self.width
        color_cache = self._color_cache
        cache_get = color_cache.get
        render_hb = self._render_half_block

        for row in range(self.char_height):
            line_parts.clear()
            top_row = pixels[row * 2]
            bottom_row = pixels[row * 2 + 1]

            for x in range(width):
                key = (top_row[x], bottom_row[x])
                cached = cache_get(key)
                if cached is not None:
                    line_parts.append(cached)
                else:
                    char_str = render_hb(key[0], key[1])
                    if len(color_cache) < 10000:
                        color_cache[key] = char_str
                    line_parts.append(char_str)

            output.append(''.join(line_parts))

        return '\n'.join(output)

    def _render_half_block(self, top_color: Tuple[int, int, int],
                           bottom_color: Tuple[int, int, int]) -> str:
        """Render a single half-block character with two colors."""
        if top_color == bottom_color:
            r, g, b = top_color
            return f"\x1b[48;2;{r};{g};{b}m \x1b[0m"

        tr, tg, tb = top_color
        br, bg, bb = bottom_color
        return f"\x1b[38;2;{tr};{tg};{tb};48;2;{br};{bg};{bb}m\u2580\x1b[0m"

    def draw_line(self, x0: int, y0: int, x1: int, y1: int,
                  color: Tuple[int, int, int]):
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        while True:
            self.set_pixel(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def draw_rect(self, x: int, y: int, width: int, height: int,
                  color: Tuple[int, int, int], filled: bool = False):
        """Draw a rectangle."""
        if filled:
            for dy in range(height):
                for dx in range(width):
                    self.set_pixel(x + dx, y + dy, color)
        else:
            for dx in range(width):
                self.set_pixel(x + dx, y, color)
                self.set_pixel(x + dx, y + height - 1, color)
            for dy in range(height):
                self.set_pixel(x, y + dy, color)
                self.set_pixel(x + width - 1, y + dy, color)

    def draw_circle(self, cx: int, cy: int, radius: int,
                    color: Tuple[int, int, int], filled: bool = False):
        """Draw a circle using midpoint circle algorithm."""
        if filled:
            for y in range(cy - radius, cy + radius + 1):
                for x in range(cx - radius, cx + radius + 1):
                    dx = x - cx
                    dy = y - cy
                    if dx * dx + dy * dy <= radius * radius:
                        self.set_pixel(x, y, color)
        else:
            x = 0
            y = radius
            d = 1 - radius
            self._draw_circle_points(cx, cy, x, y, color)
            while x < y:
                if d < 0:
                    d += 2 * x + 3
                else:
                    d += 2 * (x - y) + 5
                    y -= 1
                x += 1
                self._draw_circle_points(cx, cy, x, y, color)

    def _draw_circle_points(self, cx: int, cy: int, x: int, y: int,
                            color: Tuple[int, int, int]):
        """Draw 8 symmetric points of a circle."""
        for px, py in [
            (cx + x, cy + y), (cx - x, cy + y),
            (cx + x, cy - y), (cx - x, cy - y),
            (cx + y, cy + x), (cx - y, cy + x),
            (cx + y, cy - x), (cx - y, cy - x),
        ]:
            self.set_pixel(px, py, color)

    def display(self):
        """Display the buffer to the terminal."""
        sys.stdout.write("\x1b[2J\x1b[H\x1b[?25l")
        sys.stdout.write(self.render())
        sys.stdout.write("\x1b[0m")
        sys.stdout.flush()
