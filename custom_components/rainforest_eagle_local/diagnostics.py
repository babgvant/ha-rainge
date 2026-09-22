"""Diagnostics for Rainforest EAGLE Local."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
    CONF_PROTOCOL,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_PROTOCOL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    INTEGRATION_VERSION,
)
from .coordinator import EagleCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[EagleCoordinator]
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    cloud_id = entry.data.get(CONF_CLOUD_ID, "")
    masked_cloud_id = f"***{cloud_id[-4:]}" if cloud_id else ""
    return {
        "integration_version": INTEGRATION_VERSION,
        "configuration": async_redact_data(
            {
                **entry.data,
                **entry.options,
                CONF_CLOUD_ID: masked_cloud_id,
            },
            {CONF_INSTALL_CODE},
        ),
        "transport": {
            "protocol": entry.options.get(
                CONF_PROTOCOL, entry.data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
            ),
            "verify_ssl": entry.options.get(
                CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            ),
            "update_interval": entry.options.get(
                CONF_UPDATE_INTERVAL,
                entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ),
        },
        "meter": coordinator.data.meter.as_dict(),
        "latest_response": {
            "root": coordinator.api.last_response_root,
            "bytes": coordinator.api.last_response_bytes,
        },
        "available_variables": sorted(coordinator.data.readings),
    }
