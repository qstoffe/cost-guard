"""Export synthetic normalized/scheduled lifecycle frames for a headless DOM probe."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.pre_response_watch import PreResponseWatch, failed_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with PreResponseWatch() as case:
        messages = case.native.messages[case.stopped]
        priced = copy.deepcopy(messages[1])
        priced.update(id="priced_step", finish="tool-calls", cost=1,
            tokens={"input": 100, "output": 10}, time={"created": 3050, "completed": 3090})
        messages.insert(1, priced)
        for now in (4000, 4100):
            case.capture(now)
        frames = [case.export(4100)]
        messages.extend(failed_resume(error={"code": "quota_exceeded"}))
        case.native.active.pop(case.stopped)
        for now in (10_000, 11_000, 12_000):
            case.capture(now, churn=True)
        frames.append(case.export(12_000))
        for now in (20_000, 40_000, 50_000):
            case.capture(now, churn=True)
        frames.append(case.export(50_000))
        args.output.write_text(json.dumps({"stopped": case.stopped, "frames": frames}), encoding="utf-8")
    print(json.dumps({"status": "ok", "frames": len(frames), "synthetic": True}))


if __name__ == "__main__":
    main()
