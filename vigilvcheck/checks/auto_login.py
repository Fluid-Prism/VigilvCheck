"""auto_login.py — does this machine log someone in without asking?

The check that quietly undoes disk encryption. FileVault protects a powered-
off machine because the disk can't be read without someone supplying a
credential at boot; automatic login supplies it for them. A stolen laptop
with FileVault on and auto-login enabled boots straight to a logged-in
desktop, and the encryption has bought nothing against the threat most
people actually have.

macOS keeps the setting as a single key in com.apple.loginwindow. The key
being absent is the safe state and is what `defaults` reports for a machine
that has never had it enabled — verified live, unprivileged.

Linux has no single mechanism, so this reads the display managers that are
common enough to be worth knowing: GDM and LightDM. A box running neither
reports unknown rather than a guess.
"""
import os
import platform
import re

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, run

_LOGINWINDOW = "/Library/Preferences/com.apple.loginwindow"

_LINUX_AUTOLOGIN_FILES = [
    "/etc/gdm3/custom.conf",
    "/etc/gdm/custom.conf",
    "/etc/lightdm/lightdm.conf",
    "/etc/sddm.conf",
]

# `AutomaticLogin=` with nothing after it is how GDM spells "off" while
# leaving the key in place, so an empty value must not count as enabled.
_AUTOLOGIN_ENABLED = re.compile(r"(?mi)^\s*(?:AutomaticLoginEnable|AutomaticLogin|autologin-user)\s*=\s*(\S+)")


def parse_macos_autologin(out, found):
    """`found` is whether the key exists at all. Absent is the safe state:
    macOS removes the key rather than blanking it when auto-login is turned
    off, so 'no such key' is a definite pass, not an unreadable answer."""
    if not found:
        return CheckResult(STATUS_PASS, "No account logs in automatically at startup.")
    account = out.strip()
    if not account:
        return CheckResult(STATUS_UNKNOWN, "The automatic-login setting exists but couldn't be read.")
    return CheckResult(STATUS_FAIL, f"'{account}' logs in automatically at startup, so anyone who "
                                    f"powers this machine on gets a logged-in desktop.")


def _macos_read():
    out = run(["defaults", "read", _LOGINWINDOW, "autoLoginUser"])
    # `defaults` prints its "does not exist" complaint on stderr and returns
    # nothing on stdout, so empty stdout is the absent case.
    return parse_macos_autologin(out, found=bool(out.strip()))


def parse_linux_autologin(contents):
    """contents: {path: text or None}. None means the file isn't there."""
    enabled_in = []
    read_any = False
    for path, text in contents.items():
        if text is None:
            continue
        read_any = True
        for match in _AUTOLOGIN_ENABLED.finditer(text):
            value = match.group(1).strip().strip('"')
            if value.lower() in ("false", "no", "0", ""):
                continue
            enabled_in.append(os.path.basename(path))
            break
    if enabled_in:
        return CheckResult(STATUS_FAIL, "Automatic login is configured in "
                                        + ", ".join(sorted(set(enabled_in))) + ".")
    if read_any:
        return CheckResult(STATUS_PASS, "No automatic login configured in the display "
                                        "manager settings this checks.")
    return CheckResult(STATUS_UNKNOWN, "No GDM, LightDM or SDDM configuration found — this "
                                       "desktop may set automatic login somewhere else.")


def _linux_read():
    contents = {}
    for path in _LINUX_AUTOLOGIN_FILES:
        if os.path.isfile(path):
            try:
                contents[path] = open(path).read()
            except OSError:
                contents[path] = None
        else:
            contents[path] = None
    return parse_linux_autologin(contents)


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Turn it off in System Settings → Users & Groups → Automatic login → Off, "
                "or from the command line:\n\n"
                "    sudo defaults delete /Library/Preferences/com.apple.loginwindow autoLoginUser\n\n"
                "Worth doing even on a desktop that never leaves the house: this is the "
                "setting that decides whether FileVault protects anything once the machine "
                "is switched on.")
    return ("Edit your display manager's configuration and disable automatic login:\n\n"
            "    GDM      /etc/gdm3/custom.conf   → AutomaticLoginEnable=false\n"
            "    LightDM  /etc/lightdm/lightdm.conf → comment out autologin-user\n"
            "    SDDM     /etc/sddm.conf          → clear the User= line under [Autologin]\n\n"
            "then reboot, or restart the display manager.")


CHECK = Check(
    id="auto-login",
    title="Automatic login",
    rationale="Automatic login hands the machine to whoever switches it on. It also undoes "
             "most of what disk encryption is for: an encrypted laptop that boots straight "
             "to a logged-in desktop is only encrypted while it's off.",
    severity="high",
    cis_topic="Automatic login / console session",
    read=read,
    remediation=remediation,
)
