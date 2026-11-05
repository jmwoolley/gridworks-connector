"""Local commissioning summaries. No credentials or unselected entities are exported."""

CATEGORIES = (
    (
        "thermal",
        "Thermal State Channels",
        "Choose temperatures that together describe the thermal store. Every channel needs lower and upper limits in its selected unit. Tanks, PCM stores, slabs and indoor spaces can all contribute.",
        [("temperature", "Add thermal-state channel")],
    ),
    (
        "electric",
        "Electric Meters",
        "Describe what each meter covers, then attach its power and energy entities. Use a plant meter, generator meters, or both with explicit parent relationships so overlapping measurements are not counted twice.",
        [("meter", "Add meter"), ("signal", "Add power or energy measurement")],
    ),
    (
        "modes",
        "Operating Modes",
        "Name the discrete operating configurations your local controller recognizes. Map actual mode and availability signals where available; unknown is valid. These definitions do not operate equipment.",
        [("mode", "Add mode"), ("signal", "Add mode or restriction signal")],
    ),
    (
        "services",
        "Thermal Services",
        "Identify heating, cooling, hot water or other end uses. A service request and confirmed delivery are separate observations. Open-loop systems do not need extra instrumentation.",
        [("service", "Add service"), ("signal", "Add service observation")],
    ),
    (
        "context",
        "Site and Local Context",
        "Add location and optional weather, occupancy or other explanatory observations that may help interpret thermal behavior. Only the entities you select are included.",
        [("site", "Edit site location"), ("signal", "Add context entity")],
    ),
    (
        "cloud",
        "Cloud Connection and Weather",
        "Select the embedded demonstration or an approved external shadow peer. Review proposed weather sources after the peer has supplied its catalog; the embedded catalog is a labeled test.",
        [("transport", "Choose shadow peer"), ("weather", "Review weather sources")],
    ),
)


def binding_category(kind):
    if kind == "temperature":
        return "thermal"
    if kind in ("power", "energy"):
        return "electric"
    if kind == "current_mode" or kind.startswith("mode_") or kind == "operating_restriction":
        return "modes"
    if kind.startswith("service_"):
        return "services"
    return "context"


def overview(profile):
    categories = [
        dict(
            id=key,
            title=title,
            explanation=help_text,
            actions=[dict(step=step, label=label) for step, label in actions],
            entries=[],
        )
        for key, title, help_text, actions in CATEGORIES
    ]
    by_id = {item["id"]: item for item in categories}
    for binding in profile["bindings"]:
        details = [binding["kind"].replace("_", " ")]
        if bounds := binding.get("limits"):
            details.append(
                f"Limits: {bounds['lower']:g} to {bounds['upper']:g} {binding.get('unit') or ''}"
            )
        for key in ("meter_id", "mode_id", "service_id"):
            if binding.get(key):
                details.append(f"{key.replace('_id', '').title()}: {binding[key]}")
        by_id[binding_category(binding["kind"])]["entries"].append(
            dict(
                target="bindings/" + binding["channel_id"],
                label=binding.get("label") or binding["entity_id"],
                source=binding["entity_id"]
                + (f" / {binding['attribute']}" if binding.get("attribute") else ""),
                detail="; ".join(details),
            )
        )
    for group, field, category in (
        ("meters", "meter_id", "electric"),
        ("modes", "mode_id", "modes"),
        ("services", "service_id", "services"),
    ):
        for item in profile[group]:
            detail = (
                item.get("coverage")
                or item.get("kind")
                or (
                    "Availability: "
                    + {True: "available", False: "unavailable", None: "unknown"}[
                        item.get("declared_available")
                    ]
                )
            )
            if item.get("parent_meter_id"):
                detail += "; Parent: " + item["parent_meter_id"]
            by_id[category]["entries"].insert(
                0,
                dict(
                    target=group + "/" + item[field],
                    label=item["label"],
                    source=item[field],
                    detail=detail,
                ),
            )
    location = profile.get("location", {})
    by_id["context"]["summary"] = (
        "; ".join(f"{k.title()}: {v}" for k, v in location.items())
        or "No site location configured."
    )
    by_id["cloud"]["summary"] = (
        "Embedded demonstration"
        if profile["transport"]["mode"] == "local_demo"
        else "Approved external MQTT shadow peer"
    )
    return categories


def remove_definition(profile, target):
    group, identity = target.split("/", 1)
    fields = {
        "bindings": "channel_id",
        "meters": "meter_id",
        "modes": "mode_id",
        "services": "service_id",
    }
    if group not in fields or not any(item[fields[group]] == identity for item in profile[group]):
        raise ValueError("Definition no longer exists.")
    if group != "bindings":
        if any(item.get(fields[group]) == identity for item in profile["bindings"]):
            raise ValueError(
                "Remove or reassign the observations referring to this definition first."
            )
        if group == "meters" and any(
            item.get("parent_meter_id") == identity for item in profile["meters"]
        ):
            raise ValueError("Remove or reassign child meters first.")
    profile[group] = [item for item in profile[group] if item[fields[group]] != identity]
