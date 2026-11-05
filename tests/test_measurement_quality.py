"""A changed unit and unknown occupancy must not silently become valid numeric evidence."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from custom_components.gridworks_connector.protocol import Meter, Resource
from custom_components.gridworks_connector.runtime import read_value


def state(value, unit=None):
    return SimpleNamespace(
        state=value,
        attributes={"unit_of_measurement": unit} if unit else {},
        last_reported=datetime.fromtimestamp(1000, tz=UTC),
        last_updated=datetime.fromtimestamp(1000, tz=UTC),
    )


def test_electrical_unit_change_invalidates_measurement():
    binding = {"kind": "power", "unit": "kW", "stale_seconds": 300}
    value, stamp, quality = read_value(state("2", "W"), binding, 1001000)
    assert value is None and stamp == 1000000 and quality == "invalid"


def test_unknown_occupancy_is_not_zero():
    binding = {"kind": "occupant_count", "stale_seconds": 300}
    assert read_value(state("unknown"), binding, 1001000)[0] is None
    assert read_value(state("0"), binding, 1001000)[0] == 0
    assert read_value(state("off"), binding, 1001000)[2] == "invalid"


def test_meter_cycles_rejected(resource):
    data = resource.model_dump()
    data["meters"] = [
        Meter(
            meter_id="plant", label="Plant", coverage="all", parent_meter_id="child"
        ).model_dump(),
        Meter(
            meter_id="child", label="Child", coverage="subset", parent_meter_id="plant"
        ).model_dump(),
    ]
    with pytest.raises(ValidationError):
        Resource.model_validate(data)
