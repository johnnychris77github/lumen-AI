# Enterprise Deployment Runbook

## SCIM Lifecycle Provisioning

SCIM support is disabled by default and is intended for enterprise user and group lifecycle provisioning through identity providers such as Azure AD, Okta, and Auth0.

### Configuration

| Variable | Purpose | Production expectation |
| --- | --- | --- |
| `LUMENAI_SCIM_ENABLED` | Enables SCIM endpoints | `false` by default; enable only after IdP setup is approved |
| `LUMENAI_SCIM_BEARER_TOKEN` | Dedicated SCIM bearer token | Strong random secret stored outside source control |
| `LUMENAI_SCIM_ALLOWED_TENANTS` | Comma-separated tenant IDs SCIM may manage | Restrict to approved customer tenants |
| `LUMENAI_SCIM_DEFAULT_ROLE` | Default role for provisioned memberships | Least privilege, typically `viewer` |
| `LUMENAI_SCIM_ALLOWED_ROLES` | Roles SCIM group mapping may assign | Avoid admin roles unless explicitly approved |

### Supported Lifecycle Operations

- Create or update a user membership with `POST /scim/v2/Users`.
- Read users with `GET /scim/v2/Users` and `GET /scim/v2/Users/{id}`.
- Patch user active state or role with `PATCH /scim/v2/Users/{id}`.
- Deactivate a user with `DELETE /scim/v2/Users/{id}`. This disables membership and does not hard-delete the user.
- List groups with `GET /scim/v2/Groups`.
- Create or patch group role mappings with `POST /scim/v2/Groups` and `PATCH /scim/v2/Groups/{id}`.

### Identity Provider Setup Notes

- Configure the IdP SCIM base URL to the deployed LumenAI `/scim/v2` endpoint.
- Use the dedicated SCIM bearer token, not the development token or user API tokens.
- Map user email to `userName` or primary `emails.value`.
- Map tenant ID, tenant name, and role through the LumenAI SCIM extension fields.
- Restrict provisioning to approved tenant IDs and least-privilege roles.

### Limitations and Residual Gaps

- The implementation is intentionally minimal and does not attempt full SCIM specification coverage.
- Group objects are represented as role mappings to tenant memberships rather than a separate long-lived group directory.
- Production deployments should rotate SCIM bearer tokens and monitor `scim_*` audit events.
- SCIM does not bypass tenant authorization or create admin roles unless explicitly configured in allowed roles.
