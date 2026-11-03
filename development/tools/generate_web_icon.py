"""Regenerate the offline favicon from the canonical dependency-free tray artwork."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.web.tray_icon import favicon_bytes

if __name__ == "__main__":
    (ROOT / "src/web/assets/favicon.ico").write_bytes(favicon_bytes())
