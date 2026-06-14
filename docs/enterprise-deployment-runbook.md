# Enterprise Deployment Runbook

## Frontend CSP and Static Asset Hardening

Production frontend deployments should serve only reviewed Vite build output from `frontend/dist/` and apply browser security headers at the static host, CDN, or Nginx layer. Local Vite development can keep localhost and websocket exceptions, but those exceptions must not be copied to production.

Deployment checklist:

- Configure the production CSP documented in `docs/frontend-security-hardening.md`.
- Keep API calls same-origin through `/api` where possible, or allow only the approved HTTPS API origin.
- Run `python scripts/check_frontend_static_security.py frontend public` before publishing static assets.
- Confirm no secrets, hardcoded bearer tokens, private keys, production API keys, or private endpoints are embedded in the frontend bundle.
- Confirm all remote assets use HTTPS and no non-localhost mixed-content `http://` references remain.
- Confirm `Referrer-Policy`, `Permissions-Policy`, frame protection, content-type protection, and cross-origin isolation headers are applied by the static host.

Deployment responsibility note: CDN, object storage, Nginx, and managed static-host header configuration are production operations responsibilities. The application repository provides guidance, an Nginx baseline, and a scanner, but each deployed environment must validate the final browser-observed headers.

Remaining limitations:

- The current React frontend uses inline style objects, so production CSP temporarily allows `style-src 'unsafe-inline'`.
- Static scanning is pattern-based and does not replace code review or deployed-browser CSP testing.
