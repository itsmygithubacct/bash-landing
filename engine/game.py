"""Main game class with scene management and game loop."""

from typing import Optional, Callable, Dict
from collections import deque
import sys
import time
import signal
import argparse

from engine.pixel_buffer import PixelBuffer
from engine.scene import Scene
from engine.input_handler import InputHandler
from engine.font import draw_text
from utils.logger import create_game_logger

_logger = create_game_logger("framework")


class Game:
    """Main game class that manages scenes and the game loop."""

    def __init__(self, title: str = "Game", fps: int = 60,
                 width: int = 80, height: int = 80,
                 input_mode: str = "shell"):
        self.title = title
        self.fps = fps
        self.width = width
        self.height = height
        self.input_mode = input_mode
        self.running = False
        self.buffer = PixelBuffer(width, height)
        self.input_handler = None
        self.current_scene: Optional[Scene] = None
        self.scenes: Dict[str, Scene] = {}
        self.show_framerate = False
        self.frame_times = deque(maxlen=30)
        self.current_fps = 0.0
        self.last_frame_time = None
        self.args = None
        self._custom_args_setup: Optional[Callable] = None
        self._old_terminal_settings = None
        self._frame_count = 0
        self._last_error_frame = -1000

    def add_scene(self, name: str, scene: Scene):
        self.scenes[name] = scene

    def set_scene(self, name: str):
        logger = _logger
        old_scene_name = None

        if self.current_scene:
            for scene_name, scene in self.scenes.items():
                if scene is self.current_scene:
                    old_scene_name = scene_name
                    break
            self.current_scene.on_exit()

        if name not in self.scenes:
            logger.log_error(f"Unknown scene: '{name}'")
            raise KeyError(f"No scene registered with name '{name}'")

        self.current_scene = self.scenes[name]
        logger.log_event("scene_change", f"{old_scene_name} -> {name}")
        self.current_scene.on_enter()

    def add_argument_setup(self, setup_func: Callable):
        """Add a function to set up custom command-line arguments."""
        self._custom_args_setup = setup_func

    def parse_args(self):
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(description=self.title)
        parser.add_argument('--record', metavar='OUTPUT',
                          help='Record gameplay to MP4 file')
        parser.add_argument('--fps', type=int, default=self.fps,
                          help=f'Frames per second (default: {self.fps})')
        parser.add_argument('--record-audio', metavar='AUDIO_FILE',
                          help='Audio file to include in recording')
        parser.add_argument('--framerate', action='store_true',
                          help='Show FPS counter')
        parser.add_argument('--width', type=int, default=self.width,
                          help=f'Buffer width (default: {self.width})')
        parser.add_argument('--height', type=int, default=self.height,
                          help=f'Buffer height (default: {self.height})')
        parser.add_argument('--shell-input', action='store_true', default=True,
                          help='Use shell-based input (default)')
        parser.add_argument('--pygame-input', action='store_true',
                          help='Use pygame-based input (requires X11)')

        if self._custom_args_setup:
            self._custom_args_setup(parser)

        self.args = parser.parse_args()

        if self.args.fps:
            self.fps = self.args.fps
        if self.args.width:
            self.width = self.args.width
        if self.args.height:
            self.height = self.args.height

        self.buffer = PixelBuffer(self.width, self.height)

        if self.args.framerate:
            self.show_framerate = True

        if self.args.record:
            self._start_recording(self.args.record, self.args.record_audio)

        return self.args

    def _start_recording(self, output_file: str, audio_file: Optional[str] = None):
        """Start recording the game session."""
        try:
            from engine.recorder import GameRecorder

            recorder = GameRecorder(output_file, self.fps, audio_file)
            if not recorder.check_dependencies():
                print("Recording disabled due to missing dependencies.", file=sys.stderr)
                return

            current_script = sys.argv[0]
            command = ['uv', 'run', current_script]

            for i, arg in enumerate(sys.argv[1:]):
                if arg == '--record':
                    continue
                if i > 0 and sys.argv[i] == '--record':
                    continue
                if not arg.startswith('--record'):
                    command.append(arg)

            print(f"Starting recording session...", file=sys.stderr)
            recorder.start_recording(command)
            sys.exit(0)

        except ImportError:
            print("Error: recorder module not found", file=sys.stderr)
            sys.exit(1)

    def _update_fps(self, total_frame_time: float):
        self.frame_times.append(total_frame_time)
        avg = sum(self.frame_times) / len(self.frame_times)
        if avg > 0:
            self.current_fps = 1.0 / avg

    def _render_fps(self, buffer: PixelBuffer):
        fps_text = f"{int(self.current_fps)}"
        x = self.width - len(fps_text) * 4 - 2
        draw_text(buffer, fps_text, x, 2, (255, 255, 0))

    def _setup_terminal_for_shell_input(self):
        try:
            import termios
            fd = sys.stdin.fileno()
            self._old_terminal_settings = termios.tcgetattr(fd)
        except (ImportError, Exception):
            self._old_terminal_settings = None

    def _restore_terminal_settings(self):
        if self._old_terminal_settings is not None:
            try:
                import termios
                fd = sys.stdin.fileno()
                termios.tcsetattr(fd, termios.TCSADRAIN, self._old_terminal_settings)
            except (ImportError, Exception):
                pass

    def start(self):
        """Start the game loop."""
        logger = _logger
        logger.log_info(f"Game starting: {self.title}")

        if self.args is None:
            self.parse_args()

        self.running = True

        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(write_through=True)

        def signal_handler(sig, frame):
            logger.log_info("Received interrupt signal, stopping game")
            self.running = False
        signal.signal(signal.SIGINT, signal_handler)

        if self.args and self.args.pygame_input:
            use_shell = False
        elif self.args and self.args.shell_input:
            use_shell = True
        else:
            use_shell = self.input_mode == "shell"

        if use_shell:
            self._setup_terminal_for_shell_input()

        self.input_handler = InputHandler(use_shell=use_shell)

        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

        try:
            self.input_handler.start()
        except Exception as e:
            logger.log_error(f"Failed to start input handler: {e}", e)
            raise

        frame_duration = 1.0 / self.fps
        self.last_frame_time = time.time()
        self._frame_count = 0

        try:
            while self.running:
                frame_start = time.time()
                self._frame_count += 1

                dt = frame_start - self.last_frame_time
                self.last_frame_time = frame_start

                if self._frame_count % 60 == 0:
                    logger.log_frame(self._frame_count, dt)

                if self._frame_count % 300 == 0:
                    sys.stdout.write("\x1b[0m\x1b[2J\x1b[H")
                    sys.stdout.flush()

                try:
                    self.input_handler.update()
                except Exception as e:
                    if self._frame_count - self._last_error_frame > 60:
                        logger.log_error(f"Input update error at frame {self._frame_count}: {e}", e)
                        self._last_error_frame = self._frame_count

                if self.input_handler.is_key_just_pressed('ESCAPE'):
                    self.running = False
                    break

                if self.current_scene:
                    stuck_threshold = 1.0

                    try:
                        t0 = time.time()
                        self.current_scene.handle_input(self.input_handler)
                        elapsed = time.time() - t0
                        if elapsed > stuck_threshold:
                            logger.log_warning(f"handle_input took {elapsed:.2f}s at frame {self._frame_count}")
                    except Exception as e:
                        if self._frame_count - self._last_error_frame > 60:
                            logger.log_error(f"Scene input error at frame {self._frame_count}: {e}", e)
                            self._last_error_frame = self._frame_count

                    try:
                        t0 = time.time()
                        self.current_scene.update(dt)
                        elapsed = time.time() - t0
                        if elapsed > stuck_threshold:
                            logger.log_warning(f"update took {elapsed:.2f}s at frame {self._frame_count}")
                    except Exception as e:
                        if self._frame_count - self._last_error_frame > 60:
                            logger.log_error(f"Scene update error at frame {self._frame_count}: {e}", e)
                            self._last_error_frame = self._frame_count

                    try:
                        t0 = time.time()
                        self.current_scene.render(self.buffer)
                        elapsed = time.time() - t0
                        if elapsed > stuck_threshold:
                            logger.log_warning(f"render took {elapsed:.2f}s at frame {self._frame_count}")
                    except Exception as e:
                        if self._frame_count - self._last_error_frame > 60:
                            logger.log_error(f"Scene render error at frame {self._frame_count}: {e}", e)
                            self._last_error_frame = self._frame_count
                        try:
                            self.buffer.clear((255, 0, 0))
                        except Exception:
                            pass
                else:
                    self.buffer.clear((0, 0, 0))

                if self.show_framerate:
                    try:
                        self._render_fps(self.buffer)
                    except Exception:
                        pass

                try:
                    rendered = self.buffer.render()

                    if self.current_scene:
                        try:
                            text_overlay = self.current_scene.get_text_overlay()
                            if text_overlay is not None:
                                rendered = text_overlay.apply_to_output(rendered)
                        except Exception as e:
                            if self._frame_count - self._last_error_frame > 60:
                                logger.log_error(f"Text overlay error at frame {self._frame_count}: {e}")
                                self._last_error_frame = self._frame_count

                    sys.stdout.write("\x1b[0m\x1b[H")
                    sys.stdout.write(rendered)
                    sys.stdout.write("\x1b[0m")
                    sys.stdout.flush()
                except Exception as e:
                    if self._frame_count - self._last_error_frame > 60:
                        logger.log_error(f"Display error at frame {self._frame_count}: {e}", e)
                        self._last_error_frame = self._frame_count

                elapsed = time.time() - frame_start
                if elapsed < frame_duration:
                    time.sleep(frame_duration - elapsed)

                total_frame_time = time.time() - frame_start
                self._update_fps(total_frame_time)

        except Exception as e:
            logger.log_error(f"Fatal error in game loop: {e}", e)
            raise

        finally:
            logger.log_info(f"Game ending after {self._frame_count} frames")
            self.cleanup()

    def stop(self):
        self.running = False

    def cleanup(self):
        logger = _logger
        logger.log_info("Cleaning up resources")

        if self.input_handler:
            self.input_handler.stop()

        self._restore_terminal_settings()

        sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
        sys.stdout.flush()

        logger.log_info("Cleanup complete")
