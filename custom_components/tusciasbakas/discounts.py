"""Discount rule parser for Tuščias bakas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


DAY_ALIASES = {
    "mon": 0, "monday": 0, "pir": 0, "pirmadienis": 0,
    "tue": 1, "tuesday": 1, "ant": 1, "antradienis": 1,
    "wed": 2, "wednesday": 2, "tre": 2, "treciadienis": 2, "trečiadienis": 2,
    "thu": 3, "thursday": 3, "ket": 3, "ketvirtadienis": 3,
    "fri": 4, "friday": 4, "pen": 4, "penktadienis": 4,
    "sat": 5, "saturday": 5, "ses": 5, "šeštadienis": 5, "sestadienis": 5,
    "sun": 6, "sunday": 6, "sek": 6, "sekmadienis": 6,
}


@dataclass(slots=True, frozen=True)
class DiscountRule:
    pattern: str
    weekdays: frozenset[int]
    amount_eur_l: float
    source: str

    def active(self, station_text: str, today: date) -> bool:
        return self.pattern.casefold() in station_text.casefold() and today.weekday() in self.weekdays


def parse_discount_rules(text: str) -> tuple[list[DiscountRule], list[str]]:
    """Parse station;days;discount lines."""
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
                    errors.append(f"{lineno} eilutė: neatpažinta diena '{day.strip()}'")
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
