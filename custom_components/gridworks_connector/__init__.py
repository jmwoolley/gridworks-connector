"""GridWorks Connector. This draft is permanently shadow-only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    from .runtime import Runtime

    runtime = Runtime(hass, entry, dict(entry.options or entry.data))
    entry.runtime_data = runtime
    try:
        await runtime.start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await runtime.close()
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.close()
