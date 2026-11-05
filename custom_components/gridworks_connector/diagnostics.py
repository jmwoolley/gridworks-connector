"""Diagnostics exclude credentials, addresses, selected entity names and telemetry."""

from .const import PROTOCOL_REVISION, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    r = entry.runtime_data
    return {
        "version": VERSION,
        "protocol_revision": PROTOCOL_REVISION,
        "shadow_only": True,
        "physical_actions_supported": False,
        "channel_count": len(r.profile["bindings"]),
        "mode_count": len(r.profile["modes"]),
        "meter_count": len(r.profile["meters"]),
        "service_count": len(r.profile["services"]),
        "transport_mode": r.profile["transport"]["mode"],
        "connected": r.connected,
        "peer_fresh": r.engine.peer_fresh,
        "last_error": r.last_error or r.engine.last_error,
        "last_protocol_check": r.last_protocol_check,
    }
