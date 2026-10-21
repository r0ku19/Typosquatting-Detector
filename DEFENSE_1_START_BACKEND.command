#!/bin/zsh
set -e
cd "${0:A:h}"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Project environment missing. Install requirements first."
  read -k 1 "?Press any key to close..."
  exit 1
fi

if [[ -z "${MYSQL_PASSWORD:-}" ]]; then
  read -s "MYSQL_PASSWORD?Enter your MySQL password: "
  echo
  export MYSQL_PASSWORD
fi

echo "Starting the Chapter 3 Flask backend..."
./run.sh