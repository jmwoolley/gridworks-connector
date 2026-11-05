"""Shared constants. No live actuation capability exists in this integration."""

DOMAIN = "gridworks_connector"
VERSION = "0.1.0-beta.1"
PROTOCOL_REVISION = "draft-2026-11-05"
PREFIX = "gw.thermal."
HEARTBEAT_SECONDS = 60
PEER_STALE_SECONDS = 180
OBSERVATION_SECONDS = 60
MAX_TRACE = 2000
MAX_OUTBOX = 1000
PLATFORMS = ["sensor", "binary_sensor", "button", "select"]
KINDS = [
    "temperature",
    "power",
    "energy",
    "current_mode",
    "mode_availability",
    "mode_not_before",
    "mode_expected_return",
    "mode_min_power",
    "mode_max_power",
    "service_request",
    "service_activity",
    "service_delivery",
    "service_adequacy",
    "operating_restriction",
    "outdoor_temperature",
    "rain",
    "irradiance",
    "occupancy",
    "occupant_count",
    "solar_azimuth",
    "solar_zenith",
    "context",
]
PARTICIPATION = ["pursuing", "modified", "paused", "unknown"]
