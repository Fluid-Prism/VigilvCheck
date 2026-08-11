"""scoring.py — turn a list of check results into one honest number.

Severity-weighted: a failed critical check (disk encryption) costs more than
a failed low one. Checks that came back unknown or not_applicable are
excluded from both sides of the ratio — they're not counted as passed, and
they don't get held against you either, since neither would be true. A
machine with three unknowns and everything else passing shows a real score
for what it could actually verify, with the gaps stated separately rather
than folded into a number that would misrepresent them either way.
"""
from .checks.base import SEVERITY_WEIGHT, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, CheckResult


def run_all(checks):
    """[(check, CheckResult), ...] for every check in the registry. A bug in
    one check's read() (not a subprocess failure, which read() already
    handles — an actual unexpected exception) must not take the other seven
    results down with it, so each read runs in its own try/except."""
    results = []
    for c in checks:
        try:
            results.append((c, c.read()))
        except Exception as e:
            results.append((c, CheckResult(STATUS_UNKNOWN, f"This check hit an unexpected error: {e}")))
    return results


def score(results):
    """results: [(check, CheckResult), ...] -> (score 0-100 or None, applicable_count).
    None means nothing here was applicable/determinable — not a score of 0."""
    applicable = [(c, r) for c, r in results if r.status in (STATUS_PASS, STATUS_FAIL)]
    if not applicable:
        return None, 0
    total = sum(SEVERITY_WEIGHT[c.severity] for c, r in applicable)
    passed = sum(SEVERITY_WEIGHT[c.severity] for c, r in applicable if r.status == STATUS_PASS)
    return round(100 * passed / total), len(applicable)


def ranked_gaps(results):
    """Failed checks only, most severe first — what to fix, in order."""
    failed = [(c, r) for c, r in results if r.status == STATUS_FAIL]
    return sorted(failed, key=lambda cr: SEVERITY_WEIGHT[cr[0].severity], reverse=True)
