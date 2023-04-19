"""Config flow for Tronity integration."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_BASE_URL,
    CONF_VEHICLE_ID,
    CONF_VEHICLES_URL,
    CONF_DISPLAY_NAME,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID, default=""): str,
        vol.Required(CONF_CLIENT_SECRET, default=""): str,
        vol.Required(CONF_VEHICLE_ID, default=""): str,
    }
)


class TronityHub:
    """Initialize the TronityHub class for API authentication."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, vehicle_id: str
    ) -> None:
        """Initialize."""
        self.base_url = CONF_BASE_URL
        self.vehicle_url = CONF_VEHICLES_URL
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.vehicle_id = vehicle_id

    async def get_bearer_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "app",
                },
            ) as response:
                response_json = await response.json()
                bearer_token = response_json.get("access_token")

        return bearer_token

    async def get_display_name(self) -> str:
        bearer_token = await self.get_bearer_token()
        headers = {"Authorization": f"Bearer {bearer_token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.vehicle_url + self.vehicle_id,
                headers=headers,
            ) as response:
                data = await response.json()
                return data["displayName"]

    async def get_api_status(self) -> int:
        """Handle the start of the TronityHub config flow, validating user input and creating an entry."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "app",
                },
            ) as response:
                return response.status

    async def authenticate(self) -> bool:
        status_code = await self.get_api_status()

        if status_code == 201 or status_code == 200:
            return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    hub = TronityHub(
        hass, data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET], data[CONF_VEHICLE_ID]
    )

    if not await hub.authenticate():
        raise InvalidAuth

    title = await hub.get_display_name()

    return {"title": title}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tronity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                entry_data = {**user_input, CONF_DISPLAY_NAME: info["title"]}
                return self.async_create_entry(title=info["title"], data=entry_data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
