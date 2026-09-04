"""Entry point for the packaged (PyInstaller) build.

Running the app from source still works via `python -m src.app`
(see launch.bat); this launcher exists so PyInstaller has a top-level
script whose imports resolve the `src` package normally.
"""
from src.app import main

if __name__ == "__main__":
    main()
