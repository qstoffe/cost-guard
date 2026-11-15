"""Product intent routing, without importing Web for help or explicit CLI work."""
import os
from pathlib import Path
import subprocess
import sys

from .version import DISPLAY_VERSION


def main():
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print(f"Cost Guard {DISPLAY_VERSION}")
        return 0
    if arguments in (["--help"], ["-h"]):
        print(f"Cost Guard {DISPLAY_VERSION}\n\n"
              "Usage: python src/entrypoints/desktop.py\n"
              "Default: managed Web on Windows/macOS (requires a logged-in desktop).\n"
              "Windows: windows/Cost-Guard-Web.cmd\n"
              "macOS: macos/Cost-Guard-Web.command\n\n"
              "Legacy CLI (also Linux/headless): python src/entrypoints/cli.py [arguments]\n"
              "  python src/entrypoints/cli.py --watch\n"
              "  python src/entrypoints/cli.py <session-id> --watch\n"
              "  python src/entrypoints/cli.py --help\n"
              "Launchers: windows/Legacy/ or macos/Legacy/\n"
              "Explicit old report/date/session/Watch arguments still forward unchanged to CLI.\n"
              "Developer server: python src/entrypoints/web.py --foreground (no browser).")
        return 0
    if arguments:
        # Preserve every explicit legacy argument, including argparse's unknown-flag errors.
        from .bootstrap import main as cli
        return cli()
    root = Path(__file__).resolve().parents[1]
    if sys.platform == "win32":
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run([str(shell), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(root / "src/web/windows_launch.ps1")], check=False)
        return result.returncode
    if sys.platform == "darwin":
        from .web.macos_launch import launch_macos
        return launch_macos(root)
    print("Cost Guard's default Web launcher requires Windows/macOS and a logged-in desktop.\n"
          "Linux/headless: use python src/entrypoints/cli.py [arguments], or developer mode\n"
          "python src/entrypoints/web.py --foreground (no automatic browser).", file=sys.stderr)
    return 2
