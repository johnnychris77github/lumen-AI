# AGENTS.md

LumenAI is an SPD/IP/vendor quality, CAPA, and audit-readiness platform.

Before starting work, read:
- CURRENT_STATE.md
- SECURITY_HARDENING_BACKLOG.md
- README.md

Top priority: backend and frontend security hardening.

Rules:
- Enforce tenant, vendor, facility, role, and actor boundaries.
- Add tests for security-sensitive changes.
- Backend authorization must not depend on frontend hiding.
- Preserve audit, governance, evidence, and