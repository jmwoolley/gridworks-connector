"""Status entities belong only to the connector; no equipment entities are written."""

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN


class ConnectorEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime, key, name):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.profile['resource_id']}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.profile["resource_id"])},
            name=runtime.profile["name"],
            manufacturer="GridWorks Connector",
            model="Shadow-only development connector",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.runtime.signal, self.async_write_ha_state)
        )
