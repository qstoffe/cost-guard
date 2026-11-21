# Cost Guard

Cost Guard is a local Web dashboard for OpenCode sessions, prompts, pricing,
Token Mix and quotas. It starts a local Web server and opens your browser.

## Requirements

Requires Python 3.11+ and OpenCode on Windows and macOS.
Use the tray/menu **Exit Cost Guard** action to stop the application.

Keep `cache/` when updating or moving a stopped installation.

While the Web host is running and connected to OpenCode, it gives the visible
page priority and warms other main pages more slowly. Accounts prepares its
four CCost chart periods even before the page is opened. Watch and Mini keep
their independent live updates; individual session details still load on demand.

## Windows

Start [windows/Cost-Guard-Web.cmd](windows/Cost-Guard-Web.cmd).

## macOS

Start [macos/Cost-Guard-Web.command](macos/Cost-Guard-Web.command).

## Legacy

Terminal report and Watch launchers remain available in `windows/Legacy`
and `macos/Legacy`.
