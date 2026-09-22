"""Sensors for Rainforest EAGLE Local."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EagleCoordinator


@dataclass(frozen=True, kw_only=True)
class EagleSensorDescription(SensorEntityDescription):
    """Description of an EAGLE variable sensor."""


SENSORS = (
    EagleSensorDescription(
        key="zigbee:InstantaneousDemand",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    EagleSensorDescription(
        key="zigbee:CurrentSummationDelivered",
        translation_key="energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    EagleSensorDescription(
        key="zigbee:CurrentSummationReceived",
        translation_key="energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    EagleSensorDescription(
        key="zigbee:Voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    EagleSensorDescription(
        key="zigbee:Current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    EagleSensorDescription(
        key="zigbee:Frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    EagleSensorDescription(key="zigbee:Price", translation_key="price"),
    EagleSensorDescription(key="zigbee:RateLabel", translation_key="rate_label"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[EagleCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        EagleReadingSensor(coordinator, description) for description in SENSORS
    ]
    entities.extend(
        (EagleConnectionSensor(coordinator), EagleLastContactSensor(coordinator))
    )
    async_add_entities(entities)


class EagleBaseSensor(CoordinatorEntity[EagleCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EagleCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.meter.hardware_address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        meter = self.coordinator.data.meter
        return DeviceInfo(
            identifiers={(DOMAIN, meter.hardware_address.lower())},
            name=meter.name,
            manufacturer=meter.manufacturer or "Rainforest Automation",
            model=meter.model_id,
            via_device=(DOMAIN, self.coordinator.config_entry.entry_id),
        )


class EagleReadingSensor(EagleBaseSensor):
    def __init__(
        self, coordinator: EagleCoordinator, description: EagleSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key.replace("zigbee:", "").lower())
        self.entity_description = description
        self._description = description
        self._attr_translation_key = description.translation_key
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._description.key in self.coordinator.data.readings
        )

    @property
    def native_value(self) -> Any:
        reading = self.coordinator.data.readings.get(self._description.key)
        if reading is None:
            return None
        value = reading.value
        if not isinstance(value, Decimal):
            return value
        target = self._description.native_unit_of_measurement
        if reading.unit == "W" and target == UnitOfPower.KILO_WATT:
            return value / 1000
        if reading.unit == "Wh" and target == UnitOfEnergy.KILO_WATT_HOUR:
            return value / 1000
        return value

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        reading = self.coordinator.data.readings.get(self._description.key)
        if (
            reading
            and reading.unit
            and reading.unit != self._description.native_unit_of_measurement
        ):
            return {"api_unit": reading.unit}
        return None


class EagleConnectionSensor(EagleBaseSensor):
    _attr_translation_key = "connection_status"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: EagleCoordinator) -> None:
        super().__init__(coordinator, "connection_status")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.meter.connection_status

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        meter = self.coordinator.data.meter
        return {"network_address": meter.network_address, "protocol": meter.protocol}


class EagleLastContactSensor(EagleBaseSensor):
    _attr_translation_key = "last_contact"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: EagleCoordinator) -> None:
        super().__init__(coordinator, "last_contact")

    @property
    def native_value(self) -> datetime | None:
        try:
            return datetime.fromtimestamp(
                int(self.coordinator.data.meter.last_contact, 0), tz=UTC
            )
        except (ValueError, OSError, OverflowError):
            return None
