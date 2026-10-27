#!/bin/zsh
set -e
cd "${0:A:h}"

echo "Running calibration and evaluation. This is research-only, not part of the live defense demo."
.venv/bin/python backend/experiment.py research/data/ph_gov_domains.txt --output research/results/results.csv
echo
echo "Finished. Results are in research/results/results.csv."
read -k 1 "?Press any key to close..."