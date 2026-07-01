"""Config flow for Janitza Modbus."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .modbus import JanitzaModbusClient, JanitzaModbusError
from .registers import MIN_REGISTER_ADDRESS
from .validation import normalize_host

_LOGGER = logging.getLogger(__name__)


async def _async_validate_connection(
    host: str, port: int, unit_id: int
) -> None:
    """Validate that the device answers at the generic 19xxx block."""
    client = JanitzaModbusClient(host, port, unit_id)
    try:
        await client.async_read_holding_registers(MIN_REGISTER_ADDRESS, 2)
    finally:
        await client.async_close()


class JanitzaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Janitza Modbus config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input = _normalize_user_input(user_input)
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}"
                )
                self._abort_if_unique_id_configured()

            if not errors:
                try:
                    await _async_validate_connection(
                        user_input[CONF_HOST],
                        user_input[CONF_PORT],
                        user_input[CONF_UNIT_ID],
                    )
                except JanitzaModbusError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating Janitza device")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return JanitzaOptionsFlow(config_entry)


class JanitzaOptionsFlow(config_entries.OptionsFlow):
    """Handle Janitza Modbus options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Janitza options."""
        if user_input is not None:
            user_input = _normalize_options_input(user_input)
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={**self._config_entry.data, **user_input},
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry.data),
        )


def _user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Return the user setup schema."""
    defaults = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=65535,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                )
            ),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=247,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=3600,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector values before saving config entry data."""
    return {
        **user_input,
        CONF_HOST: normalize_host(user_input[CONF_HOST]),
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
    }


def _normalize_options_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector values before saving option updates."""
    return {
        **user_input,
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
    }


def _options_schema(data: dict[str, Any]) -> vol.Schema:
    """Return the options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=3600,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            )
        }
    )
