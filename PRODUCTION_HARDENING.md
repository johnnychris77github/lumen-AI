# Production Hardening

## Secrets and Configuration

Set `LUMENAI_ENV=production` for production deployments. Startup validation fails closed when required secrets are missing or use unsafe defaults. Error messages name only the affected variables and never print secret values.

Required production configuration:

- `SECRET_KEY`
- `JWT_SECRET_KEY` or `LUMENAI_JWT_SECRET`
- `DATABASE_URL`
- `LUMENAI_EVIDENCE_SIGNING_SECRET` when evidence signing is enabled
- `S3_ACCESS_KEY`, `S3_SECRET_KEY`, and `S3_BUCKET` when `S3_ENDPOINT` points to non-local storage

Do not use placeholder values such as `dev-token`, `changeme`, `secret`, `password`, local-only defaults, or empty strings in production.

Development and test environments remain compatible with local defaults. Production values should come from the deployment secret store or environment injection layer, not from committed files.
