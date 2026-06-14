# Residual Risk Register

This register tracks known enterprise readiness gaps. It should be reviewed before security questionnaires are returned to customers.

| Risk | Severity | Mitigation | Owner | Status | Planned Remediation |
| --- | --- | --- | --- | --- | --- |
| Live OIDC integrations not validated for each customer IdP | Medium | JWT/OIDC readiness, JWKS validation, claim mapping, and JIT tests are available | Security Engineering | Open | Pilot Azure AD, Okta, and Auth0 in staging |
| SCIM maturity is minimal and not full SCIM spec coverage | Medium | Disabled by default, dedicated bearer token, tenant allow-list, audit events | Security Engineering | Open | Validate with customer IdPs and expand spec coverage as needed |
| External notary provider maturity depends on selected provider | Medium | Safe external payload, fallback/fail-closed mode, no metadata transmission | Security Engineering | Open | Select provider, validate retention and legal acceptability |
| Redis HA validation not completed in production topology | Medium | Redis-backed rate limiter supports timeouts and fallback/fail-closed mode | Platform Operations | Open | Test managed Redis failover in staging |
| Frontend CSP maturity limited by inline React styles | Low | Nginx baseline headers, scanner, and CSP guidance exist | Frontend Engineering | Open | Move inline styles to static CSS and browser-test strict CSP |
| Formal SOC 2 audit not completed | High | Control evidence index and readiness binder available | Compliance Owner | Planned | Engage auditor and define SOC 2 readiness project |
| Formal HITRUST assessment not completed | High | Control evidence and risk register available | Compliance Owner | Planned | Engage HITRUST advisor and map controls |
| CI security checks may not be required by branch protection | Medium | Security validation workflow exists | Platform Operations | Open | Require workflow in GitHub branch protection |
| Production incident response requires customer-specific contacts | Medium | Runbook and review guide include process expectations | Operations Owner | Open | Complete environment-specific incident response appendix |
| Backup restore testing is environment-specific | Medium | Runbook describes backup and recovery expectations | Platform Operations | Open | Run restore drill before production go-live |

## Review Cadence

Review this register before enterprise security reviews, before production go-live, and after each hardening release.
