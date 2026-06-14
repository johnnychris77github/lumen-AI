# Frontend Security Hardening

## Scope

This guide covers the Vite/React frontend under `frontend/`, static files under `public/` when present, and deployment of the built `frontend/dist/` assets. It is intended for production static hosting through Nginx, a CDN, or an equivalent managed frontend host without breaking local Vite development.

## Recommended Production CSP

Recommended production header:

```text
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests
```

Deployment notes:

- Replace `https://api.example.com` with the approved production API origin when API calls do not use same-origin `/api`.
- Keep `script-src 'self'` for production. Do not allow inline scripts unless a reviewed nonce/hash strategy is implemented.
- `style-src 'unsafe-inline'` is tolerated for the current React inline-style usage; remove it after moving inline styles into static CSS.
- Use `frame-ancestors 'none'` to prevent clickjacking.
- Keep `object-src 'none'` and `base-uri 'self'`.

## Development CSP Exceptions

Local Vite development may require looser policy than production:

- `connect-src 'self' ws://localhost:* http://localhost:* http://127.0.0.1:*`
- Vite dev server websocket/HMR endpoints
- Local API endpoints such as `http://localhost:8000`

Do not copy development CSP exceptions into production.

## API Origin Allowlist

Production builds should use one of:

- Same-origin `/api` routed by the static host or edge proxy.
- A specific HTTPS API origin configured through `VITE_API_BASE_URL`.

Rules:

- Do not use wildcard API origins.
- Do not embed private network API endpoints in public static bundles.
- Do not reference non-localhost `http://` API URLs.
- Keep CORS allowlists aligned with approved frontend origins.

## Static Asset Loading Rules

- Serve JavaScript, CSS, fonts, and images from the same trusted static origin whenever possible.
- Use HTTPS for all remote assets.
- Avoid third-party script tags.
- Prefer bundled dependencies over runtime CDN scripts.
- Do not load executable assets from user-controlled URLs.
- Do not commit generated `dist/` artifacts unless the release process explicitly requires it.

## Image, Script, Style, and Font Restrictions

- Images: allow `'self'`, `data:`, and `blob:` only when needed for previews or generated assets.
- Scripts: production should be `'self'` only, with no inline scripts.
- Styles: prefer `'self'`; current inline React styles require temporary `'unsafe-inline'`.
- Fonts: prefer `'self'`; allow `data:` only if bundled font tooling requires it.

## Referrer and Permissions Policy Alignment

Recommended frontend headers should align with backend API security headers:

```text
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

## Vite Build Output Hosting

Recommended deployment flow:

1. Build with `npm run build` inside `frontend/`.
2. Serve only the generated `frontend/dist/` output.
3. Apply CSP and browser security headers at the static host, CDN, or Nginx layer.
4. Route `/api` to the backend API when same-origin API access is used.
5. Run the static security scanner before publishing assets.

## Safe Static Asset Checklist

- [ ] No secrets in frontend environment variables.
- [ ] Only `VITE_` variables are intentionally exposed to the browser.
- [ ] No hardcoded bearer tokens.
- [ ] No production API keys.
- [ ] No private endpoints embedded in the static bundle.
- [ ] No non-localhost mixed-content `http://` asset references.
- [ ] No private key material or certificate keys.
- [ ] No inline script tags in production HTML.
- [ ] CSP, referrer policy, permissions policy, frame protection, and content-type headers are set by the host.

## Static Security Scanner

Run:

```bash
python scripts/check_frontend_static_security.py frontend public
```

The scanner reports file path, line number, rule, severity, and a safe message. It does not print matched secret values.

The scanner checks for:

- `dev-token`
- Hardcoded bearer token patterns
- Private key markers
- Obvious API secret assignments
- Non-localhost `http://` references
- Inline script tags

## Limitations

- Static scanning is pattern-based and does not prove the absence of all secrets.
- Production CSP should be validated in a browser against the deployed frontend.
- CDN, object storage, and reverse proxy configuration remain deployment responsibilities.
