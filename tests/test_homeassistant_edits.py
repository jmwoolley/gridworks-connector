"""Native reconfiguration and event ordering, with temporary pytest-only entities."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gridworks_connector.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_edit_limits_preserves_channel_identity_and_reloads(hass, profile):
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Test", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await entry.runtime_data.tick()
    previous = entry.runtime_data
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"target": "bindings/temperature-1"}
    )
    assert result["step_id"] == "temperature"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "entity_id": "sensor.test_temperature",
            "label": "Refined state",
            "unit": "°C",
            "lower": 15,
            "upper": 80,
            "stale_seconds": 300,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert previous.closed
    assert entry.runtime_data.profile["bindings"][0]["channel_id"] == "temperature-1"
    assert entry.runtime_data.profile["bindings"][0]["limits"]["lower"] == 15
    await entry.runtime_data.tick()
    assert entry.runtime_data.engine.last_decision.disposition == "would_pursue"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_rapid_mode_visit_between_snapshots_is_retained(hass, profile):
    profile["modes"].append({"mode_id": "B", "label": "B", "declared_available": True})
    profile["bindings"].append(
        {
            "channel_id": "mode",
            "kind": "current_mode",
            "entity_id": "sensor.test_mode",
            "attribute": None,
            "label": "Mode",
            "registry_id": None,
            "stale_seconds": 300,
            "timestamp_basis": "ha_report_time",
            "unit": None,
            "limits": None,
        }
    )
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.test_mode", "A")
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Test", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    runtime = entry.runtime_data
    hass.states.async_set("sensor.test_mode", "B")
    hass.states.async_set("sensor.test_mode", "A")
    await hass.async_block_till_done()
    async with runtime.lock:
        trace = await hass.async_add_executor_job(runtime.journal.trace)
    modes = [
        row["message"]["Payload"]["ModeId"]
        for row in trace
        if row["direction"] == "out" and row["message"]["TypeName"].endswith("mode.event")
    ]
    assert modes[-2:] == ["B", "A"]
    await hass.config_entries.async_unload(entry.entry_id)
