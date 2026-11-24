"""Worker-only pacing for CPU-heavy archived reports during catch-up."""


def cpu_cooldown(seconds, share):
    """Rest after a completed render to limit its recurring share of one core."""
    return max(0.0, seconds * (1 / share - 1))
