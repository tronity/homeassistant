"""Platform for Tronity device tracker integration."""
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DATA_COORDINATOR
from . import TronityEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up the device tracker platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DATA_COORDINATOR]

    async_add_entites([TronityDeviceTracker(coordinator, config_entry)])


class TronityDeviceTracker(TronityEntity, TrackerEntity):
    """Class for the device tracker."""

    _attr_icon = "mdi:map"
    _attr_force_update = False

    def __init__(self, coordinator, config_entry) -> None:
        """Initialize Tronity device tracker."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{self.vehicle_id}_device_tracker"

    @property
    def name(self) -> str:
        """Return name of the sensor."""
        return f"{self.vehicle_id}_device_tracker"

    @property
    def source_type(self) -> SourceType:
        """Return the source type"""
        return SourceType.GPS

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self.coordinator.data["latitude"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self.coordinator.data["longitude"]
