"""Native HA flow, serialized panel schemas and existing-entry migration checks."""

import json
import os
from pathlib import Path

import pytest
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gridworks_connector.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def view(result):
    assert result["step_id"] == "dashboard"
    return json.loads(result["description_placeholders"]["dashboard"])


async def start(hass, profile):
    hass.states.async_set("sensor.test_temperature", "30", {"unit_of_measurement": "°C"})
    entry = MockConfigEntry(domain=DOMAIN, data=profile, title="Existing resource", version=1)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "dashboard"}
    )
    return entry, flow


async def test_grouped_panel_existing_setup_add_cancel_save(hass, profile):
    entry, flow = await start(hass, profile)
    panel = hass.data[DATA_PANELS]["gridworks-connector"]
    assert panel.require_admin
    assert panel.config_panel_domain == DOMAIN
    fixture = {}

    def capture(name, result):
        fixture[name] = {
            key: result[key] for key in ("type", "step_id", "description_placeholders")
        }

    capture("initial", flow)
    state = view(flow)
    assert state["categories"][0]["entries"][0]["source"] == "sensor.test_temperature"
    assert not state["dirty"]

    async def act(**data):
        return await hass.config_entries.options.async_configure(flow["flow_id"], data)

    flow = await act(action="open", step="temperature", category="thermal")
    capture("temperature", flow)
    assert view(flow)["form"]["step_id"] == "temperature"
    assert any(
        field["name"] == "entity_id" and "selector" in field
        for field in view(flow)["form"]["data_schema"]
    )
    data = dict(
        entity_id="sensor.test_temperature", label="Added state", unit="°C", lower=90, upper=10
    )
    flow = await act(action="submit", data=data)
    assert view(flow)["form"]["errors"]["base"] == "invalid_mapping"
    assert not entry.options
    flow = await act(action="back")
    assert not view(flow)["dirty"]
    flow = await act(action="open", step="temperature", category="thermal")
    data.update(lower=20, upper=80)
    flow = await act(action="submit", data=data)
    capture("added", flow)
    assert view(flow)["dirty"] and view(flow)["form"] is None
    assert not entry.options
    assert len(view(flow)["categories"][0]["entries"]) == 2
    flow = await act(action="save")
    assert flow["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.options["revision"] == 2
    assert entry.options["bindings"][0]["channel_id"] == "temperature-1"
    assert len(entry.runtime_data.profile["bindings"]) == 2
    if output := os.environ.get("CONNECTOR_UI_FIXTURE"):
        reopened = await hass.config_entries.options.async_init(entry.entry_id)
        reopened = await hass.config_entries.options.async_configure(
            reopened["flow_id"], {"next_step_id": "dashboard"}
        )
        capture("saved", reopened)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_grouped_editor_prefill_identity_and_safe_removal(hass, profile):
    entry, flow = await start(hass, profile)

    async def act(**data):
        return await hass.config_entries.options.async_configure(flow["flow_id"], data)

    flow = await act(action="edit", target="bindings/temperature-1")
    fields = {field["name"]: field for field in view(flow)["form"]["data_schema"]}
    assert fields["entity_id"]["description"]["suggested_value"] == "sensor.test_temperature"
    flow = await act(
        action="submit",
        data=dict(
            entity_id="sensor.test_temperature", label="Edited state", unit="°C", lower=15, upper=85
        ),
    )
    assert view(flow)["categories"][0]["entries"][0]["target"] == "bindings/temperature-1"
    flow = await act(action="open", step="signal", category="electric")
    fields = {field["name"]: field for field in view(flow)["form"]["data_schema"]}
    assert fields["kind"]["selector"]["select"]["options"] == ["power", "energy"]
    flow = await act(action="back")
    flow = await act(action="remove", target="bindings/temperature-1")
    flow = await act(action="save")
    assert view(flow)["form"]["errors"]["base"] == "incomplete"
    assert not entry.options
    await hass.config_entries.async_unload(entry.entry_id)


async def test_cancel_multistep_connection_editor_restores_draft(hass, profile):
    entry, flow = await start(hass, profile)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "open", "step": "transport"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"action": "submit", "data": {"mode": "mqtt"}}
    )
    assert view(flow)["form"]["step_id"] == "broker"
    flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"action": "back"})
    assert not view(flow)["dirty"]
    assert view(flow)["categories"][-1]["summary"] == "Embedded demonstration"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_browser_http_round_trip_serializes_dashboard_editors_and_save(
    hass, profile, hass_client
):
    # Reproduce the real site's temperature-only saved configuration.
    profile["modes"] = []
    profile["meters"] = []
    profile["services"] = []
    entry, existing = await start(hass, profile)
    hass.config_entries.options.async_abort(existing["flow_id"])
    client = await hass_client()
    base = "/api/config/config_entries/options/flow"
    response = await client.post(base, json={"handler": entry.entry_id})
    assert response.status == 200, await response.text()
    initial = await response.json()
    endpoint = base + "/" + initial["flow_id"]
    fixture = {}

    async def post(data):
        response = await client.post(endpoint, json=data)
        assert response.status == 200, await response.text()
        return await response.json()

    result = await post({"next_step_id": "dashboard"})
    fixture["initial"] = result
    assert len(view(result)["categories"][0]["entries"]) == 1
    wrapper = {field["name"]: field for field in result["data_schema"]}
    assert "object" in wrapper["data"]["selector"]
    response = await client.get(endpoint)
    assert response.status == 200
    assert view(await response.json())["form"] is None

    result = await post({"action": "open", "step": "temperature", "category": "thermal"})
    fixture["temperature"] = result
    result = await post({"action": "submit", "data": []})
    assert "must be an object" in view(result)["error"]
    assert not entry.options
    result = await post(
        {
            "action": "submit",
            "data": {
                "entity_id": "sensor.test_temperature",
                "label": "Added state",
                "unit": "°C",
                "lower": 20,
                "upper": 80,
            },
        }
    )
    fixture["added"] = result
    assert view(result)["dirty"]
    result = await post({"action": "save"})
    assert result["type"] == "create_entry"
    assert "data" not in result
    await hass.async_block_till_done()
    assert len(entry.runtime_data.profile["bindings"]) == 2
    assert entry.options["bindings"][0]["channel_id"] == "temperature-1"

    response = await client.post(base, json={"handler": entry.entry_id})
    assert response.status == 200
    reopened = await response.json()
    endpoint = base + "/" + reopened["flow_id"]
    fixture["saved"] = await post({"next_step_id": "dashboard"})
    assert not view(fixture["saved"])["dirty"]
    response = await client.get("/gridworks_connector_assets/errors.mjs")
    assert response.status == 200
    assert response.content_type in {"text/javascript", "application/javascript"}
    assert "describeApiError" in await response.text()
    if output := os.environ.get("CONNECTOR_UI_FIXTURE"):
        Path(output).write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_commissioning_http_requires_admin(hass, profile, hass_client, hass_read_only_user):
    entry, existing = await start(hass, profile)
    hass.config_entries.options.async_abort(existing["flow_id"])
    refresh = await hass.auth.async_create_refresh_token(
        hass_read_only_user, client_id="https://test.example/"
    )
    token = hass.auth.async_create_access_token(refresh)
    client = await hass_client(token)
    response = await client.get("/api/")
    assert response.status == 200
    response = await client.post(
        "/api/config/config_entries/options/flow", json={"handler": entry.entry_id}
    )
    assert response.status == 403
    assert not entry.options
    await hass.config_entries.async_unload(entry.entry_id)
