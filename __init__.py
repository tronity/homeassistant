"""The Tronity integration."""
from __future__ import annotations
import aiohttp
import async_timeout
import asyncio
from datetime import timedelta
import logging


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_VEHICLE_ID,
    CONF_CLIENT_SECRET,
    CONF_VEHICLE_DATA,
    CONF_AUTH_URL,
    CONF_DATA_COORDINATOR,
    CONF_VEHICLES_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tronity from a config entry."""

    client_id = (entry.data[CONF_CLIENT_ID],)
    client_secret = (entry.data[CONF_CLIENT_SECRET],)
    vehicle_id = entry.data[CONF_VEHICLE_ID]
    auth_url = CONF_AUTH_URL
    vehicle_url = CONF_VEHICLES_URL

    async def get_bearer_token(client_id: str, client_secret: str) -> str:
        """Get bearer token for authentication."""

        async with aiohttp.ClientSession() as session:
            async with session.post(
                auth_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "app",
                },
            ) as response:
                response_json = await response.json()
                bearer_token = response_json.get("access_token")
                return bearer_token

    async def async_update_data():
        """Fetch data from Tronity API."""
        bearer_token = await get_bearer_token(client_id, client_secret)
        headers = {"Authorization": f"Bearer {bearer_token}"}

        try:
            async with async_timeout.timeout(30):
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        vehicle_url + vehicle_id + "/last_record",
                        headers=headers,
                    ) as response:
                        data = await response.json()
                        hass.data[DOMAIN][entry.entry_id][CONF_VEHICLE_DATA] = data
                        return data

        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timeout while communicating with API") from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {CONF_DATA_COORDINATOR: coordinator}

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class TronityEntity(CoordinatorEntity):
    """Defines a base Mazda entity."""

    _attr_has_entity_name = True

    @property
    def data(self):
        """Shortcut to access coordinator data for the entity."""
        return self.coordinator.data
