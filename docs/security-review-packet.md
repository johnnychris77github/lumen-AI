# Security Review Packet

## Frontend CSP and Static Asset Hardening

The frontend security posture is based on static-host security headers, safe Vite build practices, and pre-deployment scanning for hardcoded browser-exposed secrets.

Controls documented or added:

- Production CSP guidance with `script-src 'self'`, `object-src 'none'`, `base-uri 'self'`, and `frame-ancestors 'none'`.
- Nginx static-host baseline headers for CSP, referrer policy, permissions policy, frame protection, content-type protection, and cross-origin resource policies.
- API origin allowlist guidance for same-origin `/api` or approved HTTPS API origins.
- Static asset rules prohibiting hardcoded bearer tokens, production API keys, private keys, private endpoints, and non-localhost mixed-content HTTP references.
- `scripts/check_frontend_static_security.py` scanner for frontend/static files.

Residual limitations:

- Production CSP must be validated against the deployed frontend and customer hosting layer.
- Inline React style usage currently requires `style-src 'unsafe-inline'` until styles are moved to static CSS.
- CDN/static host configuration remains a shared deployment responsibility.
