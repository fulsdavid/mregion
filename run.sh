#!/usr/bin/env bash
set -e
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi
python install_deps.py --venv .venv
python run_app.py
