#!/bin/bash
# Play Bash Landing on a remote machine over SSH with local sound.
#
# Usage: ./play-ssh.sh [user@host] [remote-path]
#
# Starts a local audio relay, SSHs with a reverse tunnel so game
# sound streams back to your machine, and cleans up on exit.
#
# Requirements (local):  python3, pyaudio
# Requirements (remote): python3, the game repo

set -euo pipefail

HOST="${1:-opib}"
REMOTE_PATH="${2:-portfolio/bash_landing}"
RELAY_PORT="${AUDIO_RELAY_PORT:-7700}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RELAY_PID=""

cleanup() {
    if [ -n "$RELAY_PID" ]; then
        kill "$RELAY_PID" 2>/dev/null || true
        wait "$RELAY_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Start local audio relay
echo "Starting audio relay on port ${RELAY_PORT}..."
python3 "${SCRIPT_DIR}/audio_relay.py" --port "$RELAY_PORT" &
RELAY_PID=$!
sleep 0.5

# Verify relay started
if ! kill -0 "$RELAY_PID" 2>/dev/null; then
    echo "ERROR: Audio relay failed to start. Is pyaudio installed?" >&2
    exit 1
fi

echo "Connecting to ${HOST}..."
ssh -t \
    -R "${RELAY_PORT}:127.0.0.1:${RELAY_PORT}" \
    "$HOST" \
    "cd ${REMOTE_PATH} && AUDIO_RELAY=127.0.0.1:${RELAY_PORT} ./bash_landing.sh"
