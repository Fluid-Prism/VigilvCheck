"""vigilvcheck — a local security-posture auditor and guided hardener.

Checks this machine against a set of well-known hardening basics (disk
encryption, firewall, automatic updates, screen lock, remote login,
guest accounts, Gatekeeper, System Integrity Protection), scores what it
can determine, and explains each gap in plain English with a copy-paste
fix. It doesn't run any fix for you — see SECURITY.md for why that's a
deliberate line, not a missing feature, in this first version.

Local-first: every read happens on this machine, nothing is uploaded
anywhere. Runs as a CLI (`python3 -m vigilvcheck.audit`) or a desktop app
(`python3 -m vigilvcheck`).
"""
import os
import sys


def warn_if_root():
    """This tool only ever needs to read local system settings. Running it
    as root would widen the blast radius of any bug for no benefit, so it
    says so rather than silently going along with it."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Warning: running as root. This tool only needs a regular user "
              "account for its checks — remediation steps that need elevation "
              "will tell you so individually.", file=sys.stderr)
