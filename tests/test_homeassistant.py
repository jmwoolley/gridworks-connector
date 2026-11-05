"""Native HA2026.11 config flow, runtime and unload tests in an isolated fixture."""

import json

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gridworks_connector.const import DOMAIN
from custom_components.gridworks_connector.diagnostics import async_get_config_entry_diagnostics
from custom_components.gridworks_connector.runtime import read_value

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_setup_observes_only_selected_entities_and_unloads(hass, profile):
    hass.states.async_set("sensor.test_temperature", "35", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.unselected", "99", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Test", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    runtime = entry.runtime_data
    assert len(runtime.last_snapshot) == 1
    assert runtime.last_snapshot[0].value == 35
    await runtime.tick()
    assert runtime.engine.peer_fresh
    assert runtime.engine.last_decision is not None
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert "sensor.test_temperature" not in json.dumps(diag)
    assert diag["physical_actions_supported"] is False
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert runtime.closed and not runtime.unsubscribers and not runtime.tasks


async def test_native_flow_requires_limits_and_supports_repeated_channels(hass):
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Commissioned test"}
    )
    assert result["step_id"] == "menu"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["errors"]["base"] == "incomplete"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "temperature"}
    )
    assert result["step_id"] == "temperature"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "entity_id": "sensor.test_temperature",
            "label": "First state",
            "unit": "°C",
            "lower": 80,
            "upper": 10,
            "stale_seconds": 300,
        },
    )
    assert result["errors"]["base"] == "invalid_mapping"
    for label in ("First state", "Second state"):
        if result["step_id"] == "menu":
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"next_step_id": "temperature"}
            )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": "sensor.test_temperature",
                "label": label,
                "unit": "°C",
                "lower": 10,
                "upper": 80,
                "stale_seconds": 300,
            },
        )
        assert result["step_id"] == "menu"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    assert len(result["data"]["bindings"]) == 2
    assert (
        result["data"]["bindings"][0]["channel_id"] != result["data"]["bindings"][1]["channel_id"]
    )
    await hass.async_block_till_done()
    entry = result["result"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unknown_delivery_and_no_equipment_calls(hass, profile):
    hass.states.async_set("sensor.test_temperature", "unavailable", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Test", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    runtime = entry.runtime_data
    assert runtime.last_snapshot[0].quality == "unavailable"
    status = runtime.peer.received["service.status"]["Payload"]
    assert status["Delivered"] is None and status["Requested"] is None
    await runtime.set_participation("paused")
    assert runtime.engine.participation == "paused"
    await runtime.system_changed()
    assert "configuration.change" in runtime.peer.received
    await hass.config_entries.async_unload(entry.entry_id)


async def test_source_timestamp_never_refreshed_by_sampling(hass, profile):
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    state = hass.states.get("sensor.test_temperature")
    binding = profile["bindings"][0]
    stamp = int(state.last_reported.timestamp() * 1000)
    first = read_value(state, binding, stamp + 1000)
    second = read_value(state, binding, stamp + 400000)
    assert first[1] == second[1] == stamp
    assert first[2] == "reported" and second[2] == "stale"


async def test_weather_ui_confirms_proposal_and_backup(hass, profile):
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Test", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "weather"}
    )
    assert result["step_id"] == "weather"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "primary_source": "site",
            "backup_sources": ["remote-pending"],
            "confirmed": True,
        },
    )
    assert result["step_id"] == "menu"
    assert entry.runtime_data.engine.weather_selection["primary_source"] == "site"
    assert entry.runtime_data.peer.weather == "site"
    await hass.config_entries.async_unload(entry.entry_id)
