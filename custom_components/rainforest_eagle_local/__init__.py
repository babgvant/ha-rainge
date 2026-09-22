"""Rainforest EAGLE Local integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EagleAuthenticationError, EagleError, EagleLocalApi
from .const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
    CONF_PROTOCOL,
    CONF_VERIFY_SSL,
    DEFAULT_PROTOCOL,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
    REQUEST_TIMEOUT,
)
from .coordinator import EagleCoordinator

type EagleConfigEntry = ConfigEntry[EagleCoordinator]


def _api(hass: HomeAssistant, entry: ConfigEntry) -> EagleLocalApi:
    return EagleLocalApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_CLOUD_ID],
        entry.data[CONF_INSTALL_CODE],
        protocol=entry.options.get(
            CONF_PROTOCOL, entry.data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
        ),
        verify_ssl=entry.options.get(
            CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        ),
        timeout=REQUEST_TIMEOUT,
    )


async def async_setup_entry(hass: HomeAssistant, entry: EagleConfigEntry) -> bool:
    """Set up an EAGLE entry."""
    api = _api(hass, entry)
    try:
        meters = await api.async_get_devices()
    except EagleAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except EagleError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = EagleCoordinator(hass, entry, api, meters[0])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("rainforest_eagle_local", entry.entry_id)},
        name=f"Rainforest EAGLE ({entry.data[CONF_HOST]})",
        manufacturer="Rainforest Automation",
        model="EAGLE Gateway",
        configuration_url=f"{entry.data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)}://{entry.data[CONF_HOST]}",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EagleConfigEntry) -> bool:
    """Unload an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
