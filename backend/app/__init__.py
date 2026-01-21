"""Backend application package."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
DSIM_SRC_DIR = REPO_DIR / "dsim" / "src"

if DSIM_SRC_DIR.exists() and str(DSIM_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(DSIM_SRC_DIR))
