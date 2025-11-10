# mregion (refactored)

Modular refactor of the original monolithic script.

## Layout
- mregion/common: shared models and utilities
- mregion/ui: reusable UI widgets & dialogs
- mregion/tabs: feature tabs (Annotate, Train, Analysis)
- mregion/main.py: application entry

## Run
```bash
python -m mregion.main
```

APP_VERSION=1.6.6, RNG_SEED=1337
