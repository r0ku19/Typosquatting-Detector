#!/bin/zsh
cd "${0:A:h}"

open -a "Google Chrome" "chrome://extensions"
echo "Load or reload clients/extension if needed."
read -k 1 "?Press any key to close..."