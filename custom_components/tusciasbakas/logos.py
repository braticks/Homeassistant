"""Fuel network logo helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

NETWORK_DOMAINS = {
    "circle k": "circlek.lt",
    "circlek": "circlek.lt",
    "neste": "neste.lt",
    "viada": "viada.lt",
    "orlen": "orlen.lt",
    "baltic petroleum": "balticpetroleum.lt",
    "balticpetroleum": "balticpetroleum.lt",
    "jozita": "jozita.lt",
    "emsi": "emsi.lt",
    "saurida": "saurida.lt",
}

def station_logo_url(station: dict[str, Any] | None) -> str | None:
    """Return a network logo/favicon URL for a station when known."""
    if not station:
        return None

    text = " ".join(
        str(station.get(key, ""))
        for key in ("network", "name")
    ).casefold()

    for pattern, domain in NETWORK_DOMAINS.items():
        if pattern in text:
            return (
                "https://www.google.com/s2/favicons"
                f"?sz=128&domain_url={quote('https://' + domain, safe=':/')}"
            )
    return None
