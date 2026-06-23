from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TronityEntity
from .const import CONF_DATA_COORDINATOR, DOMAIN


BINARY_SENSOR_ENTITIES = [
    BinarySensorEntityDescription(
        key="charging",
        icon="mdi:battery-charging",
    ),
    BinarySensorEntityDescription(
        key="plugged",
        icon="mdi:power-plug",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_DATA_COORDINATOR]

    entities = [
        TronityBinarySensorEntity(coordinator, description, config_entry)
        for description in BINARY_SENSOR_ENTITIES
    ]

    async_add_entities(entities)


class TronityBinarySensorEntity(TronityEntity, BinarySensorEntity):
    """Representation of a Tronity vehicle binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description, config_entry: ConfigEntry) -> None:
        """Initialize Tronity binary sensor."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        # Keep existing sensor unique_ids untouched and create parallel binary entities.
        self._attr_unique_id = f"{self.vehicle_id}_{description.key}_binary"

    @property
    def name(self) -> str:
        """Return name of the binary sensor."""
        return f"tronity.{self.display_name}.{self.entity_description.key}_binary"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.data.get(self.entity_description.key)

        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value != 0

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on", "charging", "plugged"}:
                return True
            if normalized in {"false", "0", "no", "off", "not_charging", "unplugged"}:
                return False

        return None
