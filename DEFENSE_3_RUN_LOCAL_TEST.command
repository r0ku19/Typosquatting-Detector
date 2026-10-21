#!/bin/zsh
set -e
cd "${0:A:h}"

echo "Starting the Chapter 3 local test client..."
.venv/bin/python clients/local_test.py