@echo off
IF EXIST .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
python install_deps.py --venv .venv
python run_app.py
