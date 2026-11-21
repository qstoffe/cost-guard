"""Source-qualified running-shell timing and bounded historical comparisons."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock

from development.tests.fixtures.session_snapshots import make_snapshot, part, prov
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.sources.opencode_v2_background import ShellRegistry, background_activities, running_jobs
from src.sources.opencode_v2_normalization import normalize_message_bundle
from src.sources.opencode_v2_wire import normalize_message_items
from src.watch.shell_timing import MAX_HISTORY_PARTS
from src.watch.tools import observe_tools

COMMAND = "py -3 eval.py --arms baseline,candidate --fixture isolated --model fixed"
TIMEOUT = 3_220_000


def native_shell(key, start, *, command=COMMAND, duration=None, status=None, exit_code=0,
                 timeout=TIMEOUT, job=None, created=None, session="root"):
    state = {"status": status or ("completed" if duration is not None or job else "running"),
             "input": {"workdir": "C:/fixture", "timeout": timeout}}
    times = {"created": created if created is not None else start - 10}
    if start:
        times["ran"] = start
    if command is not None:
        state["input"]["command"] = command
    if duration is not None or job:
        times["completed"] = start + (duration if duration is not None else 1)
        state["metadata"] = {"exit": exit_code}
    if job:
        state["input"]["background"] = True
        state["metadata"]["shellID"] = job
    return {"id": key, "callID": key, "sessionID": session, "name": "shell", "type": "tool",
            "time": times, "state": state}


def notice(job, when, *, state="completed", exit_code=0, session="root"):
    return {"id": "notice-" + job, "type": "synthetic", "sessionID": session,
            "time": {"created": when}, "metadata": {"shellID": job, "source": "shell",
                                                   "state": state, "exit": exit_code}}


def capture(*tools, notices=(), registry=None, status="observed"):
    base = make_snapshot(generation="v2", running=True)
    item = {"type": "assistant", "id": "a_next", "sessionID": "root", "content": list(tools),
            "time": {"created": 2200}}
    (bundle,), _ = normalize_message_items((item,), session={"id": "root"})
    _, parts = normalize_message_bundle(bundle, lambda sid, event: prov(sid, event, "v2"))
    background, _ = background_activities((item, *notices), session_id="root", running_jobs=lambda: registry)
    messages = tuple(replace(message, parts=parts) if message.message_id == "a_next" else message
                     for message in base.messages)
    return replace(base, messages=messages, parts=parts, background=background, complete=status == "observed")


def observe(snapshot, now=2_000_000):
    return observe_tools(snapshot, "u_next", now_ms=now, include_invocations=True)


def publish(observed, now, *, zone="Europe/Stockholm", state="observed", in_progress=True):
    frame = summary_watch()
    card = frame.active_cards[0]
    row = replace(card.rows[0], tool=observed, prompt=replace(card.rows[0].prompt, in_progress=in_progress))
    card = replace(card, rows=(row,), state=state)
    return project_live(replace(frame, now_ms=now, active_cards=(card,)), timezone_id=zone).to_json()


class ShellTimingTests(TestCase):
    def test_uses_native_execution_start_over_creation_and_survives_redaction(self):
        start = 1_795_000_000_300
        shell = native_shell("one", start, created=start - 12_000, command="curl -u user:synthetic-private")
        observed = observe(capture(shell), now=start + 40_000)
        detail, = observed.running_invocations
        payload = publish(observed, now=start + 40_000)
        wire, = payload["active_cards"][0]["rows"][0]["tool"]["running_invocations"]

        self.assertEqual((start, "execution", TIMEOUT),
                         (wire["started_at_ms"], wire["shell_timing"]["anchor"], wire["shell_timing"]["timeout_ms"]))
        self.assertEqual("Europe/Stockholm", payload["timezone_id"])
        self.assertNotIn("synthetic-private", detail.text)
        self.assertIn("withheld", detail.qualification)
        self.assertIn("C:/fixture", detail.text)

    def test_creation_fallback_keeps_raw_timeout_and_never_invents_execution_boundaries(self):
        shell = native_shell("one", None, created=1000)
        detail, = observe(capture(shell)).running_invocations

        self.assertEqual((1000, "call_created", TIMEOUT, None),
            (detail.started_at_ms, detail.shell_timing.anchor, detail.shell_timing.timeout_ms,
             detail.shell_timing.estimated_duration_ms))
        for invalid in (None, True, 0, -1, "5000", float("inf"), 2**200):
            with self.subTest(invalid=invalid):
                detail, = observe(capture(native_shell("invalid", 1000, timeout=invalid))).running_invocations
                self.assertIsNone(detail.shell_timing.timeout_ms)

    def test_only_complete_matching_successful_earlier_physical_calls_contribute(self):
        live = native_shell("active", 1_200_000)
        comparable = [native_shell("sample-" + str(i), 1000, duration=value)
                      for i, value in enumerate((61_000, 123_000, 491_000))]
        duplicate = native_shell("duplicated", 1000, duration=2_000)
        false_samples = [
            native_shell("failed", 1000, duration=5_000, exit_code=1),
            native_shell("cancelled", 1000, duration=3_000, status="error"),
            native_shell("timed-out", 1000, duration=10_000, timeout=10_000),
            native_shell("still-running", 1000),
            native_shell("missing-end", 1000, status="completed"),
            native_shell("wrong-model", 1000, duration=10_000, command=COMMAND.replace("fixed", "other")),
            native_shell("wrong-arm", 1000, duration=6_000, command=COMMAND.replace("baseline,candidate", "candidate")),
            native_shell("wrong-fixture", 1000, duration=6_000, command=COMMAND.replace("isolated", "other")),
            native_shell("other-session", 1000, duration=8_000, session="other"),
            native_shell("overlapping", 1_190_000, duration=51_000),
            duplicate, duplicate,
        ]
        snapshot = capture(*comparable, *false_samples, live)
        details = observe(snapshot).running_invocations
        target = next(item for item in details if item.started_at_ms == 1_200_000)
        incomplete = observe(replace(snapshot, complete=False)).running_invocations[-1]

        self.assertEqual((3, 120_000), (target.shell_timing.sample_count, target.shell_timing.estimated_duration_ms))
        self.assertEqual(0, incomplete.shell_timing.sample_count)
        self.assertIsNone(incomplete.shell_timing.estimated_duration_ms)

    def test_sparse_generic_and_out_of_window_history_do_not_forecast(self):
        first = native_shell("first", 1000, duration=100_000)
        second = native_shell("second", 2000, duration=100_000)
        live = native_shell("live", 1_200_000)
        sparse, = observe(capture(first, live)).running_invocations
        complete = capture(first, second, live)
        filler = part("marker", "a_next", "root", "text", {}, 10_000)
        parts = (*complete.parts[:2], *((filler,) * MAX_HISTORY_PARTS), complete.parts[-1])
        messages = tuple(replace(message, parts=parts) if message.message_id == "a_next" else message
                         for message in complete.messages)
        bounded, = observe(replace(complete, parts=parts, messages=messages)).running_invocations
        generic, = observe(capture(native_shell("a", 1000, command="python -u", duration=50_000),
                                   native_shell("b", 2000, command="python -u", duration=50_000),
                                   native_shell("c", 120_000, command="python -u"))).running_invocations

        self.assertEqual((1, None), (sparse.shell_timing.sample_count, sparse.shell_timing.estimated_duration_ms))
        for detail in (bounded, generic):
            self.assertEqual((0, None), (detail.shell_timing.sample_count, detail.shell_timing.estimated_duration_ms))

    def test_live_background_deadline_and_full_completion_use_distinct_physical_jobs(self):
        jobs = [
            native_shell("past1", 2000, job="past1"),
            native_shell("past2", 4000, job="past2"),
            native_shell("failed", 5000, job="failed"),
            native_shell("unknown", 6000, job="unknown"),
            native_shell("live1", 500_000, job="live1"),
            native_shell("live2", 510_000, job="live2", timeout=30_000, command=None),
        ]
        registry = ShellRegistry(frozenset({"live1", "live2", "unknown"}), {
            "live1": {"sessionID": "root", "command": COMMAND},
            "live2": {"sessionID": "root", "command": "py -3 other.py --fixture isolated"},
        })
        snapshot = capture(*jobs, registry=registry, notices=(
            notice("past1", 62_000), notice("past2", 124_000),
            notice("failed", 15_000, state="timeout"), notice("unknown", 16_000, session="peer"),
        ))
        first, second = observe(snapshot).background_invocations
        reordered = observe(replace(snapshot, background=tuple(reversed(snapshot.background)))).background_invocations

        self.assertEqual((first, second), reordered)
        self.assertEqual((500_000, TIMEOUT, 90_000, 2),
            (first.started_at_ms, first.shell_timing.timeout_ms, first.shell_timing.estimated_duration_ms,
             first.shell_timing.sample_count))
        self.assertEqual((510_000, 30_000, None),
            (second.started_at_ms, second.shell_timing.timeout_ms, second.shell_timing.estimated_duration_ms))
        self.assertIn("other.py", second.text)
        self.assertNotIn("other.py", first.text)

    def test_registry_ownership_unavailability_and_command_only_mismatch(self):
        shell = native_shell("call", 100_000, command=None, job="job")
        client = Mock()
        client.json.return_value = {"data": [{"id": "job", "status": "running", "command": "unowned-command"}]}
        registry = running_jobs(client, "")
        unowned, = observe(capture(shell, registry=registry)).background_invocations
        unavailable, = observe(capture(shell)).background_invocations
        conflict, = observe(capture(shell, registry=ShellRegistry(frozenset({"job"}), {
            "job": {"sessionID": "peer", "command": "peer-command"}}))).background_invocations
        original, = observe(capture(native_shell("call", 100_000, job="job"), registry=ShellRegistry(
            frozenset({"job"}), {"job": {"sessionID": "root", "command": "registry-wrapper"}}))).background_invocations

        self.assertIn("No source command", unowned.qualification)
        self.assertIn("not safely linked", unowned.qualification)
        self.assertNotIn("unowned-command", unowned.text)
        self.assertEqual(TIMEOUT, unowned.shell_timing.timeout_ms)
        self.assertIn("awaiting verified", unavailable.qualification)
        self.assertIsNone(unavailable.shell_timing)
        self.assertIn("Conflicting", conflict.qualification)
        self.assertEqual("", conflict.text)
        self.assertIsNone(conflict.shell_timing)
        self.assertIn(COMMAND, original.text)
        self.assertIn("registry command differs", original.qualification)
        self.assertEqual(TIMEOUT, original.shell_timing.timeout_ms)

    def test_projection_withdraws_timing_on_pending_terminal_or_replaced_source(self):
        snapshot = capture(native_shell("call", 100_000))
        observed = observe(snapshot)
        for state, live in (("partial", True), ("unavailable", True), ("observed", False)):
            with self.subTest(state=state, live=live):
                wire = publish(observed, 1_000_000, state=state, in_progress=live)
                self.assertEqual([], wire["active_cards"][0]["rows"][0]["tool"]["running_invocations"])
        different = replace(snapshot.root.provenance, source_instance="different")
        switched = observe(replace(snapshot, root=replace(snapshot.root, provenance=different)))
        self.assertEqual((), switched.running_invocations)
