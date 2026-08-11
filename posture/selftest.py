"""selftest.py — offline checks for the logic that doesn't depend on this
machine's actual state: scoring math and registry integrity. The checks
themselves read real system state, so they're not something a fixed offline
test can assert against the way a version comparator can.

    python3 -m posture.selftest
"""
from .checks import ALL_CHECKS
from .checks.base import SEVERITY_WEIGHT, STATUS_FAIL, STATUS_NA, STATUS_PASS, STATUS_UNKNOWN, Check, CheckResult
from .checks import auto_updates, disk_encryption, firewall, gatekeeper_sip, guest_account, remote_login, screen_lock
from .scoring import ranked_gaps, run_all, score


def _fake(severity, status):
    check = Check(id="x", title="x", rationale="x", severity=severity, cis_topic="x",
                 read=lambda: None, remediation=lambda: "x")
    return check, CheckResult(status, "x")


def check_score_basic():
    # one critical pass, one low fail -> weighted, not a plain average
    results = [_fake("critical", STATUS_PASS), _fake("low", STATUS_FAIL)]
    s, applicable = score(results)
    expected = round(100 * SEVERITY_WEIGHT["critical"] / (SEVERITY_WEIGHT["critical"] + SEVERITY_WEIGHT["low"]))
    assert s == expected, f"score() = {s}, want {expected}"
    assert applicable == 2
    return 1


def check_score_excludes_unknown_and_na():
    results = [_fake("high", STATUS_PASS), _fake("high", STATUS_UNKNOWN), _fake("high", STATUS_NA)]
    s, applicable = score(results)
    assert s == 100, f"unknown/N/A shouldn't count against the score, got {s}"
    assert applicable == 1
    return 1


def check_score_none_when_nothing_applicable():
    results = [_fake("high", STATUS_UNKNOWN), _fake("critical", STATUS_NA)]
    s, applicable = score(results)
    assert s is None, "score() should be None, not 0, when nothing was determinable"
    assert applicable == 0
    return 1


def check_ranked_gaps_severity_order():
    results = [_fake("low", STATUS_FAIL), _fake("critical", STATUS_FAIL),
              _fake("medium", STATUS_FAIL), _fake("high", STATUS_PASS)]
    gaps = ranked_gaps(results)
    severities = [c.severity for c, r in gaps]
    assert severities == ["critical", "medium", "low"], f"got {severities}"
    return 1


def check_run_all_isolates_a_broken_check():
    def broken_read():
        raise ValueError("simulated bug")
    bad = Check(id="bad", title="Bad", rationale="x", severity="low", cis_topic="x",
               read=broken_read, remediation=lambda: "x")
    good = Check(id="good", title="Good", rationale="x", severity="low", cis_topic="x",
                read=lambda: CheckResult(STATUS_PASS, "fine"), remediation=lambda: "x")
    results = run_all([good, bad])
    by_id = {c.id: r for c, r in results}
    assert by_id["good"].status == STATUS_PASS, "a bug in one check corrupted an unrelated one"
    assert by_id["bad"].status == STATUS_UNKNOWN, "an unexpected exception should degrade to unknown, not propagate"
    return 1


def _assert(actual, expected_status, label):
    assert actual.status == expected_status, f"{label}: got {actual.status}, want {expected_status} ({actual.detail})"


def check_parse_disk_encryption():
    _assert(disk_encryption.parse_fdesetup("FileVault is On."), STATUS_PASS, "fdesetup on")
    _assert(disk_encryption.parse_fdesetup("FileVault is Off."), STATUS_FAIL, "fdesetup off")
    _assert(disk_encryption.parse_fdesetup("garbage"), STATUS_UNKNOWN, "fdesetup garbage")
    _assert(disk_encryption.parse_lsblk_type("crypt", "/dev/mapper/x"), STATUS_PASS, "lsblk crypt")
    _assert(disk_encryption.parse_lsblk_type("part", "/dev/sda1"), STATUS_FAIL, "lsblk plain partition")
    _assert(disk_encryption.parse_lsblk_type("", "/dev/sda1"), STATUS_UNKNOWN, "lsblk empty")
    return 6


def check_parse_firewall():
    _assert(firewall.parse_socketfilterfw("Firewall is enabled. (State = 1)"), STATUS_PASS, "socketfilterfw on")
    _assert(firewall.parse_socketfilterfw("Firewall is disabled. (State = 0)"), STATUS_FAIL, "socketfilterfw off")
    assert firewall.parse_ufw_status("Status: active") .status == STATUS_PASS
    assert firewall.parse_ufw_status("Status: inactive").status == STATUS_FAIL
    assert firewall.parse_ufw_status("") is None, "unparseable ufw output should fall through, not guess"
    assert firewall.parse_firewalld_state("running").status == STATUS_PASS
    assert firewall.parse_firewalld_state("not running").status == STATUS_FAIL
    assert firewall.parse_firewalld_state("") is None
    return 8


def check_parse_auto_updates():
    _assert(auto_updates.parse_macos_su_keys("1", "1"), STATUS_PASS, "software update both on")
    _assert(auto_updates.parse_macos_su_keys("0", "1"), STATUS_FAIL, "software update download off")
    _assert(auto_updates.parse_macos_su_keys("", ""), STATUS_UNKNOWN, "software update unreadable")
    _assert(auto_updates.parse_apt_auto_upgrades('APT::Periodic::Unattended-Upgrade "1";'), STATUS_PASS, "apt on")
    _assert(auto_updates.parse_apt_auto_upgrades('APT::Periodic::Unattended-Upgrade "0";'), STATUS_FAIL, "apt off")
    assert auto_updates.parse_dnf_automatic_timer("enabled").status == STATUS_PASS
    assert auto_updates.parse_dnf_automatic_timer("disabled").status == STATUS_FAIL
    assert auto_updates.parse_dnf_automatic_timer("") is None, "missing unit should fall through, not guess"
    return 8


def check_parse_screen_lock():
    _assert(screen_lock.parse_sysadminctl("screenLock delay is 0 seconds\n"), STATUS_PASS, "screenlock immediate")
    _assert(screen_lock.parse_sysadminctl("screenLock delay is 300 seconds\n"), STATUS_PASS, "screenlock 5 min")
    _assert(screen_lock.parse_sysadminctl("screenLock delay is 3600 seconds\n"), STATUS_FAIL, "screenlock 1hr")
    _assert(screen_lock.parse_sysadminctl("screenLock is off\n"), STATUS_FAIL, "screenlock off")
    _assert(screen_lock.parse_sysadminctl("garbage\n"), STATUS_UNKNOWN, "screenlock garbage")
    _assert(screen_lock.parse_gnome_lock("true", "300"), STATUS_PASS, "gnome lock on")
    _assert(screen_lock.parse_gnome_lock("false", ""), STATUS_FAIL, "gnome lock off")
    _assert(screen_lock.parse_gnome_lock("", ""), STATUS_UNKNOWN, "gnome lock unreadable")
    return 8


def check_parse_remote_login():
    assert remote_login.parse_systemsetup("Remote Login: On").status == STATUS_FAIL
    assert remote_login.parse_systemsetup("Remote Login: Off").status == STATUS_PASS
    assert remote_login.parse_systemsetup("You need administrator access...") is None

    safe_config = "PermitRootLogin no\nPasswordAuthentication no\n"
    risky_config = "PermitRootLogin yes\nPasswordAuthentication yes\n"
    unset_config = "# nothing set here\nPort 22\n"
    _assert(remote_login.parse_sshd_config(safe_config), STATUS_PASS, "sshd_config hardened")
    _assert(remote_login.parse_sshd_config(risky_config), STATUS_FAIL, "sshd_config wide open")
    _assert(remote_login.parse_sshd_config(unset_config), STATUS_UNKNOWN, "sshd_config unset directives")
    return 6


def check_parse_guest_account():
    _assert(guest_account.parse_guest_enabled("0"), STATUS_PASS, "guest disabled")
    _assert(guest_account.parse_guest_enabled("1"), STATUS_FAIL, "guest enabled")
    _assert(guest_account.parse_guest_enabled(""), STATUS_UNKNOWN, "guest unreadable")

    normal_passwd = "root:x:0:0:root:/root:/bin/bash\nvarun:x:1000:1000::/home/varun:/bin/bash\n"
    extra_root_passwd = "root:x:0:0:root:/root:/bin/bash\nbackdoor:x:0:0::/home/backdoor:/bin/bash\n"
    _assert(guest_account.parse_passwd_and_lightdm(normal_passwd, None), STATUS_PASS, "no extra root")
    _assert(guest_account.parse_passwd_and_lightdm(extra_root_passwd, None), STATUS_FAIL, "extra UID-0")
    _assert(guest_account.parse_passwd_and_lightdm(normal_passwd, "allow-guest=true"), STATUS_FAIL, "lightdm guest on")
    _assert(guest_account.parse_passwd_and_lightdm(normal_passwd, "allow-guest=false"), STATUS_PASS, "lightdm guest off")
    return 6


def check_parse_gatekeeper_sip():
    _assert(gatekeeper_sip.parse_spctl("assessments enabled"), STATUS_PASS, "gatekeeper on")
    _assert(gatekeeper_sip.parse_spctl("assessments disabled"), STATUS_FAIL, "gatekeeper off")
    _assert(gatekeeper_sip.parse_spctl(""), STATUS_UNKNOWN, "gatekeeper unreadable")
    _assert(gatekeeper_sip.parse_csrutil("System Integrity Protection status: enabled."), STATUS_PASS, "sip on")
    _assert(gatekeeper_sip.parse_csrutil("System Integrity Protection status: disabled."), STATUS_FAIL, "sip off")
    _assert(gatekeeper_sip.parse_csrutil(""), STATUS_UNKNOWN, "sip unreadable")
    return 6


def check_registry_integrity():
    ids = [c.id for c in ALL_CHECKS]
    assert len(ids) == len(set(ids)), f"duplicate check ids: {ids}"
    assert len(ALL_CHECKS) >= 1, "registry is empty"
    for c in ALL_CHECKS:
        assert c.severity in SEVERITY_WEIGHT, f"{c.id} has an unknown severity: {c.severity}"
        assert c.title and c.rationale and c.cis_topic, f"{c.id} is missing required text"
        assert callable(c.read) and callable(c.remediation), f"{c.id} read/remediation isn't callable"
    return len(ALL_CHECKS)


def main():
    total = 0
    for name, fn in [("score weighting", check_score_basic),
                     ("score excludes unknown/N/A", check_score_excludes_unknown_and_na),
                     ("score is None, not 0, when nothing applicable", check_score_none_when_nothing_applicable),
                     ("ranked gaps ordering", check_ranked_gaps_severity_order),
                     ("run_all isolates a broken check", check_run_all_isolates_a_broken_check),
                     ("parse: disk encryption", check_parse_disk_encryption),
                     ("parse: firewall", check_parse_firewall),
                     ("parse: auto updates", check_parse_auto_updates),
                     ("parse: screen lock", check_parse_screen_lock),
                     ("parse: remote login", check_parse_remote_login),
                     ("parse: guest account", check_parse_guest_account),
                     ("parse: gatekeeper/SIP", check_parse_gatekeeper_sip),
                     ("registry integrity", check_registry_integrity)]:
        n = fn()
        total += n
        print(f"  ✓ {name:<45} {n} case(s)")
    print(f"\n  All {total} checks passed.\n")


if __name__ == "__main__":
    main()
