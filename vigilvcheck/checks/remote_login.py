"""remote_login.py — is SSH reachable, and if so, is it configured safely?

macOS: `systemsetup -getremotelogin` needs administrator access even just to
read the answer — verified live, it refuses outright for a plain user. This
tries a non-interactive sudo first (works for free if the caller already has
a live sudo session from something else) and reports unknown rather than
prompting or guessing if that fails.

Linux: reads /etc/ssh/sshd_config directly (usually world-readable, no
elevation needed). If a directive isn't explicitly set, this reports unknown
for it rather than assuming either the secure or insecure OpenSSH default —
those defaults have changed across OpenSSH versions and distros. No SSH
server installed at all is treated as a pass: no service, no attack surface.
"""
import os
import platform
import re

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, have, try_sudo_n


def parse_systemsetup(out):
    """None means the output didn't give a definitive on/off answer at all —
    distinct from the caller not having permission to ask in the first place."""
    if "On" in out:
        return CheckResult(STATUS_FAIL, "Remote Login (SSH) is on.")
    if "Off" in out:
        return CheckResult(STATUS_PASS, "Remote Login (SSH) is off.")
    return None


def _macos_read():
    ok, out = try_sudo_n(["systemsetup", "-getremotelogin"])
    if ok:
        result = parse_systemsetup(out)
        if result:
            return result
    return CheckResult(STATUS_UNKNOWN, "Checking this needs administrator access. Run "
                                       "`sudo systemsetup -getremotelogin` yourself to see the answer.")


def parse_sshd_config(content):
    root_login = re.search(r"(?m)^\s*PermitRootLogin\s+(\S+)", content)
    password_auth = re.search(r"(?m)^\s*PasswordAuthentication\s+(\S+)", content)
    problems, unclear = [], []

    if root_login:
        if root_login.group(1).lower() not in ("no", "prohibit-password"):
            problems.append(f"PermitRootLogin {root_login.group(1)}")
    else:
        unclear.append("PermitRootLogin isn't set explicitly")

    if password_auth:
        if password_auth.group(1).lower() == "yes":
            problems.append("PasswordAuthentication yes")
    else:
        unclear.append("PasswordAuthentication isn't set explicitly")

    if problems:
        return CheckResult(STATUS_FAIL, "Risky sshd_config settings: " + ", ".join(problems) + ".")
    if unclear:
        return CheckResult(STATUS_UNKNOWN, "; ".join(unclear) + " — depends on your OpenSSH "
                                           "version's compiled-in default.")
    return CheckResult(STATUS_PASS, "sshd_config explicitly disables root login and password auth.")


def _linux_read():
    if not (have("sshd") or os.path.isfile("/etc/ssh/sshd_config")):
        return CheckResult(STATUS_PASS, "No SSH server installed. Nothing to harden here.")
    try:
        content = open("/etc/ssh/sshd_config").read()
    except OSError:
        return CheckResult(STATUS_UNKNOWN, "sshd_config exists but isn't readable.")
    return parse_sshd_config(content)


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("If you don't need to SSH into this machine remotely, turn it off in System "
                "Settings → General → Sharing → Remote Login, or:\n\n"
                "    sudo systemsetup -setremotelogin off")
    return ("Edit /etc/ssh/sshd_config and set:\n\n"
            "    PermitRootLogin no\n"
            "    PasswordAuthentication no\n\n"
            "then restart sshd:\n\n"
            "    sudo systemctl restart sshd\n\n"
            "PasswordAuthentication no requires key-based login already being set up for your "
            "account — confirm you can SSH in with a key before you disable passwords, or you "
            "can lock yourself out.")


CHECK = Check(
    id="remote-login",
    title="Remote login (SSH)",
    rationale="An SSH server accepting root logins or plain passwords is a direct target "
             "for credential-stuffing and brute-force attacks the moment it's reachable.",
    severity="high",
    cis_topic="SSH daemon configuration",
    read=read,
    remediation=remediation,
)
