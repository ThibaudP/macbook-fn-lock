"""Run GJS lifecycle checks without a display server or a session bus."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
subprocess.run(["gjs", str(ROOT / "tests/extension_harness.js"), str(ROOT)], check=True)
