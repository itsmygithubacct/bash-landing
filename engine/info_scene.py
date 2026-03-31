"""Scrollable info window scene with text overlays."""

from typing import List, Tuple, Optional

from engine.pixel_buffer import PixelBuffer
from engine.scene import Scene

# Color scheme
COLORS = {
    'title_bar': (60, 80, 120),
    'title_bar_highlight': (80, 100, 140),
    'title_text': (255, 255, 255),
    'window_bg': (45, 45, 50),
    'window_border_light': (140, 140, 150),
    'window_border_dark': (30, 30, 35),
    'content_bg': (55, 55, 60),
    'content_text': (220, 220, 220),
    'content_text_dim': (160, 160, 170),
    'scrollbar_bg': (40, 40, 45),
    'scrollbar_thumb': (100, 120, 160),
    'highlight': (80, 120, 180),
}


class TextOverlay:
    """Manages text overlays on the rendered pixel output."""

    def __init__(self):
        self.overlays: List[Tuple[int, int, str, Tuple[int, int, int], Tuple[int, int, int]]] = []

    def clear(self):
        self.overlays = []

    def add_text(self, term_row: int, term_col: int, text: str,
                 fg: Tuple[int, int, int], bg: Tuple[int, int, int]):
        self.overlays.append((term_row, term_col, text, fg, bg))

    def apply_to_output(self, rendered: str) -> str:
        if not self.overlays:
            return rendered

        lines = rendered.split('\n')

        for term_row, term_col, text, fg, bg in self.overlays:
            if term_row < 0 or term_row >= len(lines):
                continue

            colored_text = f"\033[38;2;{fg[0]};{fg[1]};{fg[2]}m\033[48;2;{bg[0]};{bg[1]};{bg[2]}m{text}\033[0m"
            lines[term_row] = self._insert_text_at_column(
                lines[term_row], term_col, colored_text, len(text))

        return '\n'.join(lines)

    def _insert_text_at_column(self, line: str, col: int, colored_text: str, text_len: int) -> str:
        result = []
        visible_col = 0
        i = 0
        text_inserted = False
        chars_to_skip = 0

        while i < len(line):
            if line[i] == '\033':
                j = i + 1
                while j < len(line) and line[j] != 'm':
                    j += 1
                if j < len(line):
                    j += 1

                if visible_col == col and not text_inserted:
                    result.append(colored_text)
                    text_inserted = True
                    chars_to_skip = text_len

                if chars_to_skip <= 0:
                    result.append(line[i:j])
                i = j
            else:
                if visible_col == col and not text_inserted:
                    result.append(colored_text)
                    text_inserted = True
                    chars_to_skip = text_len

                if chars_to_skip > 0:
                    chars_to_skip -= 1
                else:
                    result.append(line[i])
                visible_col += 1
                i += 1

        if not text_inserted:
            while visible_col < col:
                result.append(' ')
                visible_col += 1
            result.append(colored_text)

        return ''.join(result)


def wrap_text(text: str, max_width: int) -> List[str]:
    """Wrap text to fit within max_width characters."""
    if max_width <= 0 or len(text) <= max_width:
        return [text]

    leading_spaces = len(text) - len(text.lstrip())
    indent = text[:leading_spaces]

    lines = []
    remaining = text

    while remaining:
        if len(remaining) <= max_width:
            lines.append(remaining)
            break

        last_space = remaining.rfind(' ', 0, max_width + 1)
        if last_space > 0:
            lines.append(remaining[:last_space])
            remaining = remaining[last_space + 1:]
        else:
            lines.append(remaining[:max_width])
            remaining = remaining[max_width:]

        if remaining and indent:
            remaining = indent + remaining

    return lines


class InfoWindow:
    """A scrollable info window with title bar and scrollbar."""

    def __init__(self, x: int, y: int, width: int, height: int, title: str = "Information"):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title

        self._raw_lines: List[Tuple[str, Tuple[int, int, int]]] = []
        self.lines: List[Tuple[str, Tuple[int, int, int]]] = []
        self.scroll_offset = 0

        self.title_bar_height = 12
        self.border_width = 2
        self.padding = 4
        self.scrollbar_width = 1

        self.content_x = self.x + self.border_width + self.padding
        self.content_y = self.y + self.title_bar_height + self.padding
        self.content_width = self.width - (self.border_width * 2) - (self.padding * 2) - self.scrollbar_width
        self.content_height = self.height - self.title_bar_height - self.border_width - (self.padding * 2)

        self.visible_lines = self.content_height // 2
        self.max_chars = (self.content_width - 4) // 1

        self.text_overlay = TextOverlay()

    def _rewrap_content(self):
        self.lines = []
        for text, color in self._raw_lines:
            for wrapped_line in wrap_text(text, self.max_chars):
                self.lines.append((wrapped_line, color))

    def set_content(self, lines: List[str], color: Tuple[int, int, int] = None):
        if color is None:
            color = COLORS['content_text']
        self._raw_lines = [(line, color) for line in lines]
        self._rewrap_content()
        self.scroll_offset = 0

    def add_line(self, text: str, color: Tuple[int, int, int] = None):
        if color is None:
            color = COLORS['content_text']
        self._raw_lines.append((text, color))
        for wrapped_line in wrap_text(text, self.max_chars):
            self.lines.append((wrapped_line, color))

    def add_header(self, text: str):
        self._raw_lines.append((text, COLORS['highlight']))
        for wrapped_line in wrap_text(text, self.max_chars):
            self.lines.append((wrapped_line, COLORS['highlight']))

    def add_separator(self):
        sep = "\u2500" * min(40, self.max_chars)
        self._raw_lines.append((sep, COLORS['content_text_dim']))
        self.lines.append((sep, COLORS['content_text_dim']))

    def add_blank(self):
        self._raw_lines.append(("", COLORS['content_text']))
        self.lines.append(("", COLORS['content_text']))

    def scroll_up(self):
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        max_scroll = max(0, len(self.lines) - self.visible_lines)
        if self.scroll_offset < max_scroll:
            self.scroll_offset += 1

    def page_up(self):
        self.scroll_offset = max(0, self.scroll_offset - self.visible_lines)

    def page_down(self):
        max_scroll = max(0, len(self.lines) - self.visible_lines)
        self.scroll_offset = min(max_scroll, self.scroll_offset + self.visible_lines)

    def _draw_3d_border(self, buffer: PixelBuffer, x: int, y: int, w: int, h: int, inset: bool = False):
        light = COLORS['window_border_dark'] if inset else COLORS['window_border_light']
        dark = COLORS['window_border_light'] if inset else COLORS['window_border_dark']
        buffer.draw_line(x, y, x + w - 1, y, light)
        buffer.draw_line(x, y, x, y + h - 1, light)
        buffer.draw_line(x, y + h - 1, x + w - 1, y + h - 1, dark)
        buffer.draw_line(x + w - 1, y, x + w - 1, y + h - 1, dark)

    def draw(self, buffer: PixelBuffer):
        self.text_overlay.clear()

        buffer.draw_rect(self.x, self.y, self.width, self.height,
                        COLORS['window_bg'], filled=True)
        self._draw_3d_border(buffer, self.x, self.y, self.width, self.height)

        # Title bar gradient
        for ty in range(self.y + 2, self.y + self.title_bar_height):
            t = (ty - self.y - 2) / (self.title_bar_height - 4)
            r = int(COLORS['title_bar'][0] * (1 - t * 0.3) + COLORS['title_bar_highlight'][0] * t * 0.3)
            g = int(COLORS['title_bar'][1] * (1 - t * 0.3) + COLORS['title_bar_highlight'][1] * t * 0.3)
            b = int(COLORS['title_bar'][2] * (1 - t * 0.3) + COLORS['title_bar_highlight'][2] * t * 0.3)
            buffer.draw_line(self.x + 2, ty, self.x + self.width - 3, ty, (r, g, b))

        # Title text overlay
        title_term_row = (self.y + 4) // 2
        title_term_col = self.x + (self.width - len(self.title)) // 2
        self.text_overlay.add_text(title_term_row, title_term_col, self.title,
                                   COLORS['title_text'], COLORS['title_bar'])

        # Content area
        ca_x = self.x + self.border_width
        ca_y = self.y + self.title_bar_height
        ca_w = self.width - (self.border_width * 2) - self.scrollbar_width
        ca_h = self.height - self.title_bar_height - self.border_width

        buffer.draw_rect(ca_x, ca_y, ca_w, ca_h, COLORS['content_bg'], filled=True)
        self._draw_3d_border(buffer, ca_x, ca_y, ca_w, ca_h, inset=True)

        # Content text overlays
        content_start_row = (self.content_y + 2) // 2
        content_start_col = self.content_x + 1

        for i in range(self.visible_lines):
            line_idx = self.scroll_offset + i
            if line_idx >= len(self.lines):
                break
            text, color = self.lines[line_idx]
            display_text = text[:self.max_chars] if len(text) > self.max_chars else text
            self.text_overlay.add_text(content_start_row + i, content_start_col,
                                       display_text, color, COLORS['content_bg'])

        self._draw_scrollbar(buffer)

    def _draw_scrollbar(self, buffer: PixelBuffer):
        sb_x = self.x + self.width - self.scrollbar_width - self.border_width
        sb_y = self.y + self.title_bar_height
        sb_height = self.height - self.title_bar_height - self.border_width

        buffer.draw_rect(sb_x, sb_y, self.scrollbar_width, sb_height,
                        COLORS['scrollbar_bg'], filled=True)

        if len(self.lines) <= self.visible_lines:
            thumb_height = sb_height
            thumb_y = sb_y
        else:
            visible_ratio = self.visible_lines / len(self.lines)
            thumb_height = max(2, int(sb_height * visible_ratio))
            scroll_range = len(self.lines) - self.visible_lines
            scroll_ratio = self.scroll_offset / scroll_range if scroll_range > 0 else 0
            track_space = sb_height - thumb_height
            thumb_y = sb_y + int(track_space * scroll_ratio)

        buffer.draw_rect(sb_x, thumb_y, self.scrollbar_width, thumb_height,
                        COLORS['scrollbar_thumb'], filled=True)

    def get_text_overlay(self) -> TextOverlay:
        return self.text_overlay


class InfoMenuScene(Scene):
    """Scene that displays a scrollable info window.

    Subclasses can override ``on_close()`` to change what happens when
    the user presses ESC/q (default: stop the game).
    """

    def __init__(self, game, title: str = "Information", content: List[str] = None):
        super().__init__(game)
        self.title = title
        self.initial_content = content or []
        self.window: Optional[InfoWindow] = None

    def on_enter(self):
        margin = 4
        width = self.game.width - (margin * 2)
        height = self.game.height - (margin * 2)

        self.window = InfoWindow(margin, margin, width, height, self.title)

        for line in self.initial_content:
            if line.startswith("# "):
                self.window.add_header(line[2:])
            elif line == "---":
                self.window.add_separator()
            elif line == "":
                self.window.add_blank()
            else:
                self.window.add_line(line)

    def handle_input(self, input_handler):
        if not self.window:
            return

        if input_handler.is_key_pressed('UP_ARROW') or input_handler.is_key_pressed('w'):
            self.window.scroll_up()
        if input_handler.is_key_pressed('DOWN_ARROW') or input_handler.is_key_pressed('s'):
            self.window.scroll_down()

        if input_handler.is_key_just_pressed('PAGE_UP'):
            self.window.page_up()
            input_handler.release_key('PAGE_UP')
        if input_handler.is_key_just_pressed('PAGE_DOWN'):
            self.window.page_down()
            input_handler.release_key('PAGE_DOWN')

        if input_handler.is_key_just_pressed('ESCAPE') or input_handler.is_key_just_pressed('q'):
            input_handler.release_key('ESCAPE')
            input_handler.release_key('q')
            self.on_close()

    def on_close(self):
        """Called when ESC/q is pressed. Override to customize."""
        self.game.stop()

    def update(self, dt: float):
        pass

    def render(self, buffer: PixelBuffer):
        if not self.window:
            return
        buffer.clear((20, 20, 25))
        self.window.draw(buffer)

    def get_text_overlay(self) -> Optional[TextOverlay]:
        if self.window:
            return self.window.get_text_overlay()
        return None
