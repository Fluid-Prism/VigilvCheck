"""gatekeeper_sip.py — macOS-only: code execution and system-tampering gates.

Both read via unprivileged, verified-live commands. Neither has a Linux
equivalent worth forcing an analog for — SELinux/AppArmor enforcing-mode
status is the closest concept but is different enough in what it protects
that pretending it's the same check would be misleading, so this reports
not_applicable on Linux instead.

SIP specifically can't be fixed with a copy-paste command from a running
session, by design — Apple built it to be unchangeable from anywhere except
Recovery Mode, specifically so a compromised or root-level process can't
turn it off. The remediation text says so instead of pretending a
`csrutil enable` one-liner would work from here.
"""
import platform

from .base import Check, CheckResult, STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN, run


def parse_spctl(out):
    out = out.strip()
    if "assessments enabled" in out:
        return CheckResult(STATUS_PASS, "Gatekeeper is enabled.")
    if "assessments disabled" in out:
        return CheckResult(STATUS_FAIL, "Gatekeeper is disabled.")
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse spctl output: {out or '(empty)'}")


def _gatekeeper_read():
    if platform.system() != "Darwin":
        return CheckResult(STATUS_NA, "Gatekeeper is macOS-specific.")
    return parse_spctl(run(["spctl", "--status"]))


def _gatekeeper_remediation():
    return ("    sudo spctl --master-enable\n\n"
            "Turns Gatekeeper back on, so macOS checks that apps are signed and notarized "
            "before running them.")


GATEKEEPER_CHECK = Check(
    id="gatekeeper",
    title="Gatekeeper",
    rationale="With Gatekeeper off, macOS will run any app regardless of whether it's "
             "signed by a known developer or notarized by Apple, including things "
             "downloaded from a browser without a second thought.",
    severity="high",
    cis_topic="Gatekeeper / app execution policy",
    read=_gatekeeper_read,
    remediation=_gatekeeper_remediation,
)


def parse_csrutil(out):
    out = out.strip()
    if "enabled" in out.lower():
        return CheckResult(STATUS_PASS, "System Integrity Protection is enabled.")
    if "disabled" in out.lower():
        return CheckResult(STATUS_FAIL, "System Integrity Protection is disabled.")
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse csrutil output: {out or '(empty)'}")


def _sip_read():
    if platform.system() != "Darwin":
        return CheckResult(STATUS_NA, "System Integrity Protection is macOS-specific.")
    return parse_csrutil(run(["csrutil", "status"]))


def _sip_remediation():
    return ("This can't be turned on from a normal session — Apple deliberately made SIP "
            "unchangeable from anywhere except Recovery Mode, so that nothing running as "
            "root can quietly disable it. To turn it back on:\n\n"
            "  1. Restart and hold the power button (Apple silicon) or Cmd+R (Intel) until "
            "you reach Recovery Mode\n"
            "  2. Open Terminal from the Utilities menu\n"
            "  3. Run: csrutil enable\n"
            "  4. Restart normally")


SIP_CHECK = Check(
    id="sip",
    title="System Integrity Protection",
    rationale="SIP stops even a root-level process from modifying protected system files "
             "and injecting code into other processes. Turning it off removes a barrier "
             "that malware specifically has to work around otherwise.",
    severity="high",
    cis_topic="System Integrity Protection",
    read=_sip_read,
    remediation=_sip_remediation,
)
