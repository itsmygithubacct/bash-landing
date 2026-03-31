"""Scene system: base scenes, menu scenes, and game scene base."""

from typing import Optional, Callable, List, Tuple

from engine.pixel_buffer import PixelBuffer
from engine.font import draw_text, FONT_BASIC


class Scene:
    """Base class for game scenes."""

    def __init__(self, game: 'Game'):
        self.game = game

    def on_enter(self):
        """Called when scene becomes active."""
        pass

    def on_exit(self):
        """Called when scene is deactivated."""
        pass

    def update(self, dt: float):
        """Update scene logic. dt is seconds since last frame."""
        pass

    def render(self, buffer: PixelBuffer):
        """Render scene to the buffer."""
        pass

    def handle_input(self, input_handler):
        """Handle input for this scene."""
        pass

    def get_text_overlay(self) -> Optional[object]:
        """Return a text overlay object (with apply_to_output method), or None."""
        return None


class MenuItem:
    """Represents a menu item."""

    def __init__(self, text: str, callback: Callable):
        self.text = text
        self.callback = callback


class MenuScene(Scene):
    """A scene that displays a navigable menu."""

    def __init__(self, game, title: str, items: List[MenuItem],
                 bg_color: Tuple[int, int, int] = (0, 0, 50),
                 bg_image=None,
                 text_color: Tuple[int, int, int] = (255, 255, 255)):
        super().__init__(game)
        self.title = title
        self.items = items
        self.selected_index = 0
        self.bg_color = bg_color
        self.bg_image_obj = bg_image
        self.text_color = text_color

    def handle_input(self, input_handler):
        if input_handler.is_key_just_pressed('DOWN_ARROW') or \
           input_handler.is_key_just_pressed('s'):
            self.selected_index = (self.selected_index + 1) % len(self.items)
            input_handler.release_key('DOWN_ARROW')
            input_handler.release_key('s')

        if input_handler.is_key_just_pressed('UP_ARROW') or \
           input_handler.is_key_just_pressed('w'):
            self.selected_index = (self.selected_index - 1) % len(self.items)
            input_handler.release_key('UP_ARROW')
            input_handler.release_key('w')

        if input_handler.is_key_just_pressed('ENTER') or \
           input_handler.is_key_just_pressed('SPACE'):
            self.items[self.selected_index].callback()
            input_handler.release_key('ENTER')
            input_handler.release_key('SPACE')

    def render(self, buffer: PixelBuffer):
        if self.bg_image_obj:
            self.bg_image_obj.draw_to_buffer(buffer)
        else:
            buffer.clear(self.bg_color)

        draw_text(buffer, self.title, 40, 15, self.text_color, center=True, font=FONT_BASIC)

        start_y = 35
        spacing = 8
        menu_x = 4

        for i, item in enumerate(self.items):
            y = start_y + i * spacing
            color = (255, 255, 0) if i == self.selected_index else self.text_color

            if i == self.selected_index:
                draw_text(buffer, ">", menu_x - 4, y, color, font=FONT_BASIC)

            draw_text(buffer, item.text, menu_x, y, color, font=FONT_BASIC)


class GameSceneBase(Scene):
    """Base class for game scenes with pause and game-over handling.

    Provides sound manager integration and standard input handling
    for pause/game-over states.
    """

    def __init__(self, game, sounds_dir: str = "sounds"):
        super().__init__(game)
        self._sounds_dir = sounds_dir
        self._sound_manager = None

    @property
    def sound_manager(self):
        """Lazy-load sound manager to avoid import-time side effects."""
        if self._sound_manager is None:
            from engine.audio.sound_manager import SoundManager
            self._sound_manager = SoundManager(self._sounds_dir)
        return self._sound_manager

    def play_sound(self, sound_name: str):
        self.sound_manager.play(sound_name)

    def handle_pause_input(self, input_handler) -> bool:
        """Check for pause input. Returns True if pause was triggered."""
        if input_handler.is_key_just_pressed('p') or \
           input_handler.is_key_just_pressed('ESCAPE'):
            input_handler.release_key('p')
            input_handler.release_key('ESCAPE')
            self.sound_manager.play_menu_select()
            self.game.set_scene('pause')
            return True
        return False

    def handle_game_over_input(self, input_handler) -> bool:
        """Check for game-over input (return to menu). Returns True if triggered."""
        if input_handler.is_key_just_pressed('RETURN') or \
           input_handler.is_key_just_pressed('ENTER') or \
           input_handler.is_key_just_pressed('SPACE'):
            input_handler.release_key('RETURN')
            input_handler.release_key('ENTER')
            input_handler.release_key('SPACE')
            self.sound_manager.play_menu_select()
            self.game.set_scene('main_menu')
            return True
        return False
