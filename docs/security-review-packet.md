# Security Review Packet

## SCIM User and Group Lifecycle Provisioning

LumenAI includes SCIM readiness for enterprise identity lifecycle management. SCIM is disabled by default and requires a dedicated bearer token when enabled. Development tokens are not accepted for SCIM authorization.

Supported lifecycle controls:

- User provisioning creates or updates the existing user record and tenant membership.
- User deactivation disables tenant membership instead of hard-deleting the user.
- Group role mapping can assign only configured allowed roles.
- Tenant allow-lists prevent cross-tenant provisioning.
- SCIM actions create audit events such as `scim_user_created`, `scim_user_updated`, `scim_user_deactivated`, `scim_group_created`, `scim_group_updated`, and `scim_provisioning_denied`.

Security posture:

- SCIM bearer tokens must be stored as production secrets and never committed.
- SCIM errors must not leak bearer tokens or raw secrets.
- Default role assignment should follow least privilege.
- Admin role assignment should remain disabled unless explicitly approved for a specific enterprise deployment.

Residual gaps:

- Live Azure AD, Okta, and Auth0 end-to-end validation remains customer/environment-specific.
- The implementation provides minimal SCIM-compatible schemas and does not claim complete SCIM specification coverage.
- Group lifecycle behavior is scoped to tenant role mapping rather than a full external group directory sync.
