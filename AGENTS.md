# AGENTS.md

You are working on LumenAI, an enterprise-ready SPD/IP/vendor quality, CAPA, and audit-readiness platform.

Always read these files before starting work:

- CURRENT_STATE.md
- SECURITY_HARDENING_BACKLOG.md
- README.md

Current top priority: backend and frontend security hardening.

Security rules:

- Enforce tenant, vendor, facility, role, and actor boundaries.
- Add tests for every security-sensitive change.
- Never rely only on frontend hiding for authorization.
- Do not remove audit