#!/usr/bin/env python3
"""
Shell-based input module that reads keypresses using terminal escape sequences.
Works over SSH/network and doesn't require X11 or a desktop environment.

Usage:
    python termgfx_pixel/shell_input_module.py --port 12345
"""

import sys
import argparse
import json
import socket
import termios
import tty
import select
import os
import fcntl


# Mapping of escape sequences to friendly key names
ESCAPE_SEQUENCES = {
    # Arrow keys (CSI sequences)
    '[A': 'UP_ARROW',
    '[B': 'DOWN_ARROW',
    '[C': 'RIGHT_ARROW',
    '[D': 'LEFT_ARROW',
    # Arrow keys (SS3 sequences - some terminals use these)
    'OA': 'UP_ARROW',
    'OB': 'DOWN_ARROW',
    'OC': 'RIGHT_ARROW',
    'OD': 'LEFT_ARROW',
    # Navigation keys
    '[H': 'HOME',
    '[F': 'END',
    '[1~': 'HOME',
    '[4~': 'END',
    '[2~': 'INSERT',
    '[3~': 'DELETE',
    '[5~': 'PAGE_UP',
    '[6~': 'PAGE_DOWN',
    # Alternate home/end
    '[7~': 'HOME',
    '[8~': 'END',
    # Function keys (SS3 sequences)
    'OP': 'F1',
    'OQ': 'F2',
    'OR': 'F3',
    'OS': 'F4',
    # Function keys (CSI sequences)
    '[11~': 'F1',
    '[12~': 'F2',
    '[13~': 'F3',
    '[14~': 'F4',
    '[15~': 'F5',
    '[17~': 'F6',
    '[18~': 'F7',
    '[19~': 'F8',
    '[20~': 'F9',
    '[21~': 'F10',
    '[23~': 'F11',
    '[24~': 'F12',
    # Shift+arrows
    '[1;2A': 'SHIFT_UP',
    '[1;2B': 'SHIFT_DOWN',
    '[1;2C': 'SHIFT_RIGHT',
    '[1;2D': 'SHIFT_LEFT',
    # Ctrl+arrows
    '[1;5A': 'CTRL_UP',
    '[1;5B': 'CTRL_DOWN',
    '[1;5C': 'CTRL_RIGHT',
    '[1;5D': 'CTRL_LEFT',
    # Alt+arrows
    '[1;3A': 'ALT_UP',
    '[1;3B': 'ALT_DOWN',
    '[1;3C': 'ALT_RIGHT',
    '[1;3D': 'ALT_LEFT',
}

# Special character mappings
SPECIAL_CHARS = {
    '\r': 'ENTER',
    '\n': 'ENTER',
    ' ': 'SPACE',
    '\t': 'TAB',
    '\x7f': 'BACKSPACE',
    '\x08': 'BACKSPACE',
}


class InputBuffer:
    """Buffer for reading and parsing input with escape sequence handling."""
    
    def __init__(self, fd):
        self.fd = fd
        self.buffer = b''
    
    def read_available(self):
        """Read all available bytes from the file descriptor."""
        try:
            # Set non-blocking mode temporarily
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            try:
                while True:
                    chunk = os.read(self.fd, 1024)
                    if not chunk:
                        break
                    self.buffer += chunk
            except (BlockingIOError, OSError):
                pass
            finally:
                # Restore blocking mode
                fcntl.fcntl(self.fd, fcntl.F_SETFL, flags)
        except (OSError, IOError):
            pass
    
    def wait_for_input(self, timeout=0.1):
        """Wait for input to be available."""
        ready, _, _ = select.select([self.fd], [], [], timeout)
        return bool(ready)
    
    def get_next_key(self):
        """
        Parse and return the next key event from the buffer.
        Returns (key_name, modifiers) or (None, None) if no complete key.
        """
        if not self.buffer:
            return None, None
        
        # Try to decode as UTF-8
        try:
            # Check for escape sequence
            if self.buffer[0] == 0x1b:  # ESC
                return self._parse_escape_sequence()
            
            # Check for control characters
            if self.buffer[0] < 32:
                char = self.buffer[0]
                self.buffer = self.buffer[1:]
                return self._parse_control_char(char)
            
            # Check for DEL (backspace on some terminals)
            if self.buffer[0] == 0x7f:
                self.buffer = self.buffer[1:]
                return 'BACKSPACE', []
            
            # Regular character - try to decode UTF-8
            # Find how many bytes this character needs
            first_byte = self.buffer[0]
            if first_byte < 0x80:
                char_len = 1
            elif first_byte < 0xe0:
                char_len = 2
            elif first_byte < 0xf0:
                char_len = 3
            else:
                char_len = 4
            
            if len(self.buffer) >= char_len:
                char_bytes = self.buffer[:char_len]
                self.buffer = self.buffer[char_len:]
                try:
                    char = char_bytes.decode('utf-8')
                    # Map special characters
                    if char in SPECIAL_CHARS:
                        return SPECIAL_CHARS[char], []
                    return char, []
                except UnicodeDecodeError:
                    # Invalid UTF-8, skip this byte
                    return None, None
            else:
                # Need more bytes for this character
                return None, None
                
        except (IndexError, UnicodeDecodeError):
            return None, None
    
    def _parse_escape_sequence(self):
        """Parse an escape sequence from the buffer."""
        if len(self.buffer) < 1:
            return None, None
        
        # Just ESC key alone - need to wait a bit to see if more comes
        if len(self.buffer) == 1:
            # We'll handle this case by returning ESC if no more data comes
            # For now, indicate we need more data
            return None, None
        
        # Check what follows ESC
        second_byte = self.buffer[1]
        
        # CSI sequence: ESC [
        if second_byte == ord('['):
            return self._parse_csi_sequence()
        
        # SS3 sequence: ESC O
        if second_byte == ord('O'):
            return self._parse_ss3_sequence()
        
        # Alt+key: ESC followed by a regular character
        if second_byte >= 32 and second_byte < 127:
            self.buffer = self.buffer[2:]
            char = chr(second_byte)
            if char in SPECIAL_CHARS:
                return SPECIAL_CHARS[char], ['ALT']
            return char, ['ALT']
        
        # Unknown escape sequence, just return ESC
        self.buffer = self.buffer[1:]
        return 'ESCAPE', []
    
    def _parse_csi_sequence(self):
        """Parse a CSI (Control Sequence Introducer) sequence: ESC [ ..."""
        # Find the end of the sequence
        # CSI sequences end with a byte in range 0x40-0x7E (@ to ~)
        end_idx = None
        for i in range(2, min(len(self.buffer), 20)):
            if 0x40 <= self.buffer[i] <= 0x7e:
                end_idx = i
                break
        
        if end_idx is None:
            # Sequence not complete yet
            if len(self.buffer) >= 20:
                # Too long, discard
                self.buffer = self.buffer[1:]
                return 'ESCAPE', []
            return None, None
        
        # Extract the sequence (without ESC)
        seq = self.buffer[1:end_idx + 1].decode('ascii', errors='replace')
        self.buffer = self.buffer[end_idx + 1:]
        
        # Look up the sequence
        if seq in ESCAPE_SEQUENCES:
            key = ESCAPE_SEQUENCES[seq]
            modifiers = []
            if key.startswith('SHIFT_'):
                modifiers.append('SHIFT')
                key = key[6:]  # Remove SHIFT_ prefix
            elif key.startswith('CTRL_'):
                modifiers.append('CTRL')
                key = key[5:]  # Remove CTRL_ prefix
            elif key.startswith('ALT_'):
                modifiers.append('ALT')
                key = key[4:]  # Remove ALT_ prefix
            return key, modifiers
        
        # Unknown CSI sequence
        return None, None
    
    def _parse_ss3_sequence(self):
        """Parse an SS3 (Single Shift 3) sequence: ESC O ..."""
        if len(self.buffer) < 3:
            return None, None
        
        # SS3 sequences are ESC O followed by one character
        seq = self.buffer[1:3].decode('ascii', errors='replace')
        self.buffer = self.buffer[3:]
        
        if seq in ESCAPE_SEQUENCES:
            return ESCAPE_SEQUENCES[seq], []
        
        # Unknown SS3 sequence
        return None, None
    
    def _parse_control_char(self, char):
        """Parse a control character."""
        if char == 0x1b:
            return 'ESCAPE', []
        if char == 0x0d or char == 0x0a:
            return 'ENTER', []
        if char == 0x09:
            return 'TAB', []
        if char == 0x08:
            return 'BACKSPACE', []
        if char == 0x03:
            return 'CTRL_C', ['CTRL']
        
        # Other control characters: Ctrl+A through Ctrl+Z
        if 1 <= char <= 26:
            letter = chr(char + 64)  # Convert to uppercase letter
            return letter, ['CTRL']
        
        return None, None
    
    def force_escape(self):
        """Force interpretation of a lone ESC in the buffer."""
        if len(self.buffer) == 1 and self.buffer[0] == 0x1b:
            self.buffer = b''
            return 'ESCAPE', []
        return None, None


class InputServer:
    """Socket server that sends terminal input events."""
    
    def __init__(self, port):
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = True
        self.old_settings = None
        self.tty_fd = None
    
    def start_server(self):
        """Start the socket server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(1)
        print(f"Shell input server listening on port {self.port}", file=sys.stderr)
        sys.stderr.flush()
        
        # Accept one client connection
        self.client_socket, addr = self.server_socket.accept()
        print(f"Client connected from {addr}", file=sys.stderr)
        sys.stderr.flush()
    
    def send_event(self, event_data):
        """Send an event to the client."""
        if self.client_socket:
            try:
                json_data = json.dumps(event_data) + '\n'
                self.client_socket.sendall(json_data.encode('utf-8'))
            except (BrokenPipeError, ConnectionResetError):
                print("Client disconnected", file=sys.stderr)
                self.running = False
    
    def close(self):
        """Close the server."""
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()


def setup_terminal():
    """Set terminal to raw mode for character-by-character input.
    
    Opens /dev/tty directly to avoid interfering with stdin/stdout
    used by the parent process for rendering.
    """
    try:
        # Open /dev/tty directly for input - this is separate from stdin/stdout
        tty_fd = os.open('/dev/tty', os.O_RDONLY)
        old_settings = termios.tcgetattr(tty_fd)
        
        # Set raw mode on the tty
        new_settings = termios.tcgetattr(tty_fd)
        # Turn off echo, canonical mode, and signal generation
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON | termios.ISIG)
        # Set minimum characters to read and timeout
        new_settings[6][termios.VMIN] = 0
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(tty_fd, termios.TCSANOW, new_settings)
        
        return old_settings, tty_fd
    except (OSError, termios.error) as e:
        print(f"Warning: Could not open /dev/tty, falling back to stdin: {e}", file=sys.stderr)
        # Fallback to stdin
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)
        return old_settings, fd


def restore_terminal(old_settings, tty_fd):
    """Restore terminal to original settings."""
    try:
        termios.tcsetattr(tty_fd, termios.TCSANOW, old_settings)
        if tty_fd != sys.stdin.fileno():
            os.close(tty_fd)
    except (termios.error, OSError):
        pass


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Shell Input Server')
    parser.add_argument('--port', type=int, default=12345,
                        help='Port to listen on (default: 12345)')
    args = parser.parse_args()
    
    # Start the socket server
    server = InputServer(args.port)
    try:
        server.start_server()
    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Set up terminal for raw input
    old_settings, tty_fd = setup_terminal()
    
    print("Shell input server ready. Press Ctrl+C to quit.", file=sys.stderr)
    print("Reading keypresses...", file=sys.stderr)
    sys.stderr.flush()
    
    # Create input buffer
    input_buffer = InputBuffer(tty_fd)
    
    # Track when we last saw input (for ESC key timeout)
    import time
    last_input_time = 0
    esc_timeout = 0.05  # 50ms timeout for escape sequences
    
    try:
        while server.running:
            # Wait for input
            if input_buffer.wait_for_input(0.05):
                input_buffer.read_available()
                last_input_time = time.time()
            
            # Check if we have a lone ESC that's timed out
            if (len(input_buffer.buffer) == 1 and 
                input_buffer.buffer[0] == 0x1b and
                time.time() - last_input_time > esc_timeout):
                key_name, modifiers = input_buffer.force_escape()
                if key_name:
                    event_data = {
                        'type': 'key',
                        'key': key_name,
                        'event_type': 'press',
                        'modifiers': modifiers
                    }
                    server.send_event(event_data)
                    event_data['event_type'] = 'release'
                    server.send_event(event_data)
                continue
            
            # Process all complete keys in the buffer
            while True:
                key_name, modifiers = input_buffer.get_next_key()
                
                if key_name is None:
                    break
                
                # Check for Ctrl+C
                if key_name == 'CTRL_C' or (key_name == 'C' and 'CTRL' in modifiers):
                    print("\nReceived Ctrl+C, shutting down...", file=sys.stderr)
                    server.running = False
                    break
                
                # Send key press event
                event_data = {
                    'type': 'key',
                    'key': key_name,
                    'event_type': 'press',
                    'modifiers': modifiers
                }
                server.send_event(event_data)
                
                # Immediately send key release event
                # (shell input doesn't distinguish between press and release)
                event_data['event_type'] = 'release'
                server.send_event(event_data)
    
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
    
    finally:
        # Restore terminal settings
        restore_terminal(old_settings, tty_fd)
        
        # Cleanup
        server.close()
        print("Shell input server stopped", file=sys.stderr)


if __name__ == '__main__':
    main()
