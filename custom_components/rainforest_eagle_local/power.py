"""Pure calculations for signed EAGLE grid power."""

from __future__ import annotations

from decimal import Decimal


def split_grid_power(
    value: Decimal, unit: str | None
) -> tuple[Decimal, Decimal] | None:
    """Split signed meter demand into positive import and export kW."""
    if unit == "W":
        value /= 1000
    elif unit != "kW" and not (unit in (None, "") and value == 0):
        return None
    return max(value, Decimal(0)), max(-value, Decimal(0))
