# Project

This repository contains the code you shared. Below are universal setup steps so anyone can run it.

## Quickstart

```bash
git clone <YOUR_REPO_URL>.git
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

Dependencies were inferred by scanning imports across the codebase and written to `requirements.txt`. If you know precise versions, pin them there.

## Running

Explain how to run the application here (replace `run_app.py` with the actual entry point).
If there are environment variables or data files needed, document them here.

## Development

- Use a virtual environment (`python -m venv .venv`).
- Install dev tools (optional): `pip install black ruff pytest`

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-change`
3. Commit your changes: `git commit -m "Describe change"`
4. Push: `git push origin feature/my-change`
5. Open a Pull Request

## License

Choose a license (MIT recommended for simplicity). Add a `LICENSE` file accordingly.

## Publishing to GitHub (one-time)

1. Create a new empty repository on GitHub (no README/gitignore/license).
2. Locally:
   ```bash
   cd <REPO_ROOT>
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-user>/<repo>.git
   git push -u origin main
   ```
3. If the repo already exists with content, use `git pull --rebase origin main` before pushing.


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
