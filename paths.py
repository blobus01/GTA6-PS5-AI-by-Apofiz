"""Where the app writes its data.

Dev checkout: next to the code (as before).
Installed app (APOFIZ_BUNDLED=1, set by the launcher): ~/.ps5-remote or $PS5_REMOTE_HOME,
because the install folder (Program Files / the .app bundle) must stay read-only.
"""
import os
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
BUNDLED = os.environ.get("APOFIZ_BUNDLED") == "1"
DATA_DIR = Path(os.environ.get("PS5_REMOTE_HOME") or Path.home() / ".ps5-remote") if BUNDLED else CODE_DIR
ENV_LOCAL = DATA_DIR / ".env.local"
LOG_DIR = DATA_DIR / "logs"
