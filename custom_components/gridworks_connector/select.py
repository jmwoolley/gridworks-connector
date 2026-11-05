"""Participation can change without changing physical plant control."""

from homeassistant.components.select import SelectEntity

from .const import PARTICIPATION
from .entity import ConnectorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Participation(entry.runtime_data, "participation", "Shadow participation")])


class Participation(ConnectorEntity, SelectEntity):
    _attr_options = PARTICIPATION

    @property
    def current_option(self):
        return self.runtime.engine.participation

    async def async_select_option(self, option):
        await self.runtime.set_participation(option)
