"""Native HA commissioning UI; no preselected site entities or plant actions."""

from __future__ import annotations

import copy
from uuid import uuid4

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector as sel

from .const import DOMAIN, KINDS
from .protocol import Bounds, Channel, Meter, Mode, Resource, Service


def choose(options):
    return sel.SelectSelector(sel.SelectSelectorConfig(options=options, mode="dropdown"))


def text():
    return sel.TextSelector()


def number():
    return sel.NumberSelector(sel.NumberSelectorConfig(mode="box", step="any"))


def entity():
    return sel.EntitySelector(sel.EntitySelectorConfig())


class Editor:
    """Repeated menu steps make the channel list extensible, with per-channel limits."""

    profile = None

    def initialize(self, source=None):
        self.profile = copy.deepcopy(
            (dict(source) if source is not None else None)
            or {
                "name": "",
                "resource_id": str(uuid4()),
                "revision": 1,
                "bindings": [],
                "modes": [],
                "meters": [],
                "services": [],
                "location": {},
                "transport": {"mode": "local_demo"},
            }
        )

    def wire_resource(self):
        return Resource(
            name=self.profile["name"],
            channels=[
                Channel.model_validate(
                    {
                        k: v
                        for k, v in b.items()
                        if k
                        not in ("entity_id", "attribute", "registry_id", "label", "stale_seconds")
                    }
                )
                for b in self.profile["bindings"]
            ],
            modes=[
                {k: v for k, v in m.items() if k != "state_value"} for m in self.profile["modes"]
            ],
            meters=self.profile["meters"],
            services=self.profile["services"],
            location=self.profile["location"],
            capabilities=["shadow_only", "draft_protocol", "full_communication_v1"],
        )

    async def async_step_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "temperature",
                "signal",
                "mode",
                "meter",
                "service",
                "site",
                "transport",
                "weather",
                "remove",
                "review",
                "finish",
            ],
            description_placeholders={
                "counts": (
                    f"{len(self.profile['bindings'])} channels; "
                    f"{len(self.profile['modes'])} modes; "
                    f"{len(self.profile['meters'])} meters; "
                    f"{len(self.profile['services'])} services"
                )
            },
        )

    async def async_step_temperature(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                bounds = Bounds(lower=user_input["lower"], upper=user_input["upper"])
                self.add_binding(
                    {**user_input, "kind": "temperature", "limits": bounds.model_dump()}
                )
                return await self.async_step_menu()
            except ValueError, TypeError:
                errors["base"] = "invalid_mapping"
        return self.async_show_form(
            step_id="temperature",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("entity_id"): entity(),
                    vol.Optional("attribute", default=""): text(),
                    vol.Required("label"): text(),
                    vol.Required("unit"): choose(["°C", "°F", "K"]),
                    vol.Required("lower"): number(),
                    vol.Required("upper"): number(),
                    vol.Optional("stale_seconds", default=300): sel.NumberSelector(
                        sel.NumberSelectorConfig(min=1, max=86400, mode="box")
                    ),
                }
            ),
        )

    def add_binding(self, data):
        state = self.hass.states.get(data["entity_id"])
        if state is None:
            raise ValueError("entity does not exist")
        channel = {
            "channel_id": str(uuid4()),
            "kind": data["kind"],
            "unit": data.get("unit") or None,
            "limits": data.get("limits"),
            "entity_id": data["entity_id"],
            "attribute": data.get("attribute") or None,
            "label": data.get("label", ""),
            "stale_seconds": int(data.get("stale_seconds", 300)),
            "timestamp_basis": "ha_report_time",
            **{key: data[key] for key in ("mode_id", "meter_id", "service_id") if data.get(key)},
        }
        item = er.async_get(self.hass).async_get(data["entity_id"])
        channel["registry_id"] = item.id if item else None
        public = {
            k: v
            for k, v in channel.items()
            if k not in ("entity_id", "attribute", "registry_id", "label", "stale_seconds")
        }
        Channel.model_validate(public)
        self.profile["bindings"].append(channel)

    async def async_step_signal(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self.add_binding(user_input)
                return await self.async_step_menu()
            except ValueError, TypeError:
                errors["base"] = "invalid_mapping"
        schema = {
            vol.Required("entity_id"): entity(),
            vol.Required("label"): text(),
            vol.Required("kind"): choose([k for k in KINDS if k != "temperature"]),
            vol.Optional("attribute", default=""): text(),
            vol.Optional("unit", default=""): text(),
            vol.Optional("stale_seconds", default=300): sel.NumberSelector(
                sel.NumberSelectorConfig(min=1, max=86400, mode="box")
            ),
        }
        for field, group in (
            ("mode_id", "modes"),
            ("meter_id", "meters"),
            ("service_id", "services"),
        ):
            if self.profile[group]:
                schema[vol.Optional(field)] = choose([item[field] for item in self.profile[group]])
        return self.async_show_form(step_id="signal", errors=errors, data_schema=vol.Schema(schema))

    async def async_step_mode(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            state_value = data.pop("state_value", "")
            data["declared_available"] = {"unknown": None, "yes": True, "no": False}[
                data.pop("availability")
            ]
            try:
                item = Mode.model_validate(data)
                if item.mode_id in [m["mode_id"] for m in self.profile["modes"]]:
                    raise ValueError("duplicate mode")
                self.profile["modes"].append({**item.model_dump(), "state_value": state_value})
                return await self.async_step_menu()
            except ValueError:
                errors["base"] = "invalid_mapping"
        return self.async_show_form(
            step_id="mode",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("mode_id"): text(),
                    vol.Required("label"): text(),
                    vol.Optional("state_value", default=""): text(),
                    vol.Required("availability", default="unknown"): choose(
                        ["unknown", "yes", "no"]
                    ),
                }
            ),
        )

    async def async_step_meter(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                item = Meter.model_validate(user_input)
                if item.meter_id in [m["meter_id"] for m in self.profile["meters"]]:
                    raise ValueError("duplicate meter")
                if item.parent_meter_id and item.parent_meter_id not in [
                    m["meter_id"] for m in self.profile["meters"]
                ]:
                    raise ValueError("unknown parent")
                self.profile["meters"].append(item.model_dump())
                return await self.async_step_menu()
            except ValueError:
                errors["base"] = "invalid_mapping"
        schema = {
            vol.Required("meter_id"): text(),
            vol.Required("label"): text(),
            vol.Required("coverage"): text(),
            vol.Optional("provenance"): text(),
        }
        if self.profile["meters"]:
            schema[vol.Optional("parent_meter_id")] = choose(
                [m["meter_id"] for m in self.profile["meters"]]
            )
        return self.async_show_form(step_id="meter", errors=errors, data_schema=vol.Schema(schema))

    async def async_step_service(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                item = Service.model_validate(user_input)
                if item.service_id in [s["service_id"] for s in self.profile["services"]]:
                    raise ValueError("duplicate service")
                self.profile["services"].append(item.model_dump())
                return await self.async_step_menu()
            except ValueError:
                errors["base"] = "invalid_mapping"
        return self.async_show_form(
            step_id="service",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("service_id"): text(),
                    vol.Required("label"): text(),
                    vol.Required("kind"): choose(["heating", "cooling", "dhw", "other"]),
                    vol.Optional("delivery_feedback", default=False): sel.BooleanSelector(),
                }
            ),
        )

    async def async_step_site(self, user_input=None):
        errors = {}
        if user_input is not None:
            lat, lon = user_input.get("latitude"), user_input.get("longitude")
            if (lat is not None and not -90 <= lat <= 90) or (
                lon is not None and not -180 <= lon <= 180
            ):
                errors["base"] = "invalid_mapping"
            else:
                self.profile["location"] = user_input
                return await self.async_step_menu()
        return self.async_show_form(
            step_id="site",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional("address"): text(),
                    vol.Optional("latitude"): number(),
                    vol.Optional("longitude"): number(),
                }
            ),
        )

    async def async_step_transport(self, user_input=None):
        if user_input is not None:
            self.profile["transport"] = {"mode": user_input["mode"]}
            if user_input["mode"] == "mqtt":
                return await self.async_step_broker()
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="transport",
            data_schema=vol.Schema(
                {
                    vol.Required("mode", default="local_demo"): choose(["local_demo", "mqtt"]),
                }
            ),
        )

    async def async_step_broker(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            local = data["host"] in ("localhost", "127.0.0.1", "::1")
            if (
                not data.pop("test_endpoint_confirmed", False)
                or (not local and not data["tls"])
                or data["send_topic"] == data["receive_topic"]
                or any(c in data["send_topic"] + data["receive_topic"] for c in "#+")
            ):
                errors["base"] = "invalid_mapping"
            else:
                self.profile["transport"] = {"mode": "mqtt", **data}
                return await self.async_step_menu()
        return self.async_show_form(
            step_id="broker",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("host"): text(),
                    vol.Required("port", default=8883): sel.NumberSelector(
                        sel.NumberSelectorConfig(min=1, max=65535, mode="box")
                    ),
                    vol.Required("tls", default=True): sel.BooleanSelector(),
                    vol.Required("send_topic"): text(),
                    vol.Required("receive_topic"): text(),
                    vol.Optional("username"): text(),
                    vol.Optional("ca_path"): text(),
                    vol.Optional("cert_path"): text(),
                    vol.Optional("key_path"): text(),
                    vol.Required("test_endpoint_confirmed", default=False): sel.BooleanSelector(),
                }
            ),
        )

    async def async_step_weather(self, user_input=None):
        entry = getattr(self, "config_entry", None)
        runtime = getattr(entry, "runtime_data", None) if entry else None
        proposal = runtime.engine.weather_proposal if runtime else None
        if proposal is None:
            return self.async_show_form(
                step_id="weather", data_schema=vol.Schema({}), errors={"base": "weather_not_ready"}
            )
        errors = {}
        if user_input is not None:
            primary = user_input["primary_source"]
            backups = user_input.get("backup_sources", [])
            if primary in backups or not user_input.get("confirmed"):
                errors["base"] = "invalid_mapping"
            else:
                await runtime.confirm_weather(primary, backups)
                return await self.async_step_menu()
        options = [
            {"value": s.source_id, "label": s.label + " — " + s.coverage} for s in proposal.sources
        ]
        return self.async_show_form(
            step_id="weather",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("primary_source"): sel.SelectSelector(
                        sel.SelectSelectorConfig(options=options, mode="dropdown")
                    ),
                    vol.Optional("backup_sources", default=[]): sel.SelectSelector(
                        sel.SelectSelectorConfig(options=options, mode="list", multiple=True)
                    ),
                    vol.Required("confirmed", default=False): sel.BooleanSelector(),
                }
            ),
        )

    async def async_step_remove(self, user_input=None):
        if user_input is not None:
            channel_id = user_input["channel_id"]
            self.profile["bindings"] = [
                b for b in self.profile["bindings"] if b["channel_id"] != channel_id
            ]
            return await self.async_step_menu()
        if not self.profile["bindings"]:
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required("channel_id"): sel.SelectSelector(
                        sel.SelectSelectorConfig(
                            options=[
                                {"value": b["channel_id"], "label": b["label"]}
                                for b in self.profile["bindings"]
                            ],
                            mode="dropdown",
                        )
                    ),
                }
            ),
        )

    async def async_step_review(self, user_input=None):
        if user_input is not None:
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="review",
            data_schema=vol.Schema({}),
            description_placeholders={
                "summary": str(
                    {
                        "channels": [
                            (b["label"], b["kind"], b.get("limits"))
                            for b in self.profile["bindings"]
                        ],
                        "modes": self.profile["modes"],
                        "meters": self.profile["meters"],
                        "services": self.profile["services"],
                        "transport": self.profile["transport"]["mode"],
                    }
                )
            },
        )

    async def async_step_finish(self, user_input=None):
        if user_input is not None:
            return await self.async_step_menu()
        try:
            self.wire_resource()
            if self.profile["transport"].get("mode") == "mqtt" and not self.profile[
                "transport"
            ].get("host"):
                raise ValueError("incomplete broker")
        except ValueError:
            return self.async_show_form(
                step_id="finish", errors={"base": "incomplete"}, data_schema=vol.Schema({})
            )
        return self.complete()


class GridworksConnectorConfigFlow(Editor, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self.profile is None:
            self.initialize()
        if user_input is not None:
            self.profile["name"] = user_input["name"]
            await self.async_set_unique_id(self.profile["resource_id"])
            self._abort_if_unique_id_configured()
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): text(),
                }
            ),
        )

    def complete(self):
        return self.async_create_entry(title=self.profile["name"], data=self.profile)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ConnectorOptionsFlow()


class ConnectorOptionsFlow(Editor, config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        self.initialize(self.config_entry.options or self.config_entry.data)
        return await self.async_step_menu()

    def complete(self):
        self.profile["revision"] += 1
        return self.async_create_entry(data=self.profile)
