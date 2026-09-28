"""Pure calculations for signed EAGLE grid power."""

from __future__ import annotations

from decimal import Decimal


def split_grid_power(
    value: Decimal, unit: str | None
) -> tuple[Decimal, Decimal] | None:
    """Split signed meter demand into positive import and export kW."""
    if unit == "W":
        value /= 1000
    elif unit not in ("kW", None, ""):
        return None
    return max(value, Decimal(0)), max(-value, Decimal(0))
