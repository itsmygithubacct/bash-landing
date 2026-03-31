# Bash Landing

A terminal-based lunar lander game rendered with ANSI half-block pixel graphics.

Control a spacecraft and land safely on the moon's surface. Use thrusters to manage
descent speed, angle, and fuel while targeting landing pads for points.

## Features

- 120x80 pixel rendering in the terminal using half-block Unicode characters
- Angular physics with thrust-follows-angle mechanics
- Procedurally generated terrain with difficulty scaling per level
- Twinkling starfield, Earth backdrop, and animated thrust flames
- Sound effects for thrust, landing, crash, and proximity warnings
- Configurable gameplay via JSON config file

## Quick Start

```bash
./bash_landing.sh
```

Or directly:

```bash
python3 game/main.py
```

## Controls

| Key | Action |
|-----|--------|
| UP / W | Main thrust |
| LEFT / A | Rotate left + strafe |
| RIGHT / D | Rotate right + strafe |
| ESC | Pause / Menu |

## Landing Tips

- Keep speed below the safe threshold (green on HUD)
- Keep angle within landing tolerance
- Use short bursts to conserve fuel
- Smaller pads are worth more points

## Configuration

Edit `config/bash_landing.json` to tweak gameplay parameters:

- `gameplay.gravity` - Lunar gravity strength
- `gameplay.initial_fuel` - Starting fuel per level
- `gameplay.max_safe_speed` - Maximum safe landing speed
- `gameplay.max_landing_angle` - Maximum angle for safe landing (radians)

## Dependencies

- Python 3.10+
- PyAudio (for sound effects)
- Pillow (optional, for title screen image)

Install with uv:

```bash
uv pip install pyaudio Pillow
```

## Project Structure

```
bash_landing/
├── engine/              # Reusable game framework
│   ├── audio/           # WAV playback and sound generation
│   ├── pixel_buffer.py  # ANSI half-block rendering
│   ├── font.py          # 3x5 pixel fonts
│   ├── game.py          # Game loop and scene management
│   ├── scene.py         # Scene base classes and menus
│   ├── input_handler.py # Socket-based input from backends
│   ├── info_scene.py    # Scrollable info window
│   ├── title_menu.py    # Title screen menu system
│   └── image_display.py # PNG image loading
├── game/                # Lunar lander game code
│   ├── main.py          # Entry point and config
│   ├── scene.py         # Main gameplay scene
│   ├── hud.py           # Heads-up display rendering
│   ├── lander.py        # Spacecraft with physics and rendering
│   ├── terrain.py       # Procedural terrain generation
│   ├── physics.py       # Angular ship physics model
│   ├── sound_manager.py # Lander sound effects
│   └── controls_scene.py# Controls help screen
├── input_backends/      # Standalone input server processes
│   ├── pygame_input.py  # X11/pygame keyboard input
│   └── shell_input.py   # Raw terminal escape sequence input
├── utils/               # Shared utilities
│   ├── logger.py        # File-based game logging
│   └── paths.py         # Project path resolution
├── config/              # Game configuration
├── assets/              # Images and sound files
└── logs/                # Runtime log files (gitignored)
```

## Input Backends

Two input backends are available:

- **Shell input** (default): Works over SSH, no X11 required. Reads raw terminal
  escape sequences.
- **Pygame input**: Requires X11/desktop. Use `--pygame-input` flag.

## Recording

Record gameplay to video (requires `asciinema` and `ffmpeg`):

```bash
python3 game/main.py --record output.mp4
```
