"""Title screen menu system with player selection support."""

from typing import Optional, Dict, Tuple, List
import os

from engine.scene import Scene, MenuItem, MenuScene

try:
    from engine.image_display import BackgroundImage
except ImportError:
    BackgroundImage = None


class GameTitleMenu:
    """Reusable title menu system for games.

    Handles player selection, custom menu items, and scene management.
    """

    def __init__(self, game, title: str,
                 game_scenes: Dict[int, Tuple[str, Optional[Scene]]],
                 sounds_dir: Optional[str] = None,
                 title_image=None,
                 title_image_path: Optional[str] = None,
                 extra_menu_items: Optional[List[Tuple[str, str]]] = None,
                 bg_color: Tuple[int, int, int] = (0, 0, 50),
                 text_color: Tuple[int, int, int] = (255, 255, 255)):
        self.game = game
        self.title = title
        self.game_scenes = game_scenes
        self.bg_color = bg_color
        self.text_color = text_color
        self.extra_menu_items = extra_menu_items or []

        # Load title image
        if title_image:
            self.title_image = title_image
        elif title_image_path and BackgroundImage and os.path.exists(title_image_path):
            try:
                self.title_image = BackgroundImage(
                    filename=title_image_path,
                    width=game.width,
                    height=game.height
                )
            except Exception:
                self.title_image = None
        else:
            self.title_image = None

        # Sound manager (lazy)
        self.sound_manager = None
        if sounds_dir:
            from engine.audio.sound_manager import SoundManager
            self.sound_manager = SoundManager(sounds_dir)

        # Register game scenes
        for player_count, (scene_name, scene) in game_scenes.items():
            if scene is not None:
                game.add_scene(scene_name, scene)

        self._create_menu_scenes()

    def _create_menu_scenes(self):
        if len(self.game_scenes) == 1:
            player_count = list(self.game_scenes.keys())[0]
            scene_name = self.game_scenes[player_count][0]
            menu_items = [
                MenuItem("START GAME", lambda s=scene_name: self._start_game(s))
            ]
        else:
            menu_items = [
                MenuItem("PLAY", lambda: self.game.set_scene("player_select"))
            ]

        for label, target_scene in self.extra_menu_items:
            menu_items.append(
                MenuItem(label, lambda s=target_scene: self.game.set_scene(s))
            )

        menu_items.append(MenuItem("QUIT", lambda: self.game.stop()))

        main_menu = MenuScene(
            self.game, self.title, menu_items,
            bg_color=self.bg_color,
            bg_image=self.title_image,
            text_color=self.text_color
        )
        self.game.add_scene("main_menu", main_menu)

        if len(self.game_scenes) > 1:
            self._create_player_select_menu()

    def _create_player_select_menu(self):
        player_items = []
        for player_count in sorted(self.game_scenes.keys()):
            scene_name = self.game_scenes[player_count][0]
            label = f"{player_count} PLAYER" if player_count == 1 else f"{player_count} PLAYERS"
            player_items.append(
                MenuItem(label, lambda s=scene_name: self._start_game(s))
            )

        player_items.append(MenuItem("BACK", lambda: self.game.set_scene("main_menu")))

        player_select = MenuScene(
            self.game, "SELECT PLAYERS", player_items,
            bg_color=self.bg_color,
            bg_image=self.title_image,
            text_color=self.text_color
        )
        self.game.add_scene("player_select", player_select)

    def _start_game(self, scene_name: str):
        if self.sound_manager:
            self.sound_manager.play_menu_select()
        self.game.set_scene(scene_name)

    def set_initial_scene(self):
        self.game.set_scene("main_menu")


def create_title_menu(game, title, game_scenes, **kwargs):
    """Convenience function to create a GameTitleMenu."""
    return GameTitleMenu(game=game, title=title, game_scenes=game_scenes, **kwargs)
