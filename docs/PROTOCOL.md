# Proposed Sema-style shadow message and timing package

Status: **draft for Jessica and her agents**. These names are not registered, not approved
GridWorks wire vocabulary, and not emitted by the official Sema generator yet.
The shipped local models use PascalCase, dotted TypeName, literal Version000,
closed objects and JSON Schema2020-12. Proposed schemas are reproducible from
`python -m tools.generate_schemas`. No generated official snapshots are hand-edited.

## Envelope

Every word carries TypeName, Version, ProtocolRevision, MessageId, ResourceId,
SessionId, Sender, Receiver, CreatedMs, Sequence, ConfigRevision, Shadow=true,
Historical and a typed Payload. Resource/session/message IDs are UUIDs; runtime
MQTT instance is a different identity. Peer names in this draft profile are ha/cloud.
Final GridWorks aliases/envelopes/edge rules need an adapter agreed with maintainers.

All times are UTC epoch milliseconds unless explicitly a sample's declared unit.
Observation original times are distinct from transport receipt/transmission time.
Individual values are asynchronous, never a fictitious simultaneous snapshot.

## Proposed words

| TypeName suffix after gw.thermal. | Payload meaning | Sender |
| --- | --- | --- |
| resource.config | Chosen channels/limits, meter boundaries, modes, services, capabilities, location | HA |
| observations | Individually timed values, units through channel definitions, quality and observation-set identity | HA |
| context | Chosen meteorology/occupancy and provenance | HA |
| context.calculated | Solar azimuth/zenith calculated from commissioned coordinates/time, with explicit source | Cloud |
| mode.event | Actual mode, event time and active-since; unknown valid | HA |
| availability | Per-mode availability, earliest start, estimated return and known power limits | HA |
| service.status | Requested/active/delivered/adequate, each unknown when unsupported | HA |
| participation | Pursuing/modified/paused/unknown and optional reason | HA |
| shadow.request | Window, average electrical W, boundary, preferred mode and sequence | Cloud |
| shadow.decision | Receipt-independent hypothetical pursuit, substitution, target status and optional reason | HA |
| peer.status | Current request, last peer message, readiness/engine/participation | Both |
| receipt | Application ingestion/rejection of MessageId; no ack-of-ack | Both |
| weather.proposal | Source catalog, coverage, variables and test/provider provenance | Cloud |
| weather.selection | Explicitly confirmed primary and backups, linked to proposal | HA |
| weather.status | Current source, reason and issue/valid times where applicable | Cloud |
| configuration.change | Revision/effective time/affected identities; user change notice | HA |
| reassessment | Suspected/requested/acknowledged/resolved notice, evidence, test flag | Both |
| gap | Bounded-history/outbox dropped count and reason | HA |
| error | Unsupported direction/protocol/config or other typed error | Both |

Wire examples and constraints are the JSON schemas alongside this document. The alias
generator spells acronym suffixes as Id/Ms/W in this draft; do not assume these match
a published Sema name until reviewed.

## Timing proposal

- Observations: event-driven for chosen HA state changes, plus60-second snapshots.
  Resampling cache keeps its HA report time. Same-value source freshness is limited
  by the upstream integration; no invented acquisition timestamp.
- Heartbeat:60seconds; a peer becomes stale after180seconds. The network client
  alone never emits an independent healthy supervisor heartbeat.
- Shadow policy: one proposal per five-minute window, configurable in a future
  approved profile. A substitution can trigger a replacement immediately.
- Interval-average6000W for five minutes implies500Wh; it is not a servo and no
  missed energy is automatically repaid.
- A future request is stored and evaluated when its start is reached by the engine
  tick. Actual evaluation resolution in this draft is the60-second tick.
- Expired requests cannot become current. A partially elapsed valid window is
  flagged; no catch-up. Minimum-run information affects hypothetical feasibility,
  never forces equipment to stop at the interval boundary.
- Sender sequence rejects superseded requests; duplicate MessageId reuses its
  recorded decision. Transport PUBACK does not equal ingestion/acceptance.
- Application receipts retire the bounded outbox. No ack-of-ack loop.
- Replay older than180seconds is Historical; original times remain. Historic
  requests are expired and historic heartbeat never refreshes liveness.
- MQTT QoS1, no retained requests; retained inbound messages are discarded.
  TLS validates the broker; topic permissions/identity use the approved test setup.
- Current resource/session/config revision and authorized peer must agree before
  a message is consumed. Unknown or incompatible words stay visible as errors.

SQLite journal/outbox is bounded (2000 trace/seen items,1000 pending messages) with
gap reporting; it is not an unlimited Recorder replacement. Cloud loss does not stop
local observations, and nothing here assumes measurements collected while HA was off.

## Coordination decisions

Approve/revise the words, version seed and namespaced generation; map the provisional
envelope/topics onto GridWorks transport; identify test peer owners and credentials;
confirm timing/retention limits and how live-versus-shadow routes are isolated.
No production acceptance/contract should be fabricated to bypass Alice's operator hold.

Both the HA endpoint and companion peer have bounded persistent outboxes/deduplication. A changed configuration opens a fresh session and reports unacknowledged old-session gaps; a restored heartbeat is never fresh liveness. The peer recovers request sequence from HA relationship status.

Illustrative *.example.json files and proposed_seed_request.yaml are included. The seed uses the existing GridWorks request shape, but cannot be generated from the official registry until these words are approved/registered. Run python -m tools.generate_examples to reproduce.
