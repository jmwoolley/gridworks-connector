"""Generate deterministic wire examples and a proposed seed for GridWorks review."""

import json
from pathlib import Path
from uuid import UUID

from custom_components.gridworks_connector.const import PREFIX
from custom_components.gridworks_connector.protocol import Message, PAYLOADS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "proposed-sema"
NOW = 1793908800000  # Fixed illustrative UTC time, not a field measurement.


def identity(index):
    return str(UUID(int=index, version=4))


resource = {
    "name": "Illustrative resource",
    "channels": [
        {
            "channel_id": "state-1",
            "kind": "temperature",
            "unit": "°C",
            "limits": {"lower": 10, "upper": 90},
        },
        {"channel_id": "outdoor-air", "kind": "outdoor_temperature", "unit": "°C"},
    ],
    "modes": [
        {"mode_id": "A", "label": "A", "declared_available": True},
        {"mode_id": "B", "label": "B", "declared_available": True},
    ],
    "meters": [{"meter_id": "plant", "label": "Plant", "coverage": "All generators"}],
    "services": [{"service_id": "heat", "label": "Heating", "kind": "heating"}],
    "capabilities": ["shadow_only", "illustrative_example"],
}
observation = {
    "observation_set_id": "example-set",
    "readings": [
        {
            "channel_id": "state-1",
            "value": 45.0,
            "observed_ms": NOW - 1000,
            "received_ms": NOW,
            "quality": "reported",
            "timestamp_basis": "ha_report_time",
        },
    ],
}
examples = {
    "resource.config": resource,
    "observations": observation,
    "context": {
        "observation_set_id": "example-context",
        "readings": [
            {
                "channel_id": "outdoor-air",
                "value": None,
                "observed_ms": None,
                "received_ms": NOW,
                "quality": "unknown",
                "timestamp_basis": "ha_report_time",
            }
        ],
    },
    "context.calculated": {
        "observed_ms": NOW,
        "source": "illustrative-calculated-context",
        "solar_azimuth_deg": 120.0,
        "solar_zenith_deg": 50.0,
    },
    "mode.event": {
        "mode_id": "A",
        "occurred_ms": NOW - 10000,
        "active_since_ms": NOW - 10000,
        "evidence": "observed",
    },
    "availability": {
        "mode_id": "B",
        "available": False,
        "not_before_ms": NOW + 60000,
        "expected_return_ms": NOW + 120000,
        "min_power_w": 3000,
        "max_power_w": 6000,
    },
    "service.status": {
        "service_id": "heat",
        "requested": True,
        "active": None,
        "delivered": None,
        "adequate": None,
        "observed_ms": NOW,
    },
    "participation": {"status": "modified", "request_id": "example-request"},
    "shadow.request": {
        "request_id": "example-request",
        "request_sequence": 1,
        "valid_from_ms": NOW,
        "valid_until_ms": NOW + 300000,
        "average_power_w": 6000,
        "electrical_boundary": "plant",
        "preferred_mode": "A",
        "intent": "communications_test_only",
    },
    "shadow.decision": {
        "request_id": "example-request",
        "disposition": "would_pursue_with_changes",
        "preferred_mode": "A",
        "selected_mode": "B",
        "deliberate_substitution": True,
        "target_status": "pursuing",
        "reason": "Illustrative local service priority",
    },
    "peer.status": {
        "current_request_id": "example-request",
        "participation": "modified",
        "last_peer_message_id": identity(1),
        "last_request_sequence": 1,
        "ready": True,
        "engine_healthy": True,
    },
    "receipt": {"message_id": identity(1), "status": "ingested"},
    "weather.proposal": {
        "proposal_id": "example-catalog",
        "sources": [
            {
                "source_id": "primary",
                "label": "Example primary",
                "coverage": "Illustration only",
                "variables": ["temperature"],
                "provenance": "test_catalog",
            },
            {
                "source_id": "backup",
                "label": "Example backup",
                "coverage": "Illustration only",
                "variables": ["temperature"],
                "provenance": "test_catalog",
            },
        ],
    },
    "weather.selection": {
        "proposal_id": "example-catalog",
        "primary_source": "primary",
        "backup_sources": ["backup"],
        "confirmed": True,
    },
    "weather.status": {
        "source_id": "backup",
        "test_scenario": True,
        "reason": "Illustrative fallback, not an observed provider outage",
    },
    "configuration.change": {
        "revision": 1,
        "effective_ms": NOW,
        "affected_ids": ["state-1"],
        "details": "User reports a system change; details unknown",
    },
    "reassessment": {
        "notice_id": "example-notice",
        "status": "suspected",
        "evidence": "TEST: notification delivery only",
        "test_scenario": True,
    },
    "gap": {"dropped_count": 2, "reason": "bounded_outbox_overflow"},
    "error": {"code": "unsupported_version", "detail": "Review the proposed protocol revision"},
}
assert set(examples) == set(PAYLOADS)
cloud = {
    "context.calculated",
    "shadow.request",
    "peer.status",
    "weather.proposal",
    "weather.status",
    "reassessment",
}
OUT.mkdir(parents=True, exist_ok=True)
for index, (kind, payload) in enumerate(examples.items(), 1):
    word = Message(
        type_name=PREFIX + kind,
        message_id=identity(index),
        resource_id=identity(100),
        session_id=identity(200),
        sender="cloud" if kind in cloud else "ha",
        receiver="ha" if kind in cloud else "cloud",
        created_ms=NOW,
        sequence=index,
        config_revision=1,
        payload=payload,
    )
    (OUT / f"{PREFIX}{kind}.000.example.json").write_text(
        json.dumps(word.model_dump(by_alias=True), indent=2) + "\n", encoding="utf-8"
    )
seed = [
    "# PROPOSED ONLY: register/review definitions before running the official generator.",
    "# Same seed-request shape as gridworks-flo; names are not currently published.",
    "initial_targets:",
    "  types:",
]
for kind in PAYLOADS:
    seed.extend([f"    {PREFIX}{kind}:", '      versions: ["000"]'])
seed.extend(["local_names:", "  strip_prefixes: [gw]", ""])
(OUT / "proposed_seed_request.yaml").write_text("\n".join(seed), encoding="utf-8")
print(f"Generated {len(examples)} validated illustrative wire examples and proposed seed")
