# Security Review Packet

## External Audit Timestamp / Notary Provider

LumenAI supports a pluggable audit anchor provider model with `internal` and `external_http` providers. The external provider can timestamp or notarize an audit chain anchor outside the application database, reducing the risk that database rollback or full-database tampering goes undetected.

Only safe anchor material is shared externally:

- Anchor hash
- Tenant ID
- Anchor timestamp
- Last audit log ID
- Number of records covered

The integration does not transmit full audit metadata, audit record details, request payloads, bearer tokens, or provider secrets. Only a safe provider reference is stored with the anchor record.

Failure modes:

- `internal_fallback` preserves anchor creation availability by falling back to an internal anchor.
- `fail_closed` blocks anchor creation when the external provider fails.

This is an enterprise readiness control and does not claim SOC 2, HITRUST, HIPAA, or other certification.
