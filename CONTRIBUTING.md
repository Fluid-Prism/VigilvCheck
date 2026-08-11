# Contributing to Posture

## Dev setup

```bash
git clone <this repo>
cd posture
pip install -r requirements.txt

python3 -m posture                   # launch the desktop app
python3 -m posture.audit             # or the headless CLI
python3 -m posture.selftest          # offline checks, run these before every PR
```

## Tests

`posture/selftest.py` covers the logic that doesn't depend on your specific
machine: scoring math and registry integrity. It can't meaningfully test
the checks themselves offline, since each one reads real system state — if
you add a check, the honest test is running it on the platform it targets
and confirming the result matches reality, not a fixture.

## Code style

Same discipline as Kevscope, its sibling app:

- Don't comment what code does. Good names do that. Comment the non-obvious
  why: a platform quirk, an invariant, a workaround for a specific bug.
- No speculative abstraction. A check that only needs two branches
  (`if platform.system() == "Darwin"`) doesn't need a plugin architecture.
- Every read degrades to `unknown`, never raises, never guesses. A missing
  tool or a permission error means that one check can't be answered, not
  that the check failed and not that the app crashes.
- State confidence honestly. `not_applicable` is not the same as `pass`,
  and `unknown` is not the same as `fail` — collapsing any of these into
  each other for a tidier score is exactly the false confidence this tool
  exists to avoid.

## Pull requests

Keep PRs scoped to one thing and explain why in the description.

If you're adding or fixing a Linux check, say in the PR whether you
verified it on a real machine or wrote it from documented behavior — both
are useful, but the difference matters and should be visible, not implied.

Don't add auto-remediation for a check without reading the "Why there's no
auto-remediation yet" section of the README first. The bar for that is
higher than "the command works."
