# Enterprise Deployment Runbook

## External Audit Timestamp / Notary Provider

Audit chain anchors can use the default internal provider or an external HTTP timestamp/notary provider. The internal provider remains the default and is suitable for local development and deployments that have not approved an external notary service.

### Configuration

| Variable | Purpose | Production expectation |
| --- | --- | --- |
| `LUMENAI_AUDIT_ANCHOR_PROVIDER` | `internal` or `external_http` | Use `external_http` only after provider approval |
| `LUMENAI_AUDIT_ANCHOR_EXTERNAL_URL` | External notary endpoint | HTTPS endpoint only |
| `LUMENAI_AUDIT_ANCHOR_EXTERNAL_TOKEN` | Provider bearer token | Store as a production secret |
| `LUMENAI_AUDIT_ANCHOR_TIMEOUT_SECONDS` | HTTP timeout | Low timeout to avoid request pileups |
| `LUMENAI_AUDIT_ANCHOR_FAIL_MODE` | `internal_fallback` or `fail_closed` | Choose based on availability vs enforcement requirements |

### Data Shared With Provider

The external provider receives only:

- `anchor_hash`
- `tenant_id`
- `timestamp`
- `last_audit_log_id`
- `records_covered`

Full audit metadata, audit record details, request payloads, and secrets must not be sent to the provider.

### Failure Modes

- `internal_fallback`: create an internal anchor if the external provider is unavailable.
- `fail_closed`: block anchor creation if the external provider is unavailable.

External provider tokens must never appear in logs, errors, or stored anchor references.

### Residual Risks

External timestamp anchoring improves rollback/tamper detection but does not by itself certify SOC 2, HITRUST, HIPAA, or any other compliance framework. Provider availability, provider retention, network egress controls, and customer contract requirements remain deployment responsibilities.
