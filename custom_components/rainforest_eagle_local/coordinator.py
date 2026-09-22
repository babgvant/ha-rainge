"""Data coordinator for Rainforest EAGLE Local."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EagleError, EagleLocalApi, Meter, MeterReading
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN


@dataclass(frozen=True, slots=True)
class EagleData:
    """Latest gateway data."""

    meter: Meter
    readings: dict[str, MeterReading]


class EagleCoordinator(DataUpdateCoordinator[EagleData]):
    """Poll one EAGLE meter efficiently."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: EagleLocalApi,
        meter: Meter,
    ) -> None:
        self.api = api
        self.meter = meter
        interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> EagleData:
        try:
            self.meter, readings = await self.api.async_get_meter_data(self.meter)
        except EagleError as err:
            raise UpdateFailed(str(err)) from err
        return EagleData(self.meter, readings)
