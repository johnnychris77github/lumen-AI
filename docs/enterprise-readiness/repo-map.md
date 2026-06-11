# LumenAI Repository Map

## Backend
- `backend/app/main.py`: FastAPI app, CORS, startup database initialization, route registration.
- `backend/app/routes/`: API routes for inspection, history, reports, QA review, alerts, analytics, digest, and reporting.
- `backend/app/models/`: SQLAlchemy models for inspections, users, tenant membership, alerts, audit, governance, billing, and reporting.
- `backend/app/core/`: runtime settings and security-oriented core helpers.
- `backend/app/db/`: SQLAlchemy base, session, and model registration.

## Frontend
- `frontend/package.json`: Vite/React package configuration.
- `frontend/src/`: React source tree when present in the working copy.

## Tests
- Backend tests should live under `backend/tests/`.
- CI discovers test folders under the repository.

## Deployment
- Root `Dockerfile` builds the Python API image.
- `.github/workflows/ci.yml` runs Python checks and Docker image builds.
- No `render.yaml` was found during this pass.

## Security and auth files
- `backend/app/deps.py`: current-user dependency and temporary token authentication.
- `backend/app/authz.py`: role-based authorization dependency.
- `backend/app/tenant.py`: tenant resolution from request headers.
- `backend/app/models/tenant_membership.py`: tenant membership model.
- `backend/app/routes/inspections.py`: single-inspection access endpoint.

## Immediate enterprise-readiness risks
1. Tenant identity is still accepted from request headers, so it must not be trusted as proof of authorization.
2. Temporary development tokens remain useful for local development but should be disabled in production.
3. Single-object reads and write actions must verify tenant scope before returning or mutating records.
4. CI should fail on test failures instead of allowing `pytest` failures to pass silently.
