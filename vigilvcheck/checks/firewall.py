"""firewall.py — is a host firewall actually blocking anything?

macOS: the Application Firewall via socketfilterfw. Unprivileged, verified live.
Linux: ufw, then firewalld, in that order — the two most common front ends.
If neither is present this reports unknown rather than trying to interpret
raw nftables/iptables rules, which vary too much to read generically (a
default-deny ruleset and a default-allow one can look superficially similar
without parsing every rule in order).
"""
import platform

from .base import (Check, CheckResult, STATUS_FAIL, STATUS_NA, STATUS_PASS,
                   STATUS_UNKNOWN, have, run)


def parse_socketfilterfw(out):
    out = out.strip()
    if "enabled" in out.lower():
        return CheckResult(STATUS_PASS, out)
    if "disabled" in out.lower():
        return CheckResult(STATUS_FAIL, out)
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse socketfilterfw output: {out or '(empty)'}")


def _macos_read():
    return parse_socketfilterfw(run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]))


def parse_ufw_status(out):
    """None means ufw's output didn't give a definitive answer — the caller
    should fall through to the next front end, not treat that as unknown yet."""
    if "Status: active" in out:
        return CheckResult(STATUS_PASS, "ufw is active.")
    if "Status: inactive" in out:
        return CheckResult(STATUS_FAIL, "ufw is installed but inactive.")
    return None


def parse_firewalld_state(out):
    out = out.strip()
    if out == "running":
        return CheckResult(STATUS_PASS, "firewalld is running.")
    if out == "not running":
        return CheckResult(STATUS_FAIL, "firewalld is installed but not running.")
    return None


def _linux_read():
    if have("ufw"):
        result = parse_ufw_status(run(["ufw", "status"]))
        if result:
            return result
    if have("firewall-cmd"):
        result = parse_firewalld_state(run(["firewall-cmd", "--state"]))
        if result:
            return result
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


def parse_stealth_mode(out):
    out = (out or "").strip().lower()
    if "stealth mode is on" in out or "stealth mode is enabled" in out:
        return CheckResult(STATUS_PASS, "Stealth mode is on — this machine doesn't answer "
                                        "unsolicited probes.")
    if "stealth mode is off" in out or "stealth mode is disabled" in out:
        return CheckResult(STATUS_FAIL, "Stealth mode is off, so this machine answers pings "
                                        "and probes from any network it's on.")
    return CheckResult(STATUS_UNKNOWN, f"Couldn't parse the stealth mode setting: {out or '(empty)'}")


def _stealth_read():
    if platform.system() != "Darwin":
        return CheckResult(STATUS_NA, "Stealth mode is a macOS Application Firewall feature. "
                                      "The nearest Linux equivalent is an ICMP policy in your "
                                      "own firewall rules, which varies too much to check here.")
    return parse_stealth_mode(
        run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getstealthmode"]))


def _stealth_remediation():
    return ("Turn it on in System Settings → Network → Firewall → Options → Enable stealth "
            "mode, or run:\n\n"
            "    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on\n\n"
            "This stops the machine replying to pings and to probes on closed ports, so it "
            "doesn't announce itself to anything scanning the network. It's a smaller win "
            "than the firewall itself — someone on your network can still find you other "
            "ways — but it costs nothing on a laptop that joins networks you don't control.")


STEALTH_CHECK = Check(
    id="firewall-stealth",
    title="Firewall stealth mode",
    rationale="With stealth mode off, this machine answers unsolicited pings and probes, "
             "confirming it exists to anything sweeping the network it's joined.",
    severity="low",
    cis_topic="Host-based firewall / stealth mode",
    read=_stealth_read,
    remediation=_stealth_remediation,
)


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
