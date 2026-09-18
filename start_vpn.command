#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -f ".venv/bin/python3" ]; then
    exec .venv/bin/python3 main.py
else
    exec python3 main.py
fi
