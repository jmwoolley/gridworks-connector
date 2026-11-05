# GridWorks Connector — shadow-only development draft

An independent Home Assistant custom integration, domain `gridworks_connector`.
Created on a personal development fork of GridWorks' earlier HA repository.
**Not an official GridWorks release or published Sema implementation.**

The integration has **no equipment-control action interface**. It reads only user-selected
entities, publishes observations and evaluates hypothetical guidance. An embedded test
peer exercises the bidirectional relationship; an integration-owned MQTT client can
connect to an approved external **test** peer using this draft protocol. Alice is unchanged.

## Install the draft

Target: **Home Assistant Core 2026.11.0 or later**; tested baseline is2026.11.0.
the pilot site was inspected running2026.7.2; do not install this package there before
a separately scheduled HA upgrade/compatibility and recovery review. Nothing here
updates HA or changes HVAC settings.

1. Obtain the component-only ZIP from the developer's build artifacts, or use the
   component folder on the development branch. There is no official Marketplace listing.
2. Back up the HA configuration before installing custom code.
3. Extract **only** `custom_components/gridworks_connector` into HA's config directory.
   Do not replace the whole `custom_components` folder. Keep keys/databases outside code.
4. Restart HA if required by the install method. Go to **Settings → Devices & services →
   Add integration → GridWorks Connector**.
5. Use **Embedded demonstration** initially. It needs no cloud account, keys or broker.
   It is a local peer, not proof of a connection to GridWorks.
6. After commissioning, open the integration's device page for status, buttons and
   the participation selector. **Configure** reopens the commissioning menu.

The older GridWorks API may coexist under its original separate domain; this draft
repository distributes only the connector. There is no automatic migration of Pico data.

## Commissioning interface

Nothing is preselected for the pilot site. Repeated menu steps let you add as many meaningful
temperature channels as needed, each with label, existing HA entity, optional attribute,
unit, lower/upper limits and stale threshold. Tanks, PCM sensors, slabs and indoor spaces
use the same representation. A climate entity can use an existing temperature attribute.
Limits apply in the selected unit; no scalar SOC is calculated.

Define meters before binding power/energy signals: one plant meter or several generator
meters, with coverage and optional parent scope. Values retain declared units; no summing
of parent and submeter data is performed. Do not claim settlement certification.

Define opaque modes and services, then bind optional signals to those identities.
Mode's local state mapping stays local; cloud sees the opaque mode ID.
Use signal kinds to distinguish a service call, activity, delivery and adequacy.
Uninstrumented delivery remains unknown. No BTU meter or compressor percentage required.
Mode availability can be declared unknown/yes/no or bound to an existing binary entity.
Not-before/estimated-return timestamps accept epoch ms (unit `ms`) or seconds (`s`);
power capability signals accept W or kW.

Site context supports optional address/coordinates, weather and occupancy entities.
Only selected bindings are exported; entity registry IDs and local entity names stay local.
HA report times are identified as such; source acquisition times cannot be invented.

After setup: **Configure → Review proposed weather sources** presents the peer's catalog,
primary and multiple backups, requiring explicit confirmation. Embedded catalog entries
are labeled test entries and do not fetch live weather or certify representativeness.

## See the loop

Commission at least one temperature channel and limits. Define a meter boundary and
at least one mode with known availability to evaluate a power proposal; absent information
produces unknown/cannot-assess rather than fictitious capability.

- **Send observations** publishes the current selected readings, mode/service evidence,
  availability and context.
- **Exercise shadow protocol** delivers a clearly marked reassessment test notification
  and advances the local message exchange. It never changes plant states.
- The test peer proposes a five-minute **interval-average** target, not an instantaneous
  compressor command. HA reports a hypothetical decision; a deliberate substitution
  changes the peer's next proposal.
- **Shadow participation** can pause hypothetical pursuit while observations continue.
- **System changed** emits a reassessment/configuration notice.
- **Acknowledge reassessment notices** closes that notification path.

There is no inferred thermal response to these requests. Actual mode and readings remain
independent observations. A local demo does not complete the approved external-cloud
interop milestone. See [coverage](docs/COMMUNICATION_COVERAGE.md).

## External peer and Jessica handoff

Read [protocol and timing](docs/PROTOCOL.md), the [credential/interop handoff](docs/GRIDWORKS_HANDOFF.md)
and [proposed schemas](docs/proposed-sema/). These words require Sema review/registration,
generation and a cloud adapter before production GridWorks can understand them.

The companion peer runs separately in an approved test environment:
`python -m tools.shadow_peer --config /protected/broker.local.json`.
Reverse the HA send/receive topics in its protected config. Do not reuse a production
GNode key or assume this provisional topic profile is already approved by GridWorks.
TLS is mandatory outside loopback. Secrets and precise site information belong outside Git.

## Development and verification

Use Python3.14.2+ and a Linux HA development/test environment for full lifecycle tests.
The matching central fixtures require Linux; portable protocol tests can run on Windows.

```text
uv sync --group dev
uv run pytest -q
uv run ruff check custom_components/gridworks_connector tests tools
uv run python -m tools.generate_schemas
uv run python -m tools.build_package
```

Pin reviewed commits/locks; never auto-pull source into a running experiment.
Install/update commissioning and software credentials are separate from operational
GridWorks enrollment. Diagnostics are intentionally redacted. Local SQLite observation
history and outbox live under HA `.storage`; backups must protect them.

## Status and limitations

This is an initial functional development draft for review, not permission to activate
physical controls or claim market participation. Exact field names/default timings are
proposals. Local weather catalog, peer policy and reassessment trigger are deterministic
test functionality, not a learned optimizer, provider-discovery service or anomaly detector.
No communications outage history exists while HA is powered off. See tests and recorded
verification results for what has actually passed.

License/release ownership of the eventual organization product still needs maintainer
agreement. Earlier API history remains in Git provenance; the connector implementation
is newly authored and does not import the old Pico runtime.
