# Security Validation Workflow

## Purpose

The Security Validation workflow prevents regression of enterprise security controls before changes reach `main`. It validates authentication, authorization, tenant isolation, audit integrity, audit anchoring, JWT/OIDC readiness, reporting isolation, and migration safety using GitHub-hosted runners and local test infrastructure only.

The workflow is defined in `.github/workflows/security-validation.yml` and runs on:

- `pull_request`
- `push` to `main`

No production credentials, external OIDC providers, paid services, or production databases are required.

## Jobs

### `compile-checks`

Compiles key backend entry points:

- `backend/app/auth.py`
- `backend/app/deps.py`
- `backend/app/main.py`

It also recursively compiles:

- `backend/app/core/`
- `backend/app/models/`
- `backend/app/routes/`

Any Python compile error fails the job.

### `security-tests`

Runs the security-focused test manifest for enterprise controls. The job executes every listed test file that exists on the current branch and records missing listed tests as pending in an artifact. This keeps the workflow compatible with branches where future hardening PR test files have not merged yet, while automatically expanding coverage as those tests land.

Covered areas include:

- Tenant authorization for alerts, analytics, reporting, QA review, agent, and PowerBI routes
- Audit immutability and hash-chain controls
- Rate limiting
- Security headers
- Secrets management
- Session/token hardening
- JWT/OIDC readiness
- Tenant JIT provisioning

### `migration-validation`

Runs:

```bash
python -m alembic upgrade head
```

The job sets:

```bash
DATABASE_URL=sqlite:///security-validation-migration.db
LUMENAI_ENV=test
```

The database is fresh for each run and no production secrets are required.

To keep the validation independent from production settings and external services, the job writes a minimal CI-only Alembic environment file inside the runner before executing `upgrade head`, then restores the repository file in the runner workspace. This validates migration script execution against SQLite without changing application code.

### `dependency-safety`

Runs a lightweight dependency scan with `pip-audit` when available. The workflow fails only when a finding is explicitly reported with high or critical severity. Findings without severity metadata are recorded in the artifact for review without failing the build.

### `security-validation-summary`

Generates `security-validation-summary.txt` as a workflow artifact. The summary includes:

- Commit SHA
- Workflow run date
- Job results
- Tests executed policy
- Migration validation result
- Dependency scan result

## Failure Handling

- Compile failures usually indicate syntax errors or missing imports in security-sensitive modules.
- Security test failures should be treated as potential control regressions until triaged.
- Migration failures should be resolved before merge because they may block production rollout.
- High or critical dependency findings should be reviewed and remediated or explicitly risk-accepted in a follow-up security process.
- Missing test files in the security-test manifest are reported as pending, not failures, until their corresponding hardening PRs merge.

## Local Developer Commands

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
```

Run entry-point compile checks:

```bash
python -m py_compile backend/app/auth.py
python -m py_compile backend/app/deps.py
python -m py_compile backend/app/main.py
```

Compile security-sensitive packages recursively:

```bash
python - <<'PY'
import compileall
import sys

paths = ["backend/app/core", "backend/app/models", "backend/app/routes"]
failed = any(not compileall.compile_dir(path, quiet=1) for path in paths)
sys.exit(1 if failed else 0)
PY
```

Run security tests that exist on your branch:

```bash
python -m pytest \
  backend/tests/test_alerts_tenant_authorization.py \
  backend/tests/test_agent_tenant_authorization.py \
  backend/tests/test_powerbi_tenant_authorization.py
```

Run migration validation against SQLite:

```bash
DATABASE_URL=sqlite:///security-validation-migration.db python -m alembic upgrade head
```

Run dependency safety scan when `pip-audit` is available:

```bash
python -m pip install pip-audit
pip-audit -r requirements.txt
```

## Notes

This workflow is a validation gate for code review and merge safety. It does not require production credentials and does not claim SOC 2 or HITRUST certification.
