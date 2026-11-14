"""The task-scoped mixed-input exclusion fails closed outside measured evidence."""
from copy import deepcopy
import unittest

from development.tests.integration.ci_mini_tooltips import accepted_mixed_gap, fr704_delivery


class MiniCiTests(unittest.TestCase):
    def evidence(self):
        observation = dict(method="hover", theme="classic", scheme="light", unit="credits",
            same=True, connected=True, focus=True, active=False, open=False, hit=True, hovered=True,
            events=[
                dict(kind="pointermove", trusted=True, mouse=True, onTarget=True, hovered=True,
                     same=True, connected=True, focus=True, elapsed=0),
                dict(kind="selector", guard=True, result=False, same=True, connected=True, focus=True, elapsed=600)])
        detail = dict(outcome="FAIL", diagnostic=dict(phase="rendered-duration", code="condition_not_reached",
            probeCase="mini-total-heading-hover", observation=observation))
        pull = dict(head=dict(ref="fr-000704", repo=dict(full_name="qstoffe/cost-guard")),
                    base=dict(ref="main", repo=dict(full_name="qstoffe/cost-guard")))
        event = dict(number=310, pull_request=pull)
        environment = dict(GITHUB_REPOSITORY="qstoffe/cost-guard", GITHUB_EVENT_NAME="pull_request")
        core = {name: dict(outcome="PASS", journey=name) for name in ("mouse", "touch")}
        return detail, event, environment, core

    def test_only_exact_failed_trace_is_nonblocking_after_both_core_journeys_pass(self):
        detail, event, environment, core = self.evidence()

        accepted = accepted_mixed_gap("mixed", detail, 1, event, environment, core)

        self.assertTrue(accepted)
        self.assertEqual("FAIL", detail["outcome"], "the original failure is never rewritten to PASS")
        for journey, code in (("mouse", 1), ("touch", 1), ("mixed", -1), ("mixed", 0), ("mixed", 2)):
            self.assertFalse(accepted_mixed_gap(journey, detail, code, event, environment, core))

    def test_missing_different_or_departed_evidence_and_failed_core_are_fatal(self):
        detail, event, environment, core = self.evidence()
        variants = []
        for key, value in (("theme", "web"), ("unit", "usd"), ("connected", False), ("focus", False),
                           ("hit", False), ("events", []), ("events", None), ("same", "true")):
            changed = deepcopy(detail)
            changed["diagnostic"]["observation"][key] = value
            variants.append(changed)
        changed = deepcopy(detail)
        changed["diagnostic"]["observation"]["events"][1]["result"] = True
        variants.append(changed)
        changed = deepcopy(detail)
        changed["diagnostic"]["observation"]["events"].append(dict(kind="pointerleave", onTarget=True, elapsed=200))
        variants.append(changed)
        changed = deepcopy(detail)
        changed["diagnostic"]["probeCase"] = "another-heading"
        variants.extend((changed, {}, dict(outcome="PASS"), dict(outcome="FAIL", diagnostic={})))
        for changed in variants:
            self.assertFalse(accepted_mixed_gap("mixed", changed, 1, event, environment, core))
        for name in ("mouse", "touch"):
            failed_core = deepcopy(core)
            failed_core[name]["outcome"] = "FAIL"
            self.assertFalse(accepted_mixed_gap("mixed", detail, 1, event, environment, failed_core))

    def test_exclusion_does_not_transfer_to_another_pr_repository_or_later_main_commit(self):
        _, event, environment, _ = self.evidence()
        for changed in (dict(event, number=311), {}, dict(event, number="310")):
            self.assertFalse(fr704_delivery(changed, environment))
        self.assertFalse(fr704_delivery(event, dict(environment, GITHUB_REPOSITORY="other/cost-guard")))
        sha = "a" * 40
        push = dict(head_commit=dict(id=sha,
            message="Fix stationary hover lifetime and compact Mini tooltip scopes (FR000704) (#310)\n\nDetails"))
        environment = dict(GITHUB_REPOSITORY="qstoffe/cost-guard", GITHUB_EVENT_NAME="push",
                           GITHUB_REF="refs/heads/main", GITHUB_SHA=sha)
        self.assertTrue(fr704_delivery(push, environment))
        push["head_commit"]["message"] = "A later tooltip change (#311)"
        self.assertFalse(fr704_delivery(push, environment))


if __name__ == "__main__":
    unittest.main()
