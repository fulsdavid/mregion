#!/usr/bin/env python3
"""
Bootstrap installer: checks for required packages and installs any missing ones.
Usage:
    python install_deps.py               # installs into current environment
    python install_deps.py --venv .venv  # creates/uses a venv and installs there
"""
import sys, subprocess, os, venv, argparse

REQUIREMENTS = """Pillow
PyQt6
matplotlib
mregion
numpy
pyqtgraph
pyvips
tifffile
torch
""".strip().splitlines()

def run(cmd, env=None):
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, env=env)

def ensure_venv(venv_dir):
    vpy = os.path.join(venv_dir, 'bin', 'python') if os.name != 'nt' else os.path.join(venv_dir, 'Scripts', 'python.exe')
    if not os.path.exists(vpy):
        print(f"Creating virtual environment at {venv_dir} ...")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    return vpy

def pip_install(python, packages):
    cmd = [python, "-m", "pip", "install", "--upgrade", "pip"]
    run(cmd)
    if packages:
        cmd = [python, "-m", "pip", "install", *packages]
        code = run(cmd)
        if code != 0:
            print("Retrying with --no-cache-dir ...")
            run([python, "-m", "pip", "install", "--no-cache-dir", *packages])

def missing_packages():
    missing = []
    for pkg in REQUIREMENTS:
        if not pkg or pkg.startswith("#"):
            continue
        modname = pkg.split('==')[0].split('[')[0].replace('-', '_')
        try:
            __import__(modname)
        except Exception:
            missing.append(pkg)
    return missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venv", help="Path to create/use a virtualenv")
    args = ap.parse_args()

    python = sys.executable
    if args.venv:
        python = ensure_venv(args.venv)

    miss = missing_packages()
    if miss:
        print("Missing packages:", ", ".join(miss))
        pip_install(python, miss)
        miss2 = missing_packages()
        if miss2:
            print("Warning: still missing after install:", ", ".join(miss2))
            sys.exit(1)
    else:
        print("All required packages are already installed.")
    print("Done.")

if __name__ == "__main__":
    main()
