"""Explicit transport and shadow-only status."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ConnectorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            Status(entry.runtime_data, "connected", "Transport connected"),
            Status(entry.runtime_data, "shadow", "Shadow only"),
        ]
    )


class Status(ConnectorEntity, BinarySensorEntity):
    @property
    def is_on(self):
        if self._attr_unique_id.endswith("_shadow"):
            return True
        return self.runtime.connected
