"""Windows entry point for the installed app (Start Menu / desktop / autostart shortcut).

Runs `python -m launcher` from the install folder with APOFIZ_BUNDLED=1, so child
processes use %LOCALAPPDATA%\\ApofizPlay as their working folder and nothing
from the user's own Python (user site-packages) leaks in.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("APOFIZ_BUNDLED", "1")
os.environ.setdefault("APOFIZ_APP_ROOT", HERE)
os.environ["PYTHONNOUSERSITE"] = "1"
os.chdir(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.argv = ["launcher", *sys.argv[1:]]
runpy.run_module("launcher", run_name="__main__", alter_sys=True)
