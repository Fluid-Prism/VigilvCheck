"""selftest.py — offline checks for the logic that doesn't depend on this
machine's actual state: scoring math and registry integrity. The checks
themselves read real system state, so they're not something a fixed offline
test can assert against the way a version comparator can.

    python3 -m posture.selftest
"""
from .checks import ALL_CHECKS
from .checks.base import SEVERITY_WEIGHT, STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN, Check, CheckResult
from .scoring import ranked_gaps, score


def _fake(severity, status):
    check = Check(id="x", title="x", rationale="x", severity=severity, cis_topic="x",
                 read=lambda: None, remediation=lambda: "x")
    return check, CheckResult(status, "x")


def check_score_basic():
    # one critical pass, one low fail -> weighted, not a plain average
    results = [_fake("critical", STATUS_PASS), _fake("low", STATUS_FAIL)]
    s, applicable = score(results)
    expected = round(100 * SEVERITY_WEIGHT["critical"] / (SEVERITY_WEIGHT["critical"] + SEVERITY_WEIGHT["low"]))
    assert s == expected, f"score() = {s}, want {expected}"
    assert applicable == 2
    return 1


def check_score_excludes_unknown_and_na():
    results = [_fake("high", STATUS_PASS), _fake("high", STATUS_UNKNOWN), _fake("high", STATUS_NA)]
    s, applicable = score(results)
    assert s == 100, f"unknown/N/A shouldn't count against the score, got {s}"
    assert applicable == 1
    return 1


def check_score_none_when_nothing_applicable():
    results = [_fake("high", STATUS_UNKNOWN), _fake("critical", STATUS_NA)]
    s, applicable = score(results)
    assert s is None, "score() should be None, not 0, when nothing was determinable"
    assert applicable == 0
    return 1


def check_ranked_gaps_severity_order():
    results = [_fake("low", STATUS_FAIL), _fake("critical", STATUS_FAIL),
              _fake("medium", STATUS_FAIL), _fake("high", STATUS_PASS)]
    gaps = ranked_gaps(results)
    severities = [c.severity for c, r in gaps]
    assert severities == ["critical", "medium", "low"], f"got {severities}"
    return 1


def check_registry_integrity():
    ids = [c.id for c in ALL_CHECKS]
    assert len(ids) == len(set(ids)), f"duplicate check ids: {ids}"
    assert len(ALL_CHECKS) >= 1, "registry is empty"
    for c in ALL_CHECKS:
        assert c.severity in SEVERITY_WEIGHT, f"{c.id} has an unknown severity: {c.severity}"
        assert c.title and c.rationale and c.cis_topic, f"{c.id} is missing required text"
        assert callable(c.read) and callable(c.remediation), f"{c.id} read/remediation isn't callable"
    return len(ALL_CHECKS)


def main():
    total = 0
    for name, fn in [("score weighting", check_score_basic),
                     ("score excludes unknown/N/A", check_score_excludes_unknown_and_na),
                     ("score is None, not 0, when nothing applicable", check_score_none_when_nothing_applicable),
                     ("ranked gaps ordering", check_ranked_gaps_severity_order),
                     ("registry integrity", check_registry_integrity)]:
        n = fn()
        total += n
        print(f"  ✓ {name:<45} {n} case(s)")
    print(f"\n  All {total} checks passed.\n")


if __name__ == "__main__":
    main()
