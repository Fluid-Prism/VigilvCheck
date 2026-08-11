# Posture

A local desktop app that checks this machine against a set of well-known
hardening basics, scores what it can actually determine, and explains each
gap in plain English with a copy-paste fix. It's the sibling to
[Kevscope](https://github.com/Fluid-Prism/Kevscope): Kevscope answers "what
vulnerable software is on this machine," Posture answers "is this machine
configured to resist an attack in the first place."

It runs on the machine you launch it on. Nothing is uploaded anywhere —
every check is a local read, and the only thing this app writes is its own
history of past scans, kept in a local SQLite file only you can read.

## What "posture score" actually means

A weighted percentage of the checks below that passed, weighted by how much
each one matters. That's it. A 100 means every check this tool knows how to
run passed — it does not mean this machine is secure. This tool checks eight
specific things. It doesn't check your passwords, your browser extensions,
whether you click links in phishing emails, or a hundred other things that
matter more day to day. Treat the score as "these particular basics are
covered," never as a verdict.

Checks that come back "couldn't determine" (need administrator access this
tool won't silently escalate to, or a desktop environment it doesn't know
how to read) are excluded from the score entirely — not counted as passed,
not held against you either. A `?` next to a check is the tool being honest
about the limits of what it can see, not a hidden fail.

## Run it

```bash
pip install -r requirements.txt      # PySide6 (Qt) — no network dependency at all
# or: pip install -e .

python3 -m posture                   # launch the desktop app
python3 -m posture.audit             # or the headless CLI
python3 -m posture.selftest          # offline checks (scoring math + registry integrity)
```

## The checks

| Check | Severity | macOS | Linux |
| --- | --- | --- | --- |
| Disk encryption | Critical | `fdesetup status` | root filesystem on a LUKS volume? |
| Firewall | Medium | Application Firewall | ufw, then firewalld |
| Automatic security updates | High | `com.apple.SoftwareUpdate` prefs | unattended-upgrades, then dnf-automatic |
| Screen lock on sleep | Medium | `sysadminctl -screenLock status` | GNOME only, via gsettings |
| Remote login (SSH) | High | needs admin access to read | `sshd_config` |
| Guest / extra-privileged accounts | Medium | Guest account toggle | extra UID-0 accounts, lightdm guest session |
| Gatekeeper | High | `spctl --status` | not applicable |
| System Integrity Protection | High | `csrutil status` | not applicable |

The macOS reads were tested against a real machine while this was built.
The Linux reads were written from documented behavior, not verified against
a live box — if one of them is wrong for your distro, that's a real bug,
please file it rather than assume the tool is right.

Two things worth knowing up front:

**Screen lock only works on GNOME.** KDE, Wayland compositors without a
screensaver daemon, and headless machines all report "couldn't determine"
rather than a guessed answer, because there's no single mechanism to check
across Linux desktops the way there is on macOS.

**System Integrity Protection can't be fixed with a command.** Apple built
SIP so nothing running in a normal session — root included — can turn it
back on; that's the point of it. If this check fails, the remediation is
reboot-into-Recovery-Mode instructions, not a one-liner, because a one-liner
that pretended to fix it from here would be lying to you.

## Why there's no auto-remediation yet

Every fix in this version is a copy-paste command plus an explanation of
what it does. Nothing runs automatically. That's deliberate, not an
unfinished feature:

- Reading system state is always safe. Changing it isn't. Enabling
  FileVault kicks off an encryption pass that takes hours and isn't
  something you casually undo — there's no clean "restore the old value"
  for a check like that the way there is for, say, toggling a firewall.
- This app would need per-action privilege escalation (`osascript`'s admin
  prompt on macOS, `pkexec` on Linux) done carefully, not a blanket "run the
  whole app as root" — this app warns rather than refuses if you do launch
  it as root, because nothing here needs it.
- Getting the trust story right — preview before running, snapshot before
  changing, a real undo where one actually exists, and an honest "this one
  can't be undone" where it doesn't — is real engineering that deserves its
  own pass, not something to bolt on after the fact.

Read-only first, then copy-paste remediation, then (eventually) one-click
for the handful of checks where undo genuinely works. That's the plan, in
that order.

## Files

```
posture/
  gui.py            PySide6 desktop app   (python3 -m posture)
  audit.py          headless CLI          (python3 -m posture.audit)
  scoring.py         severity-weighted score + ranked gap list
  store.py           SQLite: scan history (owner-only file permissions)
  selftest.py         offline checks: scoring math + registry integrity
  checks/
    base.py            the Check/CheckResult shape every check implements
    disk_encryption.py, firewall.py, auto_updates.py, screen_lock.py,
    remote_login.py, guest_account.py, gatekeeper_sip.py
```

## Adding a check

Each check is its own small module: an `id`, a `title`, a `rationale` (why
an attacker cares), a `severity`, a `cis_topic`, a `read()` that returns a
`CheckResult` (pass/fail/unknown/not_applicable — never guess), and a
`remediation()` that returns plain-English instructions plus a copy-paste
command. Write the module, add it to `ALL_CHECKS` in `checks/__init__.py`,
done. See any existing check for the pattern — `guest_account.py` is a
reasonably short one to start from.

CIS references in this codebase are topic-level, not a specific section
number — CIS benchmarks get revised per OS version and section numbers
shift between revisions, so hardcoding one that can't be verified against
the current PDF would be presenting a guess as fact. Look up the exact
control on cisecurity.org for the citation.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for dev setup and code style, and
[SECURITY.md](./SECURITY.md) to report a vulnerability.

## Roadmap

- Guided, one-click remediation for the checks where undo genuinely works
  (firewall, screen lock), with a preview and a snapshot of the old value
  first.
- Verify the Linux checks against real Debian, Fedora, and Arch installs
  instead of just documented behavior.
- KDE and Wayland-generic screen lock detection.
- Posture-over-time as an actual chart, not just a number in the history
  table.
- More checks: browser autofill/password-manager presence, SSH key
  strength, sudo timeout configuration.
