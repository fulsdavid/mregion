# Project

Below are universal setup steps so anyone can run this program.

## Quickstart

```bash
git clone https://github.com/fulsdavid/mregion.git
cd <REPO_NAME>
python3 -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
python install_deps.py --venv .venv
# then run your app/script:
python run_app.py
```

> If you prefer to install into your system/user environment instead of a virtual environment:
>
> ```bash
> python install_deps.py
> ```

## Requirements

Pillow
PyQt6
matplotlib
numpy
pyqtgraph
pyvips
tifffile
torch

## Running

Should be 


## License

MIT

### GUI requirements (PyQt)

This is a desktop GUI. It requires **PyQt6**. Our installer will handle that, but on some systems you may need extra OS packages:

- **macOS:** Xcode Command Line Tools: `xcode-select --install` (if not already installed).
- **Linux (Ubuntu/Debian):** Ensure basic build tools: `sudo apt-get update && sudo apt-get install -y build-essential libgl1`
- **Windows:** No extra steps typically needed.

If you see a Qt platform plugin error (e.g., about "xcb" or "cocoa"), try setting the platform manually:
```bash
QT_QPA_PLATFORM=offscreen python run_app.py   # headless test
QT_QPA_PLATFORM=xcb python run_app.py         # Linux desktop
```
