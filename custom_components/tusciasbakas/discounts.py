"""Discount handling for Tuščias bakas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


DAY_ALIASES = {
    "mon": 0, "monday": 0, "pir": 0, "pirmadienis": 0,
    "tue": 1, "tuesday": 1, "ant": 1, "antradienis": 1,
    "wed": 2, "wednesday": 2, "tre": 2, "treciadienis": 2, "trečiadienis": 2,
    "thu": 3, "thursday": 3, "ket": 3, "ketvirtadienis": 3,
    "fri": 4, "friday": 4, "pen": 4, "penktadienis": 4,
    "sat": 5, "saturday": 5, "ses": 5, "šeštadienis": 5, "sestadienis": 5,
    "sun": 6, "sunday": 6, "sek": 6, "sekmadienis": 6,
}

DAY_SHORT = ["Pir", "Ant", "Tre", "Ket", "Pen", "Šeš", "Sek"]


@dataclass(slots=True, frozen=True)
class DiscountRule:
    pattern: str
    weekdays: frozenset[int]
    amount_eur_l: float
    source: str

    def active(self, station_text: str, today: date) -> bool:
        return (
            self.pattern.casefold() in station_text.casefold()
            and today.weekday() in self.weekdays
        )


def parse_discount_rules(text: str) -> tuple[list[DiscountRule], list[str]]:
    """Parse legacy station;days;discount lines."""
    rules: list[DiscountRule] = []
    errors: list[str] = []

    for lineno, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split(";")]
        if len(parts) != 3:
            errors.append(f"{lineno} eilutė: reikia formato Degalinė;dienos;nuolaida")
            continue

        pattern, days_raw, amount_raw = parts
        if not pattern:
            errors.append(f"{lineno} eilutė: trūksta degalinės pavadinimo")
            continue

        if days_raw.casefold() in {"all", "kasdien", "daily", "*"}:
            weekdays = frozenset(range(7))
        else:
            day_values: set[int] = set()
            for day in days_raw.split(","):
                key = day.strip().casefold()
                if key not in DAY_ALIASES:
                    errors.append(
                        f"{lineno} eilutė: neatpažinta diena '{day.strip()}'"
                    )
                    day_values.clear()
                    break
                day_values.add(DAY_ALIASES[key])
            if not day_values:
                continue
            weekdays = frozenset(day_values)

        try:
            amount = float(amount_raw.replace(",", "."))
        except ValueError:
            errors.append(f"{lineno} eilutė: neteisinga nuolaida '{amount_raw}'")
            continue
        if not 0 <= amount <= 1:
            errors.append(f"{lineno} eilutė: nuolaida turi būti 0–1 €/l")
            continue

        rules.append(DiscountRule(pattern, weekdays, amount, line))

    return rules, errors


def rules_from_structured(items: list[dict[str, Any]] | None) -> list[DiscountRule]:
    """Convert UI-friendly structured discounts to runtime rules."""
    result: list[DiscountRule] = []
    for item in items or []:
        try:
            network = str(item["network"]).strip()
            weekdays = frozenset(int(day) for day in item.get("weekdays", []))
            amount = float(item["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if not network or not weekdays or not 0 <= amount <= 1:
            continue

        days = ", ".join(DAY_SHORT[d] for d in sorted(weekdays) if 0 <= d <= 6)
        result.append(
            DiscountRule(
                pattern=network,
                weekdays=weekdays,
                amount_eur_l=amount,
                source=f"{network}: {days} −{amount:.2f} €/l",
            )
        )
    return result


def structured_from_legacy(text: str) -> list[dict[str, Any]]:
    """Convert old free-text rules so upgrades keep existing discounts."""
    rules, _ = parse_discount_rules(text)
    return [
        {
            "network": rule.pattern,
            "weekdays": sorted(rule.weekdays),
            "amount": rule.amount_eur_l,
        }
        for rule in rules
    ]


def structured_rule_label(item: dict[str, Any]) -> str:
    """Human readable label for the options flow."""
    network = str(item.get("network", "Degalinė"))
    weekdays = [
        DAY_SHORT[int(day)]
        for day in item.get("weekdays", [])
        if str(day).isdigit() and 0 <= int(day) <= 6
    ]
    amount = float(item.get("amount", 0) or 0)
    return f"{network} · {', '.join(weekdays)} · −{amount:.2f} €/l"
