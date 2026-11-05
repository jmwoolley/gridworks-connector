"""Connector actions only: snapshots, notices and test messages, never equipment."""

from homeassistant.components.button import ButtonEntity

from .entity import ConnectorEntity

BUTTONS = {
    "snapshot": ("Send observations", "snapshot"),
    "changed": ("System changed — request reassessment", "system_changed"),
    "scenarios": ("Exercise shadow protocol", "run_scenarios"),
    "acknowledge": ("Acknowledge reassessment notices", "acknowledge_notices"),
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(Action(entry.runtime_data, key, *value) for key, value in BUTTONS.items())


class Action(ConnectorEntity, ButtonEntity):
    def __init__(self, runtime, key, name, action):
        super().__init__(runtime, key, name)
        self.action = action

    async def async_press(self):
        await getattr(self.runtime, self.action)()
