"""Inspect relationship, commissioning and hypothetical decisions."""

from homeassistant.components.sensor import SensorEntity

from .entity import ConnectorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        Status(entry.runtime_data, key, name)
        for key, name in (
            ("relationship", "Shadow relationship"),
            ("decision", "Hypothetical decision"),
            ("channels", "Commissioned channels"),
            ("notices", "Pending reassessments"),
            ("error", "Last protocol error"),
            ("peer", "Peer implementation"),
        )
    )


class Status(ConnectorEntity, SensorEntity):
    @property
    def native_value(self):
        r, e = self.runtime, self.runtime.engine
        key = self._attr_unique_id.rsplit("_", 1)[-1]
        if key == "relationship":
            return "fresh_shadow" if e.peer_fresh else "waiting_or_stale"
        if key == "decision":
            return e.last_decision.disposition if e.last_decision else "none"
        if key == "channels":
            return len(r.profile["bindings"])
        if key == "notices":
            return sum(n["status"] not in ("acknowledged", "resolved") for n in e.notices.values())
        if key == "error":
            return r.last_error or e.last_error or "none"
        return "embedded_test_peer" if r.peer else "external_test_broker"

    @property
    def extra_state_attributes(self):
        e = self.runtime.engine
        return {
            "shadow_only": True,
            "protocol_status": "unpublished_draft",
            "config_revision": e.revision,
            "current_request": e.current_request.request_id if e.current_request else None,
            "hypothetical_mode": e.last_decision.selected_mode if e.last_decision else None,
            "physical_actions_supported": False,
        }
