from __future__ import annotations

import re


_MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


def is_mac_address_valid(value: str | None) -> bool:
    if not value:
        return False
    return bool(_MAC_PATTERN.match(value))


__all__ = ["is_mac_address_valid"]
