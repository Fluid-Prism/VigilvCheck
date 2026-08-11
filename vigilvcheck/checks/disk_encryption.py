"""disk_encryption.py — is the boot disk encrypted at rest?

macOS: `fdesetup status` (FileVault). Unprivileged, verified live.
Linux: is the block device backing / a dm-crypt (LUKS) volume? Verified by
knowledge, not by running it on a live Linux box — this repo doesn't have
one. Best-effort: confirms *some* LUKS device is under /, not that every
sensitive path is encrypted (e.g. a separate unencrypted /home would pass
this and shouldn't be treated as fully covered).
"""
import platform

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, run


def parse_fdesetup(out):
    out = out.strip()
    if out.lower().startswith("filevault is on"):
        return CheckResult(STATUS_PASS, out)
    if out.lower().startswith("filevault is off"):
        return CheckResult(STATUS_FAIL, out)
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse fdesetup output: {out or '(empty)'}")


def _macos_read():
    return parse_fdesetup(run(["fdesetup", "status"]))


def parse_lsblk_type(kind, root_src):
    kind = kind.strip()
    if "crypt" in kind:
        return CheckResult(STATUS_PASS, f"Root filesystem ({root_src}) is on an encrypted (dm-crypt) volume.")
    if kind:
        return CheckResult(STATUS_FAIL, f"Root filesystem ({root_src}) doesn't appear to be encrypted.")
    return CheckResult(STATUS_UNKNOWN, f"Couldn't read the device type for {root_src}.")


def _linux_read():
    root_src = run(["findmnt", "-no", "SOURCE", "/"]).strip()
    if not root_src:
        return CheckResult(STATUS_UNKNOWN, "Couldn't determine the root filesystem's block device.")
    return parse_lsblk_type(run(["lsblk", "-no", "TYPE", root_src]), root_src)


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Turn on FileVault in System Settings → Privacy & Security → FileVault, "
                "or run:\n\n    sudo fdesetup enable\n\n"
                "This starts encrypting the whole disk in the background — it can take "
                "hours and isn't easily reversed once started, so it's worth doing before "
                "you need to walk away from the machine, not while you're rushing out.")
    return ("Full-disk encryption has to be set up during OS install on most distros "
            "(LUKS isn't something you bolt on to an already-formatted root partition "
            "without reinstalling). If this machine wasn't encrypted at install time, "
            "the practical options are: back up your data and reinstall with encryption "
            "enabled, or encrypt specific sensitive directories with something like "
            "gocryptfs instead of the whole disk.")


CHECK = Check(
    id="disk-encryption",
    title="Disk encryption",
    rationale="If this laptop is lost or stolen, an unencrypted disk means anyone with "
             "physical access can pull the drive and read everything on it, no password "
             "needed.",
    severity="critical",
    cis_topic="Disk encryption / FileVault / LUKS",
    read=read,
    remediation=remediation,
)
