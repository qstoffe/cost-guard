"""Actionable source-error guidance without raw schemas, URLs or exception text."""
from __future__ import annotations


def source_error_message(category: str, generation: str, retryable: bool, detail: str, *, watching: bool = False) -> tuple[str, str]:
    code = category
    if generation == "v1":
        if code == "unsupported_schema":
            return ("Cost Guard - OpenCode V1 incompatible",
                    "The selected legacy V1 history format is not supported.\n"
                    "Check the installed OpenCode version and the configured V1 source.")
        return ("Cost Guard - OpenCode V1 unavailable",
                "The selected legacy V1 history cannot be read.\n"
                "Start your V1 installation and check its history location and permissions.")
    if retryable:
        action = "Watch will reconnect automatically." if watching else "Then run Cost Guard again."
        return ("Cost Guard - OpenCode unavailable",
                "Could not connect to the OpenCode V2 background service.\n\n"
                "If you use OpenCode Desktop V2, start OpenCode Desktop once after\n"
                "starting your computer. This starts the background service, which\n"
                "may continue running after the Desktop application is closed.\n\n" + action)
    if code == "unsupported_version":
        return ("Cost Guard - OpenCode incompatible",
                "The registered OpenCode service version is not supported.\n"
                "Check that a supported OpenCode V2 installation is running.")
    if code == "registration_invalid":
        return ("Cost Guard - OpenCode registration invalid",
                "OpenCode V2 service registration is invalid or unsupported.\n"
                "Restart OpenCode normally; do not edit its service registration.")
    if code == "http_auth_failure":
        return ("Cost Guard - OpenCode access denied",
                "The OpenCode service rejected authentication or authorization.\n"
                "Restart OpenCode normally and use Diagnostics to check service access.")
    if code == "unsupported_schema":
        return ("Cost Guard - OpenCode incompatible",
                "The OpenCode API or history format is not supported.\n"
                "Check the installed version and run Diagnostics for compatibility evidence.")
    if generation == "v2":
        return ("Cost Guard - OpenCode source failure",
                "OpenCode V2 could not provide a complete readable history.\n"
                "Run Diagnostics for the failure category and operation phase.")
    return ("Cost Guard - Runtime error", detail)


def source_wait_message(requested: str) -> str:
    if requested == "v1":
        return "Watch: Waiting for OpenCode V1 history - retrying every 5s (Ctrl+C to stop)"
    return ("Watch: Waiting for OpenCode V2 - start OpenCode Desktop if needed - "
            "retrying every 5s (Ctrl+C to stop)")
