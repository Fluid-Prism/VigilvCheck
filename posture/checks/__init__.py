"""checks — the registry. Every check module exposes a module-level CHECK
(or, for gatekeeper_sip, two). ALL_CHECKS is the single source of truth the
rest of the app runs against — add a new check by writing a module here and
adding it to this list, nothing else needs to know about it.
"""
from . import (
    auto_updates,
    disk_encryption,
    firewall,
    gatekeeper_sip,
    guest_account,
    remote_login,
    screen_lock,
)

ALL_CHECKS = [
    disk_encryption.CHECK,
    firewall.CHECK,
    auto_updates.CHECK,
    screen_lock.CHECK,
    remote_login.CHECK,
    guest_account.CHECK,
    gatekeeper_sip.GATEKEEPER_CHECK,
    gatekeeper_sip.SIP_CHECK,
]
