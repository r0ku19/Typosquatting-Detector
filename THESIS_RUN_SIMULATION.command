#!/bin/zsh
set -e
cd "${0:A:h}"

echo "Running standalone thesis simulation..."
.venv/bin/python simulation/thesis_simulation.py
