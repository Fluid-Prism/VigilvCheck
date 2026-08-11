"""base.py — the shape every check conforms to.

A check is a small, self-contained unit: read the current state (always
safe, always read-only, never raises), and describe how to fix it in plain
English with a copy-paste command. Nothing here executes a fix — that's a
deliberate line for this first version, not a missing feature. See
SECURITY.md for why.

CIS references below are topic-level, not a specific section number. CIS
benchmarks get revised per OS version and section numbers shift between
revisions; hardcoding a number here that can't be verified against the
current PDF would be presenting a guess as fact. Look up the exact control
on cisecurity.org for your OS version if you need the citation.
"""
import subprocess
from dataclasses import dataclass
from shutil import which
from typing import Callable

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"
STATUS_NA = "not_applicable"

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

_HAVE_CACHE = {}


def have(tool):
    if tool not in _HAVE_CACHE:
        _HAVE_CACHE[tool] = which(tool) is not None
    return _HAVE_CACHE[tool]


def run(cmd, timeout=10):
    """Run a read-only command, returning stdout ('' on any failure). Never
    raises: a missing tool or a permission error just means this signal
    contributes nothing, not a crash and not a guessed answer."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def run_stderr(cmd, timeout=10):
    """A few macOS tools (sysadminctl) put their actual answer on stderr."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stderr
    except (OSError, subprocess.SubprocessError):
        return ""


def try_sudo_n(cmd, timeout=5):
    """Attempt a command with non-interactive sudo. Succeeds only if the
    caller already has a live sudo session; fails instantly otherwise. Never
    prompts for a password, never hangs waiting for one."""
    try:
        r = subprocess.run(["sudo", "-n", *cmd], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout
    except (OSError, subprocess.SubprocessError):
        return False, ""


@dataclass
class CheckResult:
    status: str    # pass | fail | unknown | not_applicable
    detail: str     # human-readable current state, e.g. "FileVault is off"


@dataclass
class Check:
    id: str
    title: str
    rationale: str                    # why an attacker cares
    severity: str                      # critical | high | medium | low
    cis_topic: str                      # topic-level reference, see module docstring
    read: Callable[[], CheckResult]
    remediation: Callable[[], str]      # plain-English explanation + copy-paste command
