"""firewall.py — is a host firewall actually blocking anything?

macOS: the Application Firewall via socketfilterfw. Unprivileged, verified live.
Linux: ufw, then firewalld, in that order — the two most common front ends.
If neither is present this reports unknown rather than trying to interpret
raw nftables/iptables rules, which vary too much to read generically (a
default-deny ruleset and a default-allow one can look superficially similar
without parsing every rule in order).
"""
import platform

from .base import Check, CheckResult, STATUS_FAIL, STATUS_PASS, STATUS_UNKNOWN, have, run


def _macos_read():
    out = run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]).strip()
    if "enabled" in out.lower():
        return CheckResult(STATUS_PASS, out)
    if "disabled" in out.lower():
        return CheckResult(STATUS_FAIL, out)
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse socketfilterfw output: {out or '(empty)'}")


def _linux_read():
    if have("ufw"):
        out = run(["ufw", "status"])
        if "Status: active" in out:
            return CheckResult(STATUS_PASS, "ufw is active.")
        if "Status: inactive" in out:
            return CheckResult(STATUS_FAIL, "ufw is installed but inactive.")
    if have("firewall-cmd"):
        out = run(["firewall-cmd", "--state"]).strip()
        if out == "running":
            return CheckResult(STATUS_PASS, "firewalld is running.")
        if out == "not running":
            return CheckResult(STATUS_FAIL, "firewalld is installed but not running.")
    return CheckResult(STATUS_UNKNOWN, "No ufw or firewalld found. This machine might be using "
                                       "nftables or iptables directly, which this check doesn't parse.")


def read():
    return _macos_read() if platform.system() == "Darwin" else _linux_read()


def remediation():
    if platform.system() == "Darwin":
        return ("Turn on the firewall in System Settings → Network → Firewall, or run:\n\n"
                "    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on")
    return ("If ufw is installed:\n\n    sudo ufw enable\n\n"
            "If you're on a firewalld-based distro (Fedora, RHEL, CentOS) instead:\n\n"
            "    sudo systemctl enable --now firewalld\n\n"
            "If neither is installed, `sudo apt install ufw && sudo ufw enable` (Debian/Ubuntu) "
            "is the simplest way to get a sane default-deny baseline.")


CHECK = Check(
    id="firewall",
    title="Firewall",
    rationale="Without a host firewall, any service that starts listening on a port — "
             "intentionally or by a misconfigured app — is reachable from the network by "
             "default instead of needing an explicit allow rule.",
    severity="medium",
    cis_topic="Host-based firewall",
    read=read,
    remediation=remediation,
)
