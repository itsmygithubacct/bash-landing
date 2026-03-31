"""Controls/help scene for Bash Landing."""

import math

from engine.info_scene import InfoMenuScene


class TerminalLanderControlsScene(InfoMenuScene):
    """Controls/help scene showing keybindings and tips."""

    def __init__(self, game, config: dict):
        gameplay = config['gameplay']
        max_land_deg = int(math.degrees(gameplay.get('max_landing_angle', 0.2)))
        max_speed = int(gameplay.get('max_safe_speed', 12))

        content = [
            "BASH LANDING CONTROLS",
            "",
            "UP / W     - Main Thrust",
            "LEFT / A   - Rotate Left",
            "RIGHT / D  - Rotate Right",
            "",
            "OBJECTIVE:",
            "Land safely on the",
            "green landing pads.",
            "",
            "TIPS:",
            "- Watch your speed!",
            f"- Land below {max_speed} speed",
            f"- Land within {max_land_deg} deg tilt",
            "- Thrust follows angle",
            "- Manage your fuel",
            "- Use short bursts",
            "",
            "SCORING:",
            "- Small pads = 100 pts",
            "- Large pads = 50 pts",
            "- PERFECT land = +100",
            "",
            "ESC - Back to Menu",
        ]
        super().__init__(game, title="CONTROLS", content=content)

    def on_close(self):
        """Go back to menu instead of quitting."""
        self.game.set_scene('main_menu')
