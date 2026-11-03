"""Root launcher delegating to the modular Streamlit application."""

import runpy
from pathlib import Path
import sys


root = Path(__file__).resolve().parent
src = root / "src"
if src.is_dir() and str(src) not in sys.path:
    sys.path.insert(0, str(src))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

runpy.run_path(str(root / "app" / "app.py"), run_name="__main__")
