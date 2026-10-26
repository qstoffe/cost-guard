# FR 000330 — macOS Web Beta launchers and menu-bar Open/Exit

## Outcome and dependencies

After FR000310, provide `macos/Beta/Cost Guard Web.command` and a lightweight Finder `Cost Guard Web.app` launcher backed by the same shared host/lifecycle as Windows. Reuse common code from FR000320 when present; Windows-specific implementation is not a mandatory platform dependency. Preserve the existing root macOS report/Watch launchers and Diagnostics unchanged. Follow FR000290/PLAN.md.

## Required behavior

1. The Finder app is the preferred terminal-free double-click entry. It starts the shared lifecycle helper, which verifies/stops this checkout's old instance, launches a new detached host, waits for the HTTP shell, opens the default browser and exits. A second deliberate launcher invocation must actually request restart, not merely activate an existing application window. The launcher is not a second long-lived server or icon host.
2. Keep the requested `.command` convenience entry and make it delegate to the same behavior. It must exit without an Enter-to-close pause on success. Be honest that Terminal may retain an empty finished window according to user preferences; the `.app` provides the no-Terminal guarantee. Never change global Terminal preferences, kill Terminal, close unrelated windows, or request broad AppleScript/Accessibility automation permission just to hide a window.
3. The background application presents an `NSStatusItem`-style menu-bar icon with **Open Cost Guard** and **Exit Cost Guard**. Open uses the running instance without restart; Exit stops only that instance and removes the icon. Use normal macOS menu interaction, not a required Windows-style right-click. Closing browser tabs does not stop the host.
4. Respect GUI ownership: the macOS status-menu event loop runs on the main thread; the HTTP server and engine must be coordinated without blocking that loop. Prefer the shared pystray/Pillow adapter plus its declared macOS bridge in the managed optional environment. Do not make macOS bridge packages part of the CLI dependency chain. Handle GUI initialization failure visibly and do not leave an unreachable unmanaged server behind.
5. Discover compatible installed Python without assuming Apple supplies a particular executable. Support explicit tested Python/CPU combinations; prefer wheels so users do not need Xcode or a compiler. A lightweight launcher/app wrapper may ship generated source-controlled text/resources, or reproducibly built artifacts through the existing distribution workflow. No user-side Node build or paid signing account is assumed. Document actual Gatekeeper/quarantine/executable-bit limitations without automatically disabling OS protections or claiming unsigned source ZIPs are frictionless.
6. All paths are checkout-relative for assets and user-application-data-relative for environment/state/logs. Source ZIP, clone and move scenarios must fail or recover clearly; never discover and kill another checkout through stale paths. Package preparation precedes stopping an existing healthy instance where possible. First-run dependency download requires the same explicit setup consent as Windows; later installed starts work without downloads.
7. Browser launch failure leaves the menu Open action usable when the host is healthy. Source-change exit, server crash, repeated starts and shutdown timeout use the common lifecycle/error machinery, not platform-specific competing watchers. No login item, launch agent or OS service is installed.

## Acceptance

Native macOS smoke evidence covers Finder double-click, repeated restart, default-browser opening, Open/Exit menu actions, main-thread responsiveness, launcher exit while host remains alive, and the no-Terminal app path. Check the `.command` behavior separately rather than claiming that process exit proves window closure. Test executable metadata/source ZIP handling, paths with spaces/Unicode, supported architectures/Python versions, offline setup failure and code-change cleanup. Show that stable CLI still runs when optional GUI dependencies are missing or Web is broken.

Use synthetic tests for common ownership and failure paths and record native environments actually tested. Do not mark mocked macOS UI interaction as verified. No new permanent release gate, installer service, launch-mode promotion or product version is prescribed.

Reference: https://pystray.readthedocs.io/en/latest/usage.html documents the macOS/main-thread constraint; the implementation must verify the chosen Python bridge and packaged host on real macOS.
