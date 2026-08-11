"""guest_account.py — is there a no-password or extra-privileged way in?

macOS: the Guest account toggle, via defaults (unprivileged, verified live).
Linux has no built-in guest-login concept the way macOS does, so this checks
the closest equivalents instead: extra UID-0 accounts beyond root (anyone
with one has full root privilege under a different name), and lightdm's
optional guest session, if lightdm is present. Not verified live.
"""
import os
import platform
import re

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, run


def _macos_read():
    out = run(["defaults", "read", "/Library/Preferences/com.apple.loginwindow", "GuestEnabled"]).strip()
    if out == "0":
        return CheckResult(STATUS_PASS, "Guest account is disabled.")
    if out == "1":
        return CheckResult(STATUS_FAIL, "Guest account is enabled.")
    return CheckResult(STATUS_UNKNOWN, "Couldn't read the guest account setting.")


def _linux_read():
    try:
        passwd = open("/etc/passwd").read()
    except OSError:
        return CheckResult(STATUS_UNKNOWN, "Couldn't read /etc/passwd.")

    problems = []
    extra_root = [line.split(":")[0] for line in passwd.splitlines()
                 if len(line.split(":")) > 2 and line.split(":")[2] == "0" and line.split(":")[0] != "root"]
    if extra_root:
        problems.append(f"extra UID-0 account(s): {', '.join(extra_root)}")

    lightdm_conf = "/etc/lightdm/lightdm.conf"
    if os.path.isfile(lightdm_conf):
        try:
            conf = open(lightdm_conf).read()
        except OSError:
            conf = ""
        if re.search(r"(?m)^\s*allow-guest\s*=\s*true", conf):
            problems.append("lightdm allow-guest is enabled")

    if problems:
        return CheckResult(STATUS_FAIL, "; ".join(problems) + ".")
    return CheckResult(STATUS_PASS, "No extra UID-0 accounts, no lightdm guest session enabled.")


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Turn off the guest account in System Settings → Users & Groups → Guest User, "
                "or:\n\n    sudo dscl . -delete /Users/Guest 2>/dev/null; "
                "sudo defaults write /Library/Preferences/com.apple.loginwindow "
                "GuestEnabled -bool false")
    return ("Remove or lock any extra UID-0 account (double-check what it's for first, "
            "some legitimate setups use one intentionally):\n\n"
            "    sudo passwd -l <account>\n\n"
            "If lightdm's guest session is enabled and you don't need it:\n\n"
            "    edit /etc/lightdm/lightdm.conf and set allow-guest=false")


CHECK = Check(
    id="guest-account",
    title="Guest / extra-privileged accounts",
    rationale="A guest login or an extra root-equivalent account is a way in that "
             "doesn't show up when you're thinking about \"my password\" — it's easy to "
             "forget it's there.",
    severity="medium",
    cis_topic="Guest account / redundant privileged accounts",
    read=read,
    remediation=remediation,
)
