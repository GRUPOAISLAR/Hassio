"""Config flow for Local BGH Smart integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_IGNORE_KIT_MODE,
    CONF_INVERT_DIRECTION,
    DEVICE_TYPE_CLIMATE,
    DEVICE_TYPES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_CLIMATE): SelectSelector(
            SelectSelectorConfig(
                options=DEVICE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_DEVICE_TYPE,
            )
        ),
        vol.Optional(CONF_INVERT_DIRECTION, default=False): cv.boolean,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local BGH Smart."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate MAC address format
            mac = user_input[CONF_MAC].upper().replace("-", ":")
            if not self._is_valid_mac(mac):
                errors[CONF_MAC] = "invalid_mac"
            
            # Validate IP address format
            ip_address = user_input[CONF_IP_ADDRESS]
            if not self._is_valid_ip(ip_address):
                errors[CONF_IP_ADDRESS] = "invalid_ip"
            
            if not errors:
                # Create unique ID from MAC address
                await self.async_set_unique_id(mac.replace(":", ""))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_MAC: mac,
                        CONF_IP_ADDRESS: ip_address,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                        CONF_INVERT_DIRECTION: user_input.get(CONF_INVERT_DIRECTION, False),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _is_valid_mac(self, mac: str) -> bool:
        """Validate MAC address format."""
        import re
        return bool(re.match(r"^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$", mac))

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False


class OptionsFlow(config_entries.OptionsFlow):
    """Options for an HVAC kit."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if self.config_entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_CLIMATE) != DEVICE_TYPE_CLIMATE:
            return self.async_abort(reason="no_options")

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORE_KIT_MODE,
                        default=self.config_entry.options.get(CONF_IGNORE_KIT_MODE, False),
                    ): cv.boolean,
                }
            ),
        )
