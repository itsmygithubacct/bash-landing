#!/usr/bin/env python3
"""
Script that reads keypresses using pygame and sends them over a socket.
This runs as a separate process to provide reliable keyboard input.

Usage:
    uv run --with pygame termgfx/pygame_input_module.py --port 12345
"""

import sys
import argparse
import json
import socket
import threading

try:
    import pygame
except ImportError:
    print("pygame is required. Run with:")
    print("    uv run --with pygame termgfx/pygame_input_module.py")
    sys.exit(1)


# Mapping of pygame key constants to friendly names
KEY_NAMES = {
    pygame.K_UP: 'UP_ARROW',
    pygame.K_DOWN: 'DOWN_ARROW',
    pygame.K_LEFT: 'LEFT_ARROW',
    pygame.K_RIGHT: 'RIGHT_ARROW',
    pygame.K_RETURN: 'ENTER',
    pygame.K_KP_ENTER: 'KEYPAD_ENTER',
    pygame.K_ESCAPE: 'ESCAPE',
    pygame.K_SPACE: 'SPACE',
    pygame.K_TAB: 'TAB',
    pygame.K_BACKSPACE: 'BACKSPACE',
    pygame.K_DELETE: 'DELETE',
    pygame.K_INSERT: 'INSERT',
    pygame.K_HOME: 'HOME',
    pygame.K_END: 'END',
    pygame.K_PAGEUP: 'PAGE_UP',
    pygame.K_PAGEDOWN: 'PAGE_DOWN',
    pygame.K_F1: 'F1',
    pygame.K_F2: 'F2',
    pygame.K_F3: 'F3',
    pygame.K_F4: 'F4',
    pygame.K_F5: 'F5',
    pygame.K_F6: 'F6',
    pygame.K_F7: 'F7',
    pygame.K_F8: 'F8',
    pygame.K_F9: 'F9',
    pygame.K_F10: 'F10',
    pygame.K_F11: 'F11',
    pygame.K_F12: 'F12',
    pygame.K_CAPSLOCK: 'CAPS_LOCK',
    pygame.K_NUMLOCK: 'NUM_LOCK',
    pygame.K_SCROLLOCK: 'SCROLL_LOCK',
    pygame.K_LSHIFT: 'LEFT_SHIFT',
    pygame.K_RSHIFT: 'RIGHT_SHIFT',
    pygame.K_LCTRL: 'LEFT_CTRL',
    pygame.K_RCTRL: 'RIGHT_CTRL',
    pygame.K_LALT: 'LEFT_ALT',
    pygame.K_RALT: 'RIGHT_ALT',
    pygame.K_LMETA: 'LEFT_META',
    pygame.K_RMETA: 'RIGHT_META',
    pygame.K_LSUPER: 'LEFT_SUPER',
    pygame.K_RSUPER: 'RIGHT_SUPER',
    pygame.K_PRINT: 'PRINT_SCREEN',
    pygame.K_PAUSE: 'PAUSE',
    pygame.K_MENU: 'MENU',
    # Keypad keys
    pygame.K_KP0: 'KEYPAD_0',
    pygame.K_KP1: 'KEYPAD_1',
    pygame.K_KP2: 'KEYPAD_2',
    pygame.K_KP3: 'KEYPAD_3',
    pygame.K_KP4: 'KEYPAD_4',
    pygame.K_KP5: 'KEYPAD_5',
    pygame.K_KP6: 'KEYPAD_6',
    pygame.K_KP7: 'KEYPAD_7',
    pygame.K_KP8: 'KEYPAD_8',
    pygame.K_KP9: 'KEYPAD_9',
    pygame.K_KP_PERIOD: 'KEYPAD_PERIOD',
    pygame.K_KP_DIVIDE: 'KEYPAD_DIVIDE',
    pygame.K_KP_MULTIPLY: 'KEYPAD_MULTIPLY',
    pygame.K_KP_MINUS: 'KEYPAD_MINUS',
    pygame.K_KP_PLUS: 'KEYPAD_PLUS',
}


def get_key_event_data(event):
    """Convert pygame event to JSON-serializable dict."""
    modifiers = []
    if event.mod & pygame.KMOD_CTRL:
        modifiers.append('CTRL')
    if event.mod & pygame.KMOD_ALT:
        modifiers.append('ALT')
    if event.mod & pygame.KMOD_SHIFT:
        modifiers.append('SHIFT')
    if event.mod & pygame.KMOD_META:
        modifiers.append('META')
    
    # Get key name
    if event.key in KEY_NAMES:
        key_name = KEY_NAMES[event.key]
    elif 32 <= event.key <= 126:
        # Printable ASCII
        char = chr(event.key)
        if event.mod & pygame.KMOD_SHIFT:
            # Handle shifted characters
            shift_map = {
                '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
                '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
                '-': '_', '=': '+', '[': '{', ']': '}', '\\': '|',
                ';': ':', "'": '"', '`': '~', ',': '<', '.': '>',
                '/': '?',
            }
            char = shift_map.get(char, char.upper())
        key_name = char
    else:
        # Use pygame's name
        key_name = pygame.key.name(event.key).upper()
        if not key_name or key_name == 'UNKNOWN':
            key_name = f'KEY_{event.key}'
    
    # Determine event type
    event_type = 'press' if event.type == pygame.KEYDOWN else 'release'
    
    return {
        'type': 'key',
        'key': key_name,
        'event_type': event_type,
        'modifiers': modifiers,
        'scancode': event.scancode
    }


def get_mouse_event_data(event):
    """Convert pygame mouse event to JSON-serializable dict."""
    if event.type == pygame.MOUSEBUTTONDOWN:
        event_type = 'press'
    elif event.type == pygame.MOUSEBUTTONUP:
        event_type = 'release'
    elif event.type == pygame.MOUSEMOTION:
        event_type = 'motion'
    else:
        return None
    
    return {
        'type': 'mouse',
        'event_type': event_type,
        'x': event.pos[0],
        'y': event.pos[1],
        'button': event.button if hasattr(event, 'button') else 0
    }


class InputServer:
    """Socket server that sends pygame input events."""
    
    def __init__(self, port):
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = True
        self.event_queue = []
        self.queue_lock = threading.Lock()
    
    def start_server(self):
        """Start the socket server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(1)
        print(f"Input server listening on port {self.port}", file=sys.stderr)
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


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pygame Input Server')
    parser.add_argument('--port', type=int, default=12345,
                        help='Port to listen on (default: 12345)')
    parser.add_argument('--gui', action='store_true',
                        help='Show the pygame window (hidden by default)')
    args = parser.parse_args()
    
    # Initialize pygame
    pygame.init()
    
    # Create window - either visible or hidden
    if args.gui:
        screen = pygame.display.set_mode((400, 200))
        pygame.display.set_caption("Input Server - Press ESC to quit")
    else:
        # Create a minimal hidden window
        screen = pygame.display.set_mode((1, 1))
        pygame.display.set_caption("Input Server")
        # Hide the window
        import os
        if sys.platform == 'darwin':
            pygame.display.iconify()
        else:
            os.environ['SDL_VIDEO_WINDOW_POS'] = '-1000,-1000'
            screen = pygame.display.set_mode((1, 1))
    
    # Start the socket server
    server = InputServer(args.port)
    try:
        server.start_server()
    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        pygame.quit()
        sys.exit(1)
    
    # Set up font for display (only needed if GUI is shown)
    font = None
    if args.gui:
        font = pygame.font.Font(None, 24)
    
    # Colors
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    GREEN = (0, 255, 0)
    
    last_event_text = ""
    clock = pygame.time.Clock()
    
    print("Input server ready. Waiting for events...", file=sys.stderr)
    sys.stderr.flush()
    
    while server.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                server.running = False
            
            elif event.type == pygame.KEYDOWN:
                event_data = get_key_event_data(event)
                server.send_event(event_data)
                last_event_text = f"Key Down: {event_data['key']}"
                
                # Check for ESC to quit
                if event.key == pygame.K_ESCAPE:
                    server.running = False
            
            elif event.type == pygame.KEYUP:
                event_data = get_key_event_data(event)
                server.send_event(event_data)
                last_event_text = f"Key Up: {event_data['key']}"
            
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                event_data = get_mouse_event_data(event)
                if event_data:
                    server.send_event(event_data)
                    last_event_text = f"Mouse: {event_data['event_type']}"
        
        # Draw the window (only if GUI is shown)
        if args.gui:
            screen.fill(BLACK)
            
            # Draw title
            title = font.render("Pygame Input Server", True, WHITE)
            screen.blit(title, (10, 10))
            
            # Draw status
            status = font.render(f"Port: {args.port}", True, WHITE)
            screen.blit(status, (10, 40))
            
            # Draw last event
            if last_event_text:
                event_text = font.render(f"Last: {last_event_text}", True, GREEN)
                screen.blit(event_text, (10, 80))
            
            # Draw quit hint
            quit_text = font.render("Press ESC to quit", True, WHITE)
            screen.blit(quit_text, (10, 160))
            
            pygame.display.flip()
        
        clock.tick(60)
    
    # Cleanup
    server.close()
    pygame.quit()
    print("Input server stopped", file=sys.stderr)


if __name__ == '__main__':
    main()
