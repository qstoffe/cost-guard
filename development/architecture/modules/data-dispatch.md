# Host-owned Web data demand

FR 000617, v80.197 ownership with FR000624's scoped loading/recovery delta. See the
[measurement journal](../../journal/web/data-dispatch.md) for checks and limitations;
the [foreground-recovery ledger](../../journal/web/foreground-recovery.md) owns the
new evidence and explicit tradeoffs. The delivery PR/default branch own merge status.

Architecture-90 static recheck (2026-11-09, source
`54f613db6777eb4fc7fc3c5c193ad774df6c3ece`): host/dispatcher/jobs/quantum,
application export, compact-evidence and browser-interest/recovery paths were read
against their source and representative dispatcher tests. These remain separate
demand, process, report-proof and presentation owners, not duplicate source truth.
No runtime change or new executed parity/performance/native acceptance is claimed;
[the assessment](../../journal/architecture.md) records alternatives and limits.

## Ownership and admission

`web/dispatch.py::DataDispatcher` owns authenticated route leases, twelve retained
finite projections, source identity, per-product due times, bounded failure backoff
and effective priority. At most sixteen tab leases live for ninety seconds. Hidden
or expired leases lose foreground priority without deleting safe logical work.
`dispatch_http.py` validates interest/lookup after existing cookie/Origin/CSRF/instance
guards. No finite admission precedes a pinned source identity and the first healthy
Live frame publication. The browser sends
interest and reads publications, not refresh due times.

FR 000622 / v80.202 distinguishes source selection from first-Live readiness:
an identity-bearing dispatcher with no healthy observation or source fault reports
`source_starting`, not `source_unavailable`. No finite job is admitted in that
interval. FR000624 removes elapsed-work/source-wait failure cutoffs;
actual source error codes/terminal evidence remain authoritative. Browser admission
uses cancellable exponential backoff (capped at four seconds per wait, no attempt exhaustion),
including legacy `source_unavailable` only with explicit `retryable:true`.
Only a current terminal dispatcher error can accompany a usable retained result
as failure feedback; transient errors cannot poison successful publication, and
each new acquisition clears the prior attempt's dispatcher notice.

Watch/Mini/Accounts retain their existing single Live/account owners. Settings does
not acquire history. Finite services own separate source instances and no account
providers. The host enables inactive Sessions warming only after incomplete
foreground finite demand is satisfied.

## Priority and finite process safety

`jobs.py` retains MAX_PENDING=4, MAX_JOBS=16, one executing finite child and the
8 MiB result bound. `report_control.py` adds cooperative owner-thread checkpoints
(nominal 100 ms). Private process stacks park until another duplex IPC grant.
Since FR000624 background (priority >= 2) grants park after every checkpoint
quantum, while requested/foreground grants park only on a host `yield` request
for runnable equal/higher-priority work or demotion; see the
[web module contract](web.md).
Source threads wait on a read permit, not the control pipe. Already-issued reads
can finish under original deadlines. This is not OS suspension or a universal
100 ms wall-clock response guarantee.

Foreground wins over requested unfinished work and inactive warming; coalesced
scopes use minimum numerical priority. Equal-priority jobs rotate by last service.
Inactive work has a capped duty delay; new background products stagger at least
fifteen seconds apart. Healthy finite computation has no age deadline. Every child
retains explicit cancellation, bounded IPC and its exact-parent sentinel while parked. In-flight reads can briefly overlap after a
yield, bounded by admitted jobs and existing source pools, not a thread per tab.

Only independently received durable progress resumes managed Token Mix/Comparisons
in a fresh child (`history_jobs.py`, `reports/history_work.py`). Each step verifies
compact writes, bounds roots/requests and brackets membership/revisions. Repeated
proof churn remains pending with capped backoff; advancing coverage clears that delay.
There is no step-count deadline. A missing promised durable receipt is still a
protocol failure. AI Stats retains its separate
scope/slice owner. Cancel/host stop/parent loss remain internal safety, not a user
Cancel control. Unconfirmed exit retains exact ownership and fails the host;
parked cleanup cannot release a different executing owner.

AI Stats checkpoint writes distinguish native SQLite BUSY/LOCKED from other storage
faults. Only confirmed contention yields retryable `ai_stats_checkpoint_busy`;
the dispatcher keeps demand pending with its existing 2–60 second backoff and the
browser retries automatically. READONLY, unknown storage errors and genuine source
faults remain typed failures. No extra writer, timeout or concurrency is added.

Managed histories opt into `reports/history_snapshots.py`: V2 returns only trees
whose before/after revisions match after bounded retries. Unstable trees are omitted,
not returned as mixed snapshots or zero-valued roots. Final verification drops later
changed evidence; the result exposes a safe omitted-root count and partial totals.
Entirely unverifiable history returns a typed acquisition failure instead of invented
zeros; retryable proof churn keeps the logical Web demand pending and backed off,
not terminal merely from elapsed time. Ordinary
snapshot APIs remain strict. Membership/archive/ancestry/source changes invalidate
Comparisons/Token Mix; AI Stats updates its membership and rejects foreign provenance.
All three historical views use `ReportView.historyWarning` to show the structured
omission count/reason and incomplete totals; failure feedback remains separate.

## Shared facts, freshness and useful warm set

`reports/shared_evidence.py` stages at most sixty-four roots of compatible compact
facts into existing revision/algorithm/config/price/source-keyed SQLite namespaces.
Managed scans read existing derived bundles but write no new full analysis payloads.
No raw prompts/attachments/browser storage are added. Recipient reports retain their
independent populations, totals, duration unions and completeness. Catalog/revision
validation remains necessary; reduced hydration is not zero cross-process IO.

Default warming covers Normal Models' qualified 100-prompt sample, Token Mix,
30-day AI Stats (not eager lifetime) and Comparisons' compact all-root index with at
most ten retained/requested previews. Qualified historical results remain displayable
regardless of positive age, with their original as-of and AI Stats row intervals.
Freshness is not deliverability: old computation must not finish into an immediate
discard/recompute loop. Future/malformed observations and proven host dependency
invalidation still withhold results. A previous-day Today/month snapshot shows its
actual configured-zone interval, never current-period numbers; a malformed interval
withholds only that scope. Unchanged quiet lookups retain DOM, focus and scroll.
The publication ID remains separate from an active refresh job ID. Lookup reports
actual running/queued/scheduled/delayed/waiting/stopped refresh state; a browser
publication check does not itself mean a source refresh is running.

Models with 100 qualified completed priceable prompts has an hourly floor; smaller
sample active/inactive targets are fifteen/forty-five minutes. Token Mix and
Comparisons target five/twenty minutes; AI Stats fifteen/thirty. Stable product
spread staggers due work from completion, not original observation age. Neither
age nor calendar rollover resets due/backoff. Retryable faults retain bounded
automatic retry without attempt exhaustion; terminal source errors remain explicit.
Explicit strict pricing refresh remains separate:
failure preserves valid results; success invalidates warm finite projections.
`dispatch_dependencies.py` also checks validated cached prices without network work
every thirty seconds. Confirmed price changes invalidate projections; a temporarily
unreadable disposable cache is not proof of a change. Runtime configuration changes
require a fresh host because Live pins its configuration; hot Web preferences remain
independent. The first check compares Live's pinned configuration too, so a change
during startup cannot become a new silent baseline. Source changes never merge results. Managed finite pricing defers
release-metadata network refresh; the explicit price action retains its strict path.

## Sessions and detail

`application/session_catalog.py` retains its Live scalar owner and fifty-row pages.
Activity/name demand indexes requested pages only; a requested metric sort alone
requires all global scalar keys. Visibility demotes that interest promptly while
the separate five-minute page/epoch lease remains bounded. Inactive warming covers
the first or last actually viewed page: fifteen seconds while incomplete and a
fifteen-minute floor once current, never every page. Renewed visible targets bypass
an old quiet delay; they do not hydrate unvisited pages. Main-nav return remembers offset/sort/epoch; invalid or
expired positions explicitly offer latest sessions instead of substituting page
one. Repeated publications do not renew catalog observation age.
Same-ID root provenance replacement expires retained epochs too; an out-of-range
older page requires explicit recovery, never a silent empty/page-one substitution.

Detail stays on demand with twenty-five-row revision-pinned chunks. Valid retained
captures are immediate through sixty minutes; failed acquisition cannot renew age.
Source rotation clears owned detail histories/catalog leases. No speculative
all-session detail warm-up or new persistent history ledger exists.
