# GridWorks coordination package — unsent draft

Audience: Jessica and GridWorks agents. Prepared for the user to review/share; no outreach sent.

## Goal

Connect the HA integration to an approved GridWorks test LTN/service and close **all**
planned upstream/downstream pathways in shadow, with no plant actions or market commitments.
Preserve Alice's fixed-zero behavior. Use a separately named reactive deterministic
policy and generic-resource shadow coordinator. The companion peer is a runnable
prototype of that role, not a replacement production GridWorks stack.

## Included

- Installable HA component with native commissioning/options UI.
- Real user-selected entity observation adapter, mandatory temperature limits,
  meter/mode/service/context mappings and no physical-control adapter.
- Application journal/outbox, request decisions, status/notifications and dedicated MQTT client.
- Embedded demonstration and external test-peer CLI.
- Proposed Sema-style schemas, message names and timing notes in PROTOCOL.md.
- Tests and complete communication coverage checklist.

## Needed from GridWorks

1. Review proposed words; identify existing words to reuse and additions to register.
   Supply an approved minimal transitive runtime seed covering the complete matrix,
   generator revision/namespaced import guidance and serialized interoperability examples.
2. Choose the LTN/service implementation branch, cloud owner and approved endpoint.
   The current flo.params schema requires HP/tank facts; do not require fake tanks
   for a generic thermal asset. A new tuning name alone does not fix that schema.
3. Provision a separate test resource/principal, permitted run/vhost, broker endpoint,
   CA chain, client certificate and supported key provisioning/renewal workflow.
   Never send private keys through chat or Git. Confirm actual FIS runtime-instance policy.
4. Agree routing/envelope mapping and application receipt, freshness and shadow meanings.
   This draft's isolated topics are provisional, not production GridWorks routes.
5. Implement/review the cloud handlers for every coverage row, including weather-source
   confirmation and reassessment notification/acknowledgement, with deterministic
   test scenarios where real providers/inference are not yet available.
6. Run the complete trace-based test together after the pilot site commissioning.

## Honest acceptance boundary

Local embedded-peer tests establish local message handling only. Broker/TLS admission,
actual GridWorks Sema compatibility and a full approved-cloud trace require the shared
test environment. Optional missing instrumentation remains unknown, not successful delivery.
No learned dynamics, automatic control-loop audit or certification is claimed.

License, maintainers and eventual GridWorks organization repository remain to be agreed.
The personal fork/branch is a contribution workspace. No live HA installation or update
has been performed by this code-development task.
