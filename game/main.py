#!/usr/bin/env python3
"""Bash Landing - A terminal-based lunar lander game.

Land safely on the moon's surface using thrusters to control descent.
Uses ANSI half-block characters for pixel-level rendering in the terminal.
"""

import sys
import os
import json

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import Game
from engine.title_menu import create_title_menu
from game.scene import TerminalLanderGameScene
from game.controls_scene import TerminalLanderControlsScene
from utils.paths import config_path, asset_path
from utils.logger import create_game_logger

_logger = create_game_logger("bash_landing")


def load_config() -> dict:
    """Load game configuration from JSON, merged with defaults."""
    cfg_path = config_path("bash_landing.json")

    default_config = {
        "game": {
            "title": "Bash Landing - Lunar Landing",
            "fps": 60,
            "width": 120,
            "height": 80
        },
        "display": {
            "title_text": "BASH LANDING",
            "background_image": "backgrounds/bash_landing_title.png",
            "sounds_dir": "sounds"
        },
        "controls": {
            "thrust_up": ["UP_ARROW", "w", "W"],
            "thrust_left": ["LEFT_ARROW", "a", "A"],
            "thrust_right": ["RIGHT_ARROW", "d", "D"],
            "pause": "ESCAPE",
            "quit": "q",
            "confirm": ["RETURN", "ENTER", "SPACE"]
        },
        "gameplay": {
            "gravity": 8.0,
            "lander_width": 5,
            "lander_height": 5,
            "initial_fuel": 150.0,
            "min_fuel": 30.0,
            "fuel_decrease_per_level": 5.0,
            "max_safe_speed": 12.0,
            "terrain_base_height": 65,
            "initial_pad_width": 15,
            "min_pad_margin": 2,
            "base_roughness": 8,
            "roughness_increase_rate": 2,
            "base_landing_points": 50,
            "bonus_landing_points": 50,
            "level_complete_delay": 2.0,
            "num_stars": 80,
            "starting_lives": 3,
            "thrust_sound_interval": 0.15,
            "altitude_beep_threshold": 20,
            "fuel_warning_threshold": 25
        },
        "ui": {
            "hud_color": [255, 255, 255],
            "fuel_bar_width": 20,
            "speed_bar_width": 20,
            "safe_speed_color": [0, 255, 0],
            "danger_speed_color": [255, 0, 0],
            "fuel_ok_color": [255, 255, 0],
            "fuel_low_color": [255, 0, 0],
            "fuel_low_threshold": 25
        },
        "menu": {
            "extra_items": [
                {"label": "CONTROLS", "scene": "controls"}
            ]
        }
    }

    try:
        with open(cfg_path, 'r') as f:
            loaded = json.load(f)
            for key in default_config:
                if key not in loaded:
                    loaded[key] = default_config[key]
                elif isinstance(default_config[key], dict):
                    for sub_key in default_config[key]:
                        if sub_key not in loaded[key]:
                            loaded[key][sub_key] = default_config[key][sub_key]
            return loaded
    except FileNotFoundError:
        _logger.log_info("Config file not found, using defaults")
        return default_config
    except json.JSONDecodeError as e:
        _logger.log_error(f"Error parsing config: {e}", e)
        return default_config


def main():
    """Run the Bash Landing game."""
    _logger.log_info("Bash Landing starting")

    config = load_config()

    game_config = config['game']
    game = Game(
        game_config['title'],
        fps=game_config['fps'],
        width=game_config['width'],
        height=game_config['height']
    )

    def setup_args(parser):
        parser.add_argument('--background', metavar='IMAGE_FILE',
                          help='Background image for title screen')
        parser.add_argument('--level', type=int, default=1,
                          help='Starting level (default: 1)')

    game.add_argument_setup(setup_args)
    args = game.parse_args()

    # Title image
    display_config = config['display']
    if args.background:
        title_image_path = args.background
    else:
        title_image_path = asset_path(display_config['background_image'])

    # Create scenes
    game_scene = TerminalLanderGameScene(game, config, start_level=args.level)
    game.add_scene("game", game_scene)

    controls_scene = TerminalLanderControlsScene(game, config)
    game.add_scene("controls", controls_scene)

    # Build menu
    game_menu_items = {1: ("game", None)}
    extra_menu_items = [
        (item['label'], item['scene'])
        for item in config['menu']['extra_items']
    ]

    title_menu = create_title_menu(
        game,
        display_config['title_text'],
        game_menu_items,
        sounds_dir=display_config['sounds_dir'],
        title_image_path=title_image_path,
        extra_menu_items=extra_menu_items
    )

    title_menu.set_initial_scene()
    game.start()


if __name__ == '__main__':
    main()
