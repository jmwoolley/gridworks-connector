# Install and review the first shadow draft

This guide is for an HA administrator. The draft reads commissioned entities and exchanges
shadow messages; it cannot command physical equipment.

## Before installing

Use HA Core2026.11.0 or later. The pilot version check found2026.7.2, so that instance
needs a separately scheduled upgrade before this draft is installed. Check its existing
integrations and backup/recovery arrangements when scheduling the update. This development
work has not updated or installed anything on the live instance.

## Manual installation

1. Download `gridworks-connector-0.1.0-beta.1.zip` from the successful branch build artifact,
   or obtain the same ZIP from the developer. BUILD_INFO.json identifies its exact commit.
2. Extract only `custom_components/gridworks_connector` into the HA configuration directory.
   The usual resulting folder is `/config/custom_components/gridworks_connector`.
   Do not overwrite the whole custom_components directory or put code in an app/add-on.
3. Restart HA at an appropriate time for the existing installation.
4. Open **Settings → Devices & services → Add integration → GridWorks Connector**.
5. Give the resource a name. Keep **Embedded demonstration** as the transport for the
   first interface review; no cloud credentials are needed for that mode.

This is a development ZIP, not an official Marketplace release. The older GridWorks API
has its own domain and is not automatically changed or migrated.

## Commissioning walkthrough

- **Add a thermal-state channel:** select an existing entity, label, unit and lower/upper
  bounds. Repeat for every meaningful temperature. For an entity whose state is not a
  temperature, specify an existing temperature attribute. Bounds must use the selected unit.
- **Define an electrical boundary:** describe what each existing plant/generator meter
  covers, then bind its power/energy entities through **Add a signal**. Parent/submeter
  overlap is explicit; do not invent an instrument that is not present.
- **Define modes:** use opaque IDs and labels, with optional local state-value mapping.
  Declare availability only where meaningful; otherwise leave unknown or map an existing
  availability signal. No actual equipment mode is changed by commissioning.
- **Define services:** heating, cooling, DHW or other; map calls/activity and any real
  delivery/adequacy feedback separately. Missing feedback remains unknown.
- **Site context:** optionally add location and select real meteorological/occupancy
  entities. A count of zero is different from unknown.
- **Review** the definitions, then **Finish**. Missing temperature limits block completion.

A temperature-only setup can show observation exchange. To evaluate a power/mode proposal,
the resource needs a meaningful declared meter boundary and a mode with known availability.
That hypothetical decision is not evidence that the physical plant can achieve the power.

## Review the working interface

Open the integration's device page:
- **Shadow only** stays on. **Peer implementation** identifies the embedded test peer.
- **Send observations** sends current selected data without refreshing cached timestamps.
- **Exercise shadow protocol** sends labeled reassessment/weather-fallback test messages
  and advances the local loop; it does not alter sensor values or equipment.
- The hypothetical decision reports whether direction would be pursued or modified.
- **Shadow participation** can pause hypothetical pursuit while observations continue.
- **System changed** and **Acknowledge reassessment notices** exercise those message paths.

Use **Configure → Edit a commissioned definition** to refine channels, modes, meters or
services. Labels/limits can retain a channel ID; selecting a replacement source produces a
new identity and configuration revision.

Use **Configure → Review proposed weather sources** to select a primary and multiple
backups and explicitly confirm them. The embedded catalog is a test catalog, not live
weather-provider discovery. Solar geometry can be calculated from commissioned coordinates;
it is separate from measured irradiance.

## What to show Jessica

Show entity selection/limits, meter/mode/service definitions, shadow participation/status,
the hypothetical request response, weather confirmation and reassessment acknowledgement.
Share the review ZIP or repository docs: PROTOCOL.md, GRIDWORKS_HANDOFF.md,
COMMUNICATION_COVERAGE.md, proposed schemas, wire examples and seed request.

Next agree approved Sema words/versions and routes, obtain a separate cloud test identity
and credentials, and run the complete coverage matrix against the real GridWorks peer.
Only then is actual GridWorks interoperability demonstrated. Credentials should be provisioned
through the approved secure process, not pasted into chat or the repository.

## Recovery and records

Configuration/mappings and bounded SQLite journals live under HA's normal config storage,
outside the installed code folder. Protect backups and test matching-version recovery.
Remove/unload the integration through HA if needed; the draft has no physical-control
handover to unwind. Existing HVAC controls continue independently.
