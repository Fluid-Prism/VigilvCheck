"""auto_updates.py — will critical security patches actually get installed?

macOS: reads specific keys from com.apple.SoftwareUpdate rather than parsing
`softwareupdate --schedule`'s one-line summary, which only reports whether
checking is on, not whether downloads or critical-update installs are.
Unprivileged, verified live.

Linux: unattended-upgrades (Debian/Ubuntu) via its config file, falling back
to dnf-automatic's systemd timer (Fedora/RHEL). Not verified live, no Linux
box to test against here.
"""
import os
import platform
import re

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, run

_SU_DOMAIN = "/Library/Preferences/com.apple.SoftwareUpdate"


def _macos_key(key):
    return run(["defaults", "read", _SU_DOMAIN, key]).strip()


def parse_macos_su_keys(auto_download, critical):
    if auto_download == "" and critical == "":
        return CheckResult(STATUS_UNKNOWN, "Couldn't read com.apple.SoftwareUpdate preferences.")
    missing = []
    if auto_download != "1":
        missing.append("automatic download")
    if critical != "1":
        missing.append("automatic critical security update installs")
    if missing:
        return CheckResult(STATUS_FAIL, "Off: " + ", ".join(missing) + ".")
    return CheckResult(STATUS_PASS, "Automatic download and critical security update installs are on.")


def _macos_read():
    return parse_macos_su_keys(_macos_key("AutomaticDownload"), _macos_key("CriticalUpdateInstall"))


def parse_apt_auto_upgrades(content):
    if re.search(r'Unattended-Upgrade\s+"1"', content):
        return CheckResult(STATUS_PASS, "unattended-upgrades is enabled.")
    return CheckResult(STATUS_FAIL, "unattended-upgrades is installed but not enabled.")


def parse_dnf_automatic_timer(out):
    """None means systemctl's output didn't give a definitive answer at all
    (the unit doesn't exist) — distinct from finding it explicitly disabled."""
    out = out.strip()
    if out == "enabled":
        return CheckResult(STATUS_PASS, "dnf-automatic.timer is enabled.")
    if out:
        return CheckResult(STATUS_FAIL, "dnf-automatic.timer exists but isn't enabled.")
    return None


def _linux_read():
    apt_conf = "/etc/apt/apt.conf.d/20auto-upgrades"
    if os.path.isfile(apt_conf):
        try:
            content = open(apt_conf).read()
        except OSError:
            content = ""
        return parse_apt_auto_upgrades(content)
    result = parse_dnf_automatic_timer(run(["systemctl", "is-enabled", "dnf-automatic.timer"]))
    if result:
        return result
    return CheckResult(STATUS_UNKNOWN, "No unattended-upgrades or dnf-automatic found. "
                                       "This distro may use a different mechanism.")


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Turn on \"Install Security Responses and system files\" and automatic "
                "download in System Settings → General → Software Update → Automatic Updates, "
                "or set both from the command line:\n\n"
                "    sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate "
                "AutomaticDownload -bool true\n"
                "    sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate "
                "CriticalUpdateInstall -bool true")
    return ("On Debian/Ubuntu:\n\n    sudo apt install unattended-upgrades\n"
            "    sudo dpkg-reconfigure -plow unattended-upgrades\n\n"
            "On Fedora/RHEL:\n\n    sudo dnf install dnf-automatic\n"
            "    sudo systemctl enable --now dnf-automatic.timer")


CHECK = Check(
    id="auto-updates",
    title="Automatic security updates",
    rationale="Most real-world compromises exploit a vulnerability that already has a "
             "patch available. If updates need a person to notice and click install, they "
             "get delayed, sometimes indefinitely.",
    severity="high",
    cis_topic="Automatic / unattended security updates",
    read=read,
    remediation=remediation,
)
