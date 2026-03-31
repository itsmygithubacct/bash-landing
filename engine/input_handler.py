"""Input handling via subprocess-based input backends (pygame or shell)."""

from typing import Tuple
import sys
import os
import time
import subprocess
import socket
import json
import select

from utils.paths import INPUT_BACKENDS_DIR
from utils.logger import create_game_logger

_logger = create_game_logger("input_handler")


class InputHandler:
    """Handles input from pygame or shell input backends via socket."""

    def __init__(self, port: int = 12345, use_shell: bool = False):
        self.port = port
        self.use_shell = use_shell
        self.process = None
        self.socket = None
        self.keys_pressed = set()
        self.keys_just_pressed = set()
        self.keys_just_released = set()
        self._deferred_releases = set()
        self.mouse_x = 0
        self.mouse_y = 0
        self.mouse_buttons = set()
        self.mouse_just_pressed = set()
        self.mouse_just_released = set()
        self.buffer = ""
        self._shell_input_tty = None

    def start(self):
        """Start the input module subprocess."""
        logger = _logger

        if self.use_shell:
            input_module_path = os.path.join(INPUT_BACKENDS_DIR, 'shell_input.py')
            logger.log_info(f"Starting shell input module on port {self.port}")

            try:
                self._shell_input_tty = open('/dev/tty', 'r+b', buffering=0)
                self.process = subprocess.Popen(
                    ['python3', input_module_path, '--port', str(self.port)],
                    stdin=self._shell_input_tty,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except (OSError, IOError) as e:
                logger.log_warning(f"Could not open /dev/tty: {e}, using fallback")
                self.process = subprocess.Popen(
                    ['python3', input_module_path, '--port', str(self.port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
        else:
            pygame_module_path = os.path.join(INPUT_BACKENDS_DIR, 'pygame_input.py')
            logger.log_info(f"Starting pygame input module on port {self.port}")
            self.process = subprocess.Popen(
                ['uv', 'run', '--with', 'pygame',
                 pygame_module_path,
                 '--port', str(self.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

        # Wait for server to start
        max_retries = 20
        for attempt in range(max_retries):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect(('localhost', self.port))
                self.socket.setblocking(False)
                input_type = "shell" if self.use_shell else "pygame"
                logger.log_info(f"Connected to {input_type} input server on port {self.port}")
                print(f"Connected to {input_type} input server on port {self.port}", file=sys.stderr)
                return
            except ConnectionRefusedError:
                if self.socket:
                    self.socket.close()
                    self.socket = None
                time.sleep(0.1)

        logger.log_error(f"Failed to connect to input server after {max_retries} attempts")
        input_type = "shell" if self.use_shell else "pygame"
        raise ConnectionRefusedError(
            f"Failed to connect to {input_type} input server after {max_retries} attempts."
        )

    def stop(self):
        """Stop the input handler and cleanup."""
        if self.socket:
            self.socket.close()
        if self.process:
            self.process.terminate()
            self.process.wait()
        if self._shell_input_tty:
            self._shell_input_tty.close()

    def update(self):
        """Update input state. Call once per frame."""
        self.keys_just_pressed.clear()
        self.keys_just_released.clear()
        self.mouse_just_pressed.clear()
        self.mouse_just_released.clear()

        for key in self._deferred_releases:
            if key in self.keys_pressed:
                self.keys_pressed.remove(key)
                self.keys_just_released.add(key)
        self._deferred_releases.clear()

        if not self.socket:
            return

        max_reads = 100
        reads = 0
        while reads < max_reads:
            reads += 1
            try:
                ready, _, _ = select.select([self.socket], [], [], 0)
                if not ready:
                    break
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                self.buffer += data

                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    self._process_event(line)
            except BlockingIOError:
                break
            except (ConnectionResetError, BrokenPipeError, OSError):
                self.socket = None
                break
            except Exception:
                break

    def _process_event(self, line: str):
        """Process a single event line."""
        try:
            event = json.loads(line)

            if event['type'] == 'key':
                key = event['key']
                event_type = event.get('event_type', 'press')

                if event_type == 'press':
                    if key not in self.keys_pressed:
                        self.keys_pressed.add(key)
                        self.keys_just_pressed.add(key)

                elif event_type == 'release':
                    if key in self.keys_pressed:
                        if key in self.keys_just_pressed:
                            self._deferred_releases.add(key)
                        else:
                            self.keys_pressed.remove(key)
                            self.keys_just_released.add(key)

            elif event['type'] == 'mouse':
                self.mouse_x = event['x']
                self.mouse_y = event['y']

                if event['event_type'] == 'press':
                    button = event['button']
                    if button not in self.mouse_buttons:
                        self.mouse_buttons.add(button)
                        self.mouse_just_pressed.add(button)
                elif event['event_type'] == 'release':
                    button = event['button']
                    if button in self.mouse_buttons:
                        self.mouse_buttons.remove(button)
                        self.mouse_just_released.add(button)

        except json.JSONDecodeError:
            pass

    def is_key_pressed(self, key: str) -> bool:
        return key in self.keys_pressed

    def is_key_just_pressed(self, key: str) -> bool:
        return key in self.keys_just_pressed

    def is_key_just_released(self, key: str) -> bool:
        return key in self.keys_just_released

    def release_key(self, key: str):
        """Manually release a key."""
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)
            self.keys_just_released.add(key)
        self._deferred_releases.discard(key)

    def is_mouse_button_pressed(self, button: int) -> bool:
        return button in self.mouse_buttons

    def is_mouse_button_just_pressed(self, button: int) -> bool:
        return button in self.mouse_just_pressed

    def is_mouse_button_just_released(self, button: int) -> bool:
        return button in self.mouse_just_released

    def get_mouse_pos(self) -> Tuple[int, int]:
        return (self.mouse_x, self.mouse_y)
