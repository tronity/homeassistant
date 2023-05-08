import aiohttp
import asyncio
import async_timeout
from datetime import timedelta
import logging


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)


from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_VEHICLES_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_VEHICLE_ID,
    CONF_DISPLAY_NAME,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def get_bearer_token(client_id: str, client_secret: str) -> str:
    base_url = CONF_BASE_URL

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                base_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "app",
                },
            ) as response:
                response_json = await response.json()
                bearer_token = response_json.get("access_token")

    except aiohttp.client_exceptions.ContentTypeError:
        _LOGGER.warning("Failed to decode JSON response, trying again in one minute")
        bearer_token = None

    return bearer_token


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = TronityCoordinator(
        hass,
        client_id=config_entry.data[CONF_CLIENT_ID],
        client_secret=config_entry.data[CONF_CLIENT_SECRET],
        vehicle_id=config_entry.data[CONF_VEHICLE_ID],
    )
    await coordinator.async_refresh()
    async_add_entities(
        [
            Odometer(hass, coordinator, config_entry),
            Range(hass, coordinator, config_entry),
            Level(hass, coordinator, config_entry),
            Charging(hass, coordinator, config_entry),
            Plugged(hass, coordinator, config_entry),
            ChargerPower(hass, coordinator, config_entry),
            ChargeRemainingTime(hass, coordinator, config_entry),
            DisplayName(hass, coordinator, config_entry),
        ],
        True,
    )


class TronityCoordinator(DataUpdateCoordinator):
    """Initialize Tronity Coordinator."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, vehicle_id: str
    ) -> None:
        super().__init__(hass, _LOGGER, name="tronity")
        self.client_id = client_id
        self.client_secret = client_secret
        self.vehicle_id = vehicle_id
        self.base_url = CONF_VEHICLES_URL

    async def _async_update_data(self):
        bearer_token = await get_bearer_token(self.client_id, self.client_secret)
        headers = {"Authorization": f"Bearer {bearer_token}"}

        if bearer_token == None:
            return self.data

        else:
            try:
                async with async_timeout.timeout(30):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            self.base_url + self.vehicle_id + "/last_record",
                            headers=headers,
                        ) as response:
                            self.data = await response.json()
                            return self.data
            except asyncio.TimeoutError as exc:
                raise UpdateFailed("Timeout while communicating with API") from exc


class Odometer(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.odometer"
        )
        self.coordinator = coordinator
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_native_unit_of_measurement = "km"
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_odometer"

    async def async_update(self) -> None:
        data = await self.coordinator._async_update_data()
        if data is not None:
            self._attr_native_value = data["odometer"]


class Range(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.remaining_range"
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_native_unit_of_measurement = "km"
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_remaining_range"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["range"]


class Level(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.battery_level"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = "%"
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_battery_level"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["level"]


class Charging(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charging"
        )
        self._attr_device_class = None
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_charging"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["charging"]


class Plugged(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = (
            f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.plugged"
        )
        self._attr_device_class = None
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [False, True]
        self._attr_native_value = False
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_plugged"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["plugged"]


class ChargerPower(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charger_power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = "kW"
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_charger_power"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["chargerPower"]


class ChargeRemainingTime(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.charge_remaining_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "s"
        self._attr_native_value = 0
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_charge_remaining_time"

    async def async_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            self._attr_native_value = data["chargerPower"]


class DisplayName(SensorEntity):
    def __init__(
        self, hass: HomeAssistant, coordinator: TronityCoordinator, my_api: ConfigEntry
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"tronity.{hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]}.display_name"
        self._attr_device_class = None
        self._attr_native_value = hass.data[DOMAIN][my_api.entry_id][CONF_DISPLAY_NAME]
        self._attr_unique_id = f"{self.coordinator.vehicle_id}_display_name"
