# OpenCode connectivity and safe troubleshooting

## Start Desktop V2 once after starting your computer

If you use OpenCode Desktop V2 on Windows, macOS or another supported platform,
launch Desktop once after starting your computer. This starts its background
service, which **may** continue running after the Desktop application closes.
Cost Guard does not launch Desktop or guarantee the service will stay running.
An unreachable service alone does not mean OpenCode is uninstalled.

A normal report reports **OpenCode unavailable**, explains this prerequisite and
returns non-zero if recovery fails. Start Desktop, then run the report again.
Missing installation, invalid registration, access denied, unsupported versions
and incompatible history have distinct guidance. A leftover incompatible V1
database is not evidence that your V2 installation is broken.

Healthy selection and reads do not wait. Reports share a short read-only recovery
budget: at most three failed acquisition attempts, half-second retry spacing and
four seconds of recovery time after the first retryable failure. Startup discovery
uses one-second HTTP timeouts; retries refresh registration and discard uncertain
catalog/connection state. One supported CLI service wake (`opencode api get
/api/info`, up to 20 seconds) remains separate and runs at most once. There is no
repeated CLI startup. Unsupported contracts and authorization failures are not
retried as network outages; brief HTTP 502/503/504 readiness failures can retry.

`auto` still selects one healthy source, preferring V2 with established V1
fallback. Explicit `v1`/`v2` never silently switches. Histories are never merged.

## Watch waits and recovers

Before selection, Watch waits at approximately five-second intervals and suggests
starting Desktop when appropriate. Ctrl+C stops only Watch. Cache, accounts and
pricing are not repeatedly constructed during this wait.

If initial catalog/snapshot/local-usage reads fail, the existing coordinator waits
and starts again from fresh authoritative observations. Partial rows and run
accounting are discarded; account work begins only after source acquisition.
After initialization, connection loss keeps the last valid dashboard visible,
marks reconnecting status and retries the same selected source. Recovery resyncs
snapshots and restarts its event stream; outages never prove completion or abort.
Quotas keep their own cadence. Incompatible schemas are terminal; unreadable or
concurrently changing data gets the existing bounded (~one-minute) recovery.
No partial or inconsistent histories are accepted.

## Local HTTP is not external HTTPS

OpenCode V2 uses registered **loopback HTTP**, without ambient HTTP proxies.
Pricing/release metadata uses **external HTTPS**, with normal certificate checks.
An internet outage or external TLS error does not by itself explain localhost
failures. Cached metadata may remain usable while external acquisition is degraded.

Use `development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd` on Windows,
`development/user-tools/diagnostics/macos/Cost Guard Diagnostics.command` on macOS, or
`python development/tools/collect_diagnostics.py` from the repository root.
Review the bundle before sharing. It records bounded categories, phases, exception
types, counts, durations, registration/health observations, transport counters,
metadata backoff, cache/live origin and independent probe outcomes. Recovered
source incidents remain available for later runs (24 transitions, 30 days),
including after a bundle is created. No endpoint URL, auth, prompt, title or raw
HTTP payload is collected by the new connection evidence. ZIP creation and
validation/test results are independent.

Certificate verification failures are distinct from other TLS failures. Compare
source/category timestamps and last successes: failures close together suggest
correlation, **not** a confirmed common cause.

## Observe before changing anything

Possible contributors include service restarts/process termination, resource
contention, antivirus web protection or EDR, VPN clients, loopback firewall rules,
corporate proxies/HTTPS inspection, certificate trust and system clock/certificate
validity. These are hypotheses until supported by evidence.

- Check whether Desktop/service is running and whether normal Desktop operation
  restores local reads. Cost Guard never edits registration or stops OpenCode.
- Compare Diagnostics categories with independently observed connectivity and
  existing security-product/service event logs at the same time. Avoid collecting
  unrelated inventories or confidential log content.
- For external certificate errors, verify clock/date and consult your administrator
  about the required trusted certificate/proxy configuration. External success
  later does not disprove an earlier transient failure.

Do not disable certificate validation, ignore TLS failures or routinely disable
endpoint protection. Do not add broad exclusions or change system-wide proxy,
firewall or certificate settings as a default remedy. There are no automatic
security changes or speculative antivirus/VPN workarounds in Cost Guard.
