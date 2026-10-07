"""Product version metadata kept in one runtime location."""
VERSION = "80.8"
DISPLAY_VERSION = f"v{VERSION}"
RELEASE_DATE = "2026-10-07"
PRODUCT_NAME = "Cost Guard"


def mode_heading(mode: str) -> str:
    """One product/version/date/mode grammar for startup and Diagnostics."""
    return f"{PRODUCT_NAME} {DISPLAY_VERSION} ({RELEASE_DATE}) — {mode}"
