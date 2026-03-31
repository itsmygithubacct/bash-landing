"""Image loading and display for the pixel buffer."""

from typing import Tuple, Optional
from PIL import Image


class BackgroundImage:
    """Loads and displays a background image, scaled to fit the pixel buffer."""

    def __init__(self, filename: str, width: int = 80, height: int = 80):
        self.width = width
        self.height = height
        self.pixels = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]

        try:
            img = Image.open(filename)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            img_width, img_height = img.size
            scale = min(width / img_width, height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            offset_x = (width - new_width) // 2
            offset_y = (height - new_height) // 2

            for y in range(new_height):
                for x in range(new_width):
                    pixel = img.getpixel((x, y))
                    target_x = offset_x + x
                    target_y = offset_y + y
                    if 0 <= target_x < width and 0 <= target_y < height:
                        self.pixels[target_y][target_x] = pixel

        except Exception as e:
            print(f"Warning: Could not load image {filename}: {e}")
            for y in range(height):
                for x in range(width):
                    self.pixels[y][x] = (0, 0, 50)

    def get_pixel(self, x: int, y: int) -> Tuple[int, int, int]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y][x]
        return (0, 0, 0)

    def draw_to_buffer(self, buffer):
        for y in range(min(self.height, buffer.height)):
            for x in range(min(self.width, buffer.width)):
                buffer.set_pixel(x, y, self.pixels[y][x])


def load_background_image(filename: str, width: int = 80, height: int = 80) -> Optional[BackgroundImage]:
    try:
        return BackgroundImage(filename, width, height)
    except Exception:
        return None
