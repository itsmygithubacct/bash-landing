"""Terminal session recorder using asciinema and ffmpeg."""

import subprocess
import sys
import os
import tempfile
import shutil
from typing import Optional, List

from utils.logger import create_game_logger

_logger = create_game_logger("game_recorder")


class GameRecorder:
    """Records terminal sessions and converts to MP4."""

    def __init__(self, output_file: str = "recording.mp4",
                 fps: int = 30, audio_file: Optional[str] = None):
        self.output_file = output_file
        self.fps = fps
        self.audio_file = audio_file
        self.temp_dir = None
        self.cast_file = None

    def check_dependencies(self) -> bool:
        missing = [t for t in ['asciinema', 'ffmpeg'] if not shutil.which(t)]
        if missing:
            print(f"Error: Missing required tools: {', '.join(missing)}", file=sys.stderr)
            return False
        return True

    def start_recording(self, command: List[str]):
        logger = _logger

        if not self.check_dependencies():
            sys.exit(1)

        self.temp_dir = tempfile.mkdtemp(prefix='termgfx_recording_')
        self.cast_file = os.path.join(self.temp_dir, 'session.cast')

        logger.log_info(f"Starting recording to {self.output_file}")

        uses_shell_input = '--shell-input' in command
        if command[0:2] == ['uv', 'run'] and not uses_shell_input:
            command = command[0:2] + ['--with', 'pygame'] + command[2:]

        asciinema_cmd = [
            'asciinema', 'rec', '--overwrite',
            '--command', ' '.join(command),
            self.cast_file
        ]

        try:
            result = subprocess.run(asciinema_cmd)
            if result.returncode == 0:
                self.convert_to_mp4()
            else:
                self.cleanup()
                sys.exit(result.returncode)
        except KeyboardInterrupt:
            self.cleanup()
            sys.exit(1)

    def convert_to_mp4(self):
        logger = _logger

        if not os.path.exists(self.cast_file):
            return

        gif_file = os.path.join(self.temp_dir, 'session.gif')

        if shutil.which('agg'):
            try:
                subprocess.run(['agg', '--fps', str(self.fps), self.cast_file, gif_file],
                             check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self._save_cast_backup()
                return
        else:
            self._save_cast_backup()
            return

        if os.path.exists(gif_file):
            ffmpeg_cmd = ['ffmpeg', '-i', gif_file, '-movflags', 'faststart',
                         '-pix_fmt', 'yuv420p', '-vf', f'fps={self.fps}']
            if self.audio_file and os.path.exists(self.audio_file):
                ffmpeg_cmd.extend(['-i', self.audio_file, '-c:a', 'aac'])
            ffmpeg_cmd.extend(['-y', self.output_file])

            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                print(f"\nRecording saved to: {self.output_file}", file=sys.stderr)
            except subprocess.CalledProcessError as e:
                logger.log_error(f"ffmpeg conversion failed: {e.stderr.decode()}")

        self.cleanup()

    def _save_cast_backup(self):
        cast_backup = self.output_file.replace('.mp4', '.cast')
        shutil.copy(self.cast_file, cast_backup)
        print(f"Cast file saved to: {cast_backup}", file=sys.stderr)
        print(f"Replay with: asciinema play {cast_backup}", file=sys.stderr)

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass


def record_game(game_script: str, output_file: str = "recording.mp4",
                fps: int = 30, audio_file: Optional[str] = None,
                use_shell_input: bool = False, extra_args: List[str] = None):
    """Record a game session."""
    recorder = GameRecorder(output_file, fps, audio_file)

    if use_shell_input:
        command = ['python3', game_script, '--shell-input']
    else:
        command = ['uv', 'run', '--with', 'pygame', game_script]

    if extra_args:
        command.extend(extra_args)

    recorder.start_recording(command)
