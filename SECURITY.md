# Security Policy

VigilvCheck runs entirely on your own machine. It reads local system
configuration (FileVault/LUKS status, firewall state, update settings,
screen lock, SSH config, account list, Gatekeeper/SIP status) and writes
only its own scan history to a local SQLite file. It never sends anything
over the network, never installs or changes anything on the host, and never
runs a remediation command for you — see the README for why that last one
is deliberate.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security report.

Use GitHub's private vulnerability reporting instead: repo → Security →
Report a vulnerability.

If that isn't available, email **developers@fluidprism.com** with a
description and, if possible, a minimal reproduction. We'll acknowledge
within a few days and aim to have a fix or mitigation out within 30 days for
confirmed issues, sooner for anything actively exploitable.

## Scope

In scope: anything that lets VigilvCheck be tricked into running unintended
commands, escalating privileges, leaking data anywhere, or misreporting a
failing check as passing (a false "secure" is worse than a false alarm,
given the whole point of this tool).

Expected, not a vulnerability by itself: some checks (remote login on
macOS) need administrator access just to *read* the answer, and this app
will attempt a non-interactive `sudo -n` and report "couldn't determine"
rather than prompt for a password — seeing that behavior is correct, not a
bug. Running as an unprivileged local user and having checks that need
elevation come back "unknown" is the intended behavior.

## Supported versions

VigilvCheck is pre-1.0, unreleased; only the latest commit on the default
branch is supported.
