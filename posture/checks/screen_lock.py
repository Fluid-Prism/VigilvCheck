"""screen_lock.py — does walking away from the machine actually lock it?

macOS: `sysadminctl -screenLock status` — its answer is on stderr, not
stdout (verified live). Unprivileged and doesn't hang, also verified live.
Linux: GNOME's screensaver settings via gsettings. Only covers GNOME —
KDE, Wayland compositors without a screensaver daemon, and headless boxes
all report unknown here rather than a guessed answer, since there's no
single mechanism to check across Linux desktops the way there is on macOS.
"""
import platform
import re

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, have, run, run_stderr

_MAX_REASONABLE_DELAY_SECONDS = 300  # 5 minutes


def _macos_read():
    err = run_stderr(["sysadminctl", "-screenLock", "status"])
    m = re.search(r"screenLock delay is (\d+) seconds?", err)
    if m:
        delay = int(m.group(1))
        if delay <= _MAX_REASONABLE_DELAY_SECONDS:
            return CheckResult(STATUS_PASS, f"Screen lock engages {delay} seconds after sleep/screensaver.")
        return CheckResult(STATUS_FAIL, f"Screen lock delay is {delay} seconds, more than 5 minutes.")
    if "off" in err.lower():
        return CheckResult(STATUS_FAIL, "Screen lock is off.")
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse sysadminctl's answer: {err.strip() or '(no output)'}")


def _linux_read():
    if not have("gsettings"):
        return CheckResult(STATUS_UNKNOWN, "gsettings not found — not a GNOME session, "
                                           "can't check screen lock this way.")
    lock_enabled = run(["gsettings", "get", "org.gnome.desktop.screensaver", "lock-enabled"]).strip()
    if lock_enabled == "":
        return CheckResult(STATUS_UNKNOWN, "Couldn't read GNOME screensaver settings.")
    if lock_enabled == "true":
        delay = run(["gsettings", "get", "org.gnome.desktop.session", "idle-delay"]).strip()
        return CheckResult(STATUS_PASS, f"GNOME screen lock is enabled (idle-delay: {delay or 'unknown'}).")
    return CheckResult(STATUS_FAIL, "GNOME screen lock is disabled.")


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Set this in System Settings → Lock Screen → \"Require password after screen "
                "saver begins or display is turned off\", or from the command line:\n\n"
                "    sysadminctl -screenLock immediate")
    return ("On GNOME:\n\n"
            "    gsettings set org.gnome.desktop.screensaver lock-enabled true\n"
            "    gsettings set org.gnome.desktop.session idle-delay 300\n\n"
            "On KDE or another desktop, the equivalent is in your system settings under "
            "Screen Locking — there's no single command-line equivalent across desktops.")


CHECK = Check(
    id="screen-lock",
    title="Screen lock on sleep",
    rationale="Without this, anyone who walks up to an unattended, unlocked machine has "
             "full access to whatever you're logged into, no password needed.",
    severity="medium",
    cis_topic="Screen lock / session timeout",
    read=read,
    remediation=remediation,
)
