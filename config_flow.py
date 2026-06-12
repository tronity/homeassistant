"""Config flow for Tronity integration."""
from __future__ import annotations

import asyncio
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
    CONF_AUTH_URL,
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


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""

    hub = TronityHub(
        hass, data[CONF_CLIENT_ID], data[CONF_CLIENT_SECRET], data[CONF_VEHICLE_ID]
    )

    bearer_token = await hub.authenticate()
    title = await hub.get_display_name(bearer_token)

    return {"title": title}


class TronityHub:
    """Initialize the TronityHub class for API authentication."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, vehicle_id: str
    ) -> None:
        """Initialize."""
        self.base_url = CONF_AUTH_URL
        self.vehicle_url = CONF_VEHICLES_URL
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.vehicle_id = vehicle_id

    async def get_bearer_token(self) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "app",
                    },
                    timeout=10,
                ) as response:
                    if response.status in (401, 403):
                        raise InvalidAuth
                    if response.status >= 400:
                        raise CannotConnect

                    response_json = await response.json()
                    bearer_token = response_json.get("access_token")
                    if not bearer_token:
                        raise InvalidAuth
                    return bearer_token
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect from err

    async def get_display_name(self, bearer_token: str) -> str:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.vehicle_url + self.vehicle_id,
                    headers=headers,
                    timeout=10,
                ) as response:
                    if response.status in (401, 403):
                        raise InvalidAuth
                    if response.status >= 400:
                        raise CannotConnect

                    data = await response.json()
                    display_name = data.get("displayName")
                    if not display_name:
                        raise CannotConnect
                    return display_name
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect from err

    async def authenticate(self) -> str:
        return await self.get_bearer_token()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tronity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_VEHICLE_ID])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
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


class CannotConnect(HomeAssistantError):
    """Error to indicate there was a connection problem."""
