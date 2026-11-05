"""Isolated test fixtures only; never install synthetic entities at the pilot site."""

from uuid import uuid4

import pytest

from custom_components.gridworks_connector.engine import ShadowEngine
from custom_components.gridworks_connector.journal import Journal
from custom_components.gridworks_connector.protocol import (
    Bounds,
    Channel,
    Meter,
    Mode,
    Resource,
    Service,
)


@pytest.fixture
def resource():
    return Resource(
        name="Test resource",
        channels=[
            Channel(
                channel_id="temperature-1",
                kind="temperature",
                unit="°C",
                limits=Bounds(lower=10, upper=90),
            )
        ],
        modes=[
            Mode(mode_id="A", label="A", declared_available=False),
            Mode(mode_id="B", label="B", declared_available=True),
        ],
        meters=[Meter(meter_id="plant", label="Plant", coverage="whole test plant")],
        services=[Service(service_id="heating", label="Heating", kind="heating")],
    )


@pytest.fixture
def endpoint(tmp_path, resource):
    now = [1000000]
    journal = Journal(str(tmp_path / "journal.sqlite"))
    engine = ShadowEngine(str(uuid4()), 1, resource, journal, lambda: now[0])
    yield engine, now, journal
    journal.close()


@pytest.fixture
def hass_config_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def profile():
    return {
        "name": "Test resource",
        "resource_id": str(uuid4()),
        "revision": 1,
        "bindings": [
            {
                "channel_id": "temperature-1",
                "kind": "temperature",
                "unit": "°C",
                "limits": {"lower": 10, "upper": 90},
                "entity_id": "sensor.test_temperature",
                "label": "Test temperature",
                "attribute": None,
                "registry_id": None,
                "stale_seconds": 300,
                "timestamp_basis": "ha_report_time",
            }
        ],
        "modes": [{"mode_id": "A", "label": "A", "declared_available": True}],
        "meters": [{"meter_id": "plant", "label": "Plant", "coverage": "test plant"}],
        "services": [{"service_id": "heating", "label": "Heating", "kind": "heating"}],
        "location": {},
        "transport": {"mode": "local_demo"},
    }
