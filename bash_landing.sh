#!/bin/bash
# Run Bash Landing game
cd "$(dirname "$0")"
mkdir -p logs
clear
python3 game/main.py "$@" 2>logs/bash_landing_stderr.log
