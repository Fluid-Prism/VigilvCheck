"""backups.py — is there a copy of this machine anywhere else?

The one control on this list that answers "what happens after something goes
wrong" rather than "how do I stop it going wrong". Every other check here is
about keeping an attacker out; this one is about ransomware, a failed disk,
and a stolen laptop — the outcomes where prevention has already lost and the
only question left is whether the data still exists somewhere.

macOS: `tmutil destinationinfo` lists configured Time Machine destinations,
unprivileged and without touching the drive — verified live. A machine with
no destination reports exactly that.

There is no equivalent on Linux worth pretending to check. Backups there are
whatever the person chose — restic, borg, rsync in cron, a NAS, the
distribution's own tool — and finding no configuration for any of them says
nothing about whether backups exist. Reporting not_applicable is the honest
answer; guessing would produce a confident 'no backups' for a machine backed
up perfectly well by something this doesn't know about.
"""
import platform

from .base import Check, CheckResult, STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN, have, run


def parse_tmutil_destinations(out):
    text = (out or "").strip()
    if not text:
        return CheckResult(STATUS_UNKNOWN, "Couldn't read the Time Machine configuration.")
    if "no destinations" in text.lower():
        return CheckResult(STATUS_FAIL, "No Time Machine destination is configured, so nothing "
                                        "on this machine is being backed up by it.")
    names = [line.split(":", 1)[1].strip()
             for line in text.splitlines() if line.strip().startswith("Name")]
    if names:
        label = ", ".join(names)
        return CheckResult(STATUS_PASS, f"Time Machine is configured to back up to: {label}.")
    # Output that isn't the "no destinations" line and has no Name field is a
    # format this doesn't know; saying so beats calling it a pass or a fail.
    return CheckResult(STATUS_UNKNOWN, "Time Machine returned a configuration this check "
                                       "doesn't recognise.")


def _macos_read():
    if not have("tmutil"):
        return CheckResult(STATUS_UNKNOWN, "tmutil isn't available on this system.")
    return parse_tmutil_destinations(run(["tmutil", "destinationinfo"]))


def read():
    if platform.system() != "Darwin":
        return CheckResult(STATUS_NA, "No backup mechanism on Linux is common enough to check "
                                      "for without guessing. See the README.")
    return _macos_read()


def remediation():
    return ("Set up Time Machine in System Settings → General → Time Machine → Add Backup Disk.\n\n"
            "Two things worth getting right while you're there:\n\n"
            "  • Encrypt the backup. An unencrypted backup disk is a full copy of everything "
            "FileVault is protecting, sitting on a drive anyone can walk off with.\n"
            "  • Keep a copy that isn't always plugged in. Ransomware encrypts attached "
            "drives too, so a backup that's permanently mounted shares the fate of the "
            "machine it's backing up.")


CHECK = Check(
    id="backups",
    title="Backups configured",
    rationale="Every other check here tries to keep an attacker out. This one decides what "
             "happens when that fails: with ransomware, a dead disk, or a stolen laptop, a "
             "recent backup is the difference between an afternoon and a catastrophe.",
    severity="high",
    cis_topic="Backup and recovery",
    read=read,
    remediation=remediation,
)
