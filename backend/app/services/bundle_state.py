from __future__ import annotations

from trishul_snmp import MibBundle

_bundle: MibBundle | None = None


def get_bundle() -> MibBundle | None:
    return _bundle


def set_bundle(bundle: MibBundle | None) -> None:
    global _bundle
    _bundle = bundle
