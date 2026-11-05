"""Category membership, privacy and referential integrity in local UI drafts."""

import copy
import json

import pytest

from custom_components.gridworks_connector.commissioning import overview, remove_definition


def test_grouped_overview_lists_existing_sources_and_limits_without_broker_secrets(profile):
    profile["transport"].update(
        host="private-broker", username="private-user", key_path="private-key"
    )
    before = copy.deepcopy(profile)
    categories = {item["id"]: item for item in overview(profile)}
    assert categories["thermal"]["entries"][0]["source"] == "sensor.test_temperature"
    assert "10 to 90" in categories["thermal"]["entries"][0]["detail"]
    assert categories["electric"]["entries"][0]["label"] == "Plant"
    assert len(categories) == 6
    assert all(item["explanation"] and item["actions"] for item in categories.values())
    assert "private-broker" not in json.dumps(categories)
    assert "private-key" not in json.dumps(categories)
    assert before == profile


def test_referenced_meter_cannot_be_removed_from_draft(profile):
    profile["bindings"].append({"channel_id": "power", "kind": "power", "meter_id": "plant"})
    with pytest.raises(ValueError, match="observations"):
        remove_definition(profile, "meters/plant")
    remove_definition(profile, "bindings/power")
    remove_definition(profile, "meters/plant")
    assert not profile["meters"]


def test_parent_meter_cannot_be_removed_before_child(profile):
    profile["meters"].append({"meter_id": "child", "parent_meter_id": "plant"})
    with pytest.raises(ValueError, match="child meters"):
        remove_definition(profile, "meters/plant")
