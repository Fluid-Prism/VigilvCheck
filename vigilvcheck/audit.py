"""audit.py — headless CLI. `python3 -m vigilvcheck.audit`.

Runs every check, scores what it can, prints the ranked gap list, records
the run to local history.
"""
import argparse

from . import store, warn_if_root
from .checks import ALL_CHECKS
from .checks.base import STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN
from .scoring import ranked_gaps, run_all, score

_STATUS_LABEL = {STATUS_PASS: "PASS", STATUS_FAIL: "FAIL", STATUS_UNKNOWN: "?   ", STATUS_NA: "N/A "}


def run_audit():
    results = run_all(ALL_CHECKS)
    s, applicable = score(results)
    ts = store.record_scan(results, s, applicable)
    return results, s, applicable, ts


def _print_report(results, s, applicable):
    print()
    if s is None:
        print("  Posture score: unable to determine (nothing here was checkable).")
    else:
        print(f"  Posture score: {s}/100  ({applicable} of {len(results)} checks determinable)")
    print()
    for check, result in results:
        print(f"  [{_STATUS_LABEL[result.status]}] {check.title}")
        print(f"        {result.detail}")

    gaps = ranked_gaps(results)
    if gaps:
        print(f"\n  {len(gaps)} gap(s), ranked by severity:\n")
        for check, result in gaps:
            print(f"  {check.severity.upper():8} {check.title}")
            print(f"           {result.detail}")
            print("           Fix:\n" + "\n".join(f"           {line}" for line in check.remediation().splitlines()))
            print()
    else:
        print("\n  No gaps in what could be checked. That's not the same as \"secure\" — "
              "see the README for what this tool does and doesn't cover.\n")


def main(argv=None):
    warn_if_root()
    ap = argparse.ArgumentParser(description="Local security posture auditor.")
    ap.add_argument("--json", action="store_true", help="Emit results as JSON instead of a report")
    args = ap.parse_args(argv)

    results, s, applicable, ts = run_audit()
    if args.json:
        import json
        print(json.dumps({
            "timestamp": ts,
            "score": s,
            "applicable_count": applicable,
            "results": [
                {"id": c.id, "title": c.title, "severity": c.severity,
                 "status": r.status, "detail": r.detail}
                for c, r in results
            ],
        }, indent=2))
    else:
        _print_report(results, s, applicable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
