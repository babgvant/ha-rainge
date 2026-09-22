"""Config flow for Rainforest EAGLE Local."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    EagleAuthenticationError,
    EagleConnectionError,
    EagleLocalApi,
    EagleResponseError,
    EagleTimeoutError,
)
from .const import (
    CONF_CLOUD_ID,
    CONF_INSTALL_CODE,
    CONF_PROTOCOL,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_PROTOCOL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
    REQUEST_TIMEOUT,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
            vol.Required(CONF_CLOUD_ID, default=values.get(CONF_CLOUD_ID, "")): str,
            vol.Required(CONF_INSTALL_CODE): str,
            vol.Required(
                CONF_PROTOCOL, default=values.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["https", "http"], mode=SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(
                CONF_VERIFY_SSL,
                default=values.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): bool,
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=values.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL,
                    max=300,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


async def _validate(flow: ConfigFlow, data: dict[str, Any]) -> str:
    api = EagleLocalApi(
        async_get_clientsession(flow.hass),
        data[CONF_HOST],
        data[CONF_CLOUD_ID],
        data[CONF_INSTALL_CODE],
        protocol=data[CONF_PROTOCOL],
        verify_ssl=data[CONF_VERIFY_SSL],
        timeout=REQUEST_TIMEOUT,
    )
    meters = await api.async_get_devices()
    return meters[0].hardware_address


class EagleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an EAGLE config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_credentials_step("user", user_input)

    async def _async_credentials_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                hardware_address = await _validate(self, user_input)
            except EagleAuthenticationError:
                errors["base"] = "invalid_auth"
            except EagleTimeoutError:
                errors["base"] = "timeout"
            except EagleConnectionError:
                errors["base"] = "cannot_connect"
            except EagleResponseError:
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(hardware_address.lower())
                if step_id == "reauth_confirm":
                    entry = self._get_reauth_entry()
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"EAGLE {user_input[CONF_HOST]}", data=user_input
                )
        return self.async_show_form(
            step_id=step_id,
            data_schema=_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._reauth_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            entry = self._get_reauth_entry()
            defaults = dict(entry.data)
            defaults.pop(CONF_INSTALL_CODE, None)
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=_schema(defaults)
            )
        return await self._async_credentials_step("reauth_confirm", user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EagleOptionsFlow(config_entry)


class EagleOptionsFlow(OptionsFlow):
    """Handle polling and transport options."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROTOCOL,
                        default=current.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["https", "http"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=current.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=current.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=300,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
        )
