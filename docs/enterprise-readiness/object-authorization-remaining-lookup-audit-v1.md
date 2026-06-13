# Object Authorization Remaining Lookup Audit v1

Date: 2026-06-13

## Scope

This audit inventories backend route groups that read, update, export, dispatch, or mutate tenant-owned data through raw `Inspection`, `AlertEvent`, `Tenant`, `Vendor`, CAPA/remediation, quality review, audit, packet, export, or tenant membership lookups.

Search coverage included:

- `db.query(models.Inspection)`
- `models.Inspection.id ==`
- `db.query(models.AlertEvent)`
- `models.AlertEvent.id ==`
- `inspection_id`
- `alert_event_id`
- `tenant_id`
- `vendor_id`
- `capa_id`
- `quality_event_id`
- `.filter(models.`
- Route handlers under `backend/app/routes`

Classification terms:

- `already protected`: route uses tenant membership scoping, route-level role authorization, or an explicit tenant-owned lookup that is constrained to the caller's authorized tenant.
- `protected but needs dedup/cleanup`: route is protected, but the authorization pattern is duplicated, inconsistent, or should be centralized.
- `missing tenant membership scoping`: route authenticates or role-checks the user, but data access is not constrained by `TenantMembership`.
- `missing authentication`: route returns or mutates tenant-owned data without an authentication dependency.
- `raw object lookup before authorization`: route loads a tenant-owned object by raw ID before proving the caller belongs to that object's tenant. This is acceptable only when it immediately applies 404/403 semantics before returning or mutating data.

## Recent Completed Protections

| Route group | File | Classification | Notes |
| --- | --- | --- | --- |
| `GET /inspections/{inspection_id}` | `backend/app/routes/inspections.py` | already protected | Preserves 404 for missing inspection and 403 for out-of-scope inspection. Global admins bypass tenant checks. Non-admin access is resolved through enabled `TenantMembership` by `current_user.email` and `Inspection.tenant_id`. |
| `GET /history`, `/history/summary`, `/history/export.json`, `/history/export.csv`, `/history/export.xlsx`, `/history/export.bundle.zip` | `backend/app/routes/history.py` | already protected | `fetch_rows(db, current_user)` scopes inspection rows through enabled `TenantMembership`, with global admin bypass. Summary and all export formats are built only from scoped rows. |
| `GET /alerts/feed`, `GET /alerts/open`, alert acknowledge/resolve/send/resend, `GET /alerts/history`, alert history exports | `backend/app/routes/alerts.py` | protected but needs dedup/cleanup | Alert feed/open/history/export/action endpoints now require auth and tenant scope through `TenantMembership`. `AlertEvent` access is resolved through `AlertEvent.inspection_id -> Inspection.id -> Inspection.tenant_id`. The helper pattern overlaps with inspection/history helpers and should eventually be centralized. |

## Route Inventory

### Highest-Risk Unauthenticated Inspection Reads

| Routes | File | Tenant-owned objects | Classification | Evidence and risk |
| --- | --- | --- | --- | --- |
| `GET /agent/inspection/{inspection_id}`, `GET /agent/feed` | `backend/app/routes/agent.py` | `Inspection` | missing authentication; missing tenant membership scoping; raw object lookup before authorization | Both handlers query inspections directly and have no `get_current_user`, `require_roles`, or `TenantMembership` dependency. `/agent/inspection/{inspection_id}` loads by raw inspection ID; `/agent/feed` returns latest inspection-derived assessments across tenants. |
| `GET /analytics/powerbi` | `backend/app/routes/analytics.py` | `Inspection` | missing authentication; missing tenant membership scoping | Handler returns a PowerBI dataset from `db.query(models.Inspection).all()` with no authentication or tenant scoping. |

### Role-Protected But Not Tenant-Scoped Inspection Reads, Exports, and Mutations

| Routes | File | Tenant-owned objects | Classification | Evidence and risk |
| --- | --- | --- | --- | --- |
| `GET /analytics/vendors`, vendor exports, `GET /analytics/vendors/{vendor_name}/scorecard.json`, `GET /analytics/vendors/{vendor_name}/scorecard.pdf` | `backend/app/routes/vendor_analytics.py` | `Inspection`, vendor-derived analytics | missing tenant membership scoping | Routes require broad roles, including `vendor_user` and `viewer` for the list endpoint, but build analytics from `db.query(models.Inspection).all()` before grouping by vendor. |
| `GET /tenant-analytics/summary`, tenant analytics exports | `backend/app/routes/tenant_analytics.py` | `Inspection` | missing tenant membership scoping | Routes accept tenant context from headers through `resolve_tenant` and require only `admin` or `spd_manager`; they filter by requested tenant ID but do not verify enabled tenant membership for non-global users. |
| `GET /site-analytics/summary`, site analytics exports | `backend/app/routes/site_analytics.py` | `Inspection` | missing tenant membership scoping | Routes require `admin` or `spd_manager` and aggregate every inspection row into site benchmarks. |
| `GET /review-analytics/summary`, feedback dataset exports | `backend/app/routes/review_analytics.py` | `Inspection`, QA feedback | missing tenant membership scoping | Routes require `admin` or `spd_manager`, then query all inspections and export approved/overridden feedback rows across tenants. |
| `GET /model-performance/summary`, model performance exports | `backend/app/routes/model_performance.py` | `Inspection`, QA feedback | missing tenant membership scoping | Reviewed rows are built from all inspection records and exported for model feedback analytics under role-only authorization. |
| `GET /qa-review/pending`, `POST /qa-review/{inspection_id}` | `backend/app/routes/qa_review.py` | `Inspection`, QA review mutation | missing tenant membership scoping; raw object lookup before authorization | Role check is present for `admin` and `spd_manager`, but pending reviews query all tenants. Mutation loads inspection by raw ID and updates QA fields without checking membership in the inspection tenant. |
| `GET /board-reporting/weekly`, weekly CSV/XLSX/bundle exports | `backend/app/routes/board_reporting.py` | `Inspection` | missing tenant membership scoping | Board reporting uses role-only auth and builds reports from all inspections in the date window. |
| `POST /digest-scheduler/run-now` | `backend/app/routes/digest_delivery.py` | `Inspection`, digest delivery | missing tenant membership scoping | Digest payload is generated from all inspections in the date window, then dispatched. |
| Executive digest summary/export routes | `backend/app/routes/executive_digest.py` | `Inspection` | missing tenant membership scoping | Digest builders query all inspections for executive summaries and exports under role-only auth. |

### Tenant Membership-Scoped Route Groups

| Routes | File | Tenant-owned objects | Classification | Evidence and risk |
| --- | --- | --- | --- | --- |
| Audit log list and exports | `backend/app/routes/audit_logs.py` | `AuditLog` | already protected | Uses `require_tenant_roles` and filters audit rows by the tenant resolved from enabled membership. |
| Compliance evidence pack exports and verification | `backend/app/routes/compliance_exports.py` | `Inspection`, `AuditLog`, retention metadata | already protected | Uses `require_tenant_roles("tenant_admin", "site_admin")`; inspection and audit queries use the authorized tenant ID. |
| Leadership packet generate/list/get/download | `backend/app/routes/leadership_packets.py` | `LeadershipPacket` | already protected | Uses `require_tenant_roles`; object lookup helper constrains by both `packet_id` and authorized tenant ID. |
| Account review export generate/list/get/download | `backend/app/routes/account_review_exports.py` | `AccountReviewExport` | already protected | Uses `require_tenant_roles`; object lookup helper constrains by both `export_id` and authorized tenant ID. |
| Trust center summary and trust center exports | `backend/app/routes/trust_center.py`, `backend/app/routes/trust_center_exports.py` | Governance approvals/rollbacks, audit logs, retention metadata, branding | already protected | Uses enabled tenant membership through `require_tenant_roles`; downstream lookups use the resolved tenant. |
| Tenant setup/readiness and tenant subscriptions | `backend/app/routes/tenant_setup.py`, `backend/app/routes/tenant_scoped_subscriptions.py` | Tenant memberships, retention/subscription state | already protected | Uses `require_tenant_roles`; lookups are tied to the authorized tenant ID or tenant name aliases. |
| Billing, entitlements, usage metering, branding | `backend/app/routes/billing.py`, `backend/app/routes/entitlements.py`, `backend/app/routes/usage_metering.py`, `backend/app/routes/branding.py` | Tenant billing, quota, usage, entitlement, branding records | already protected | Route dependencies require enabled membership for the tenant and filter by the resolved tenant. |
| Customer health/success/operations routes | `backend/app/routes/customer_health.py`, `backend/app/routes/customer_success.py`, `backend/app/routes/customer_operations_hub.py` | Customer/tenant operational records | already protected | Uses `require_tenant_roles` and tenant-derived filters. |
| Governance approval, command center, console, reconciliation, SLA, release, retention, legal hold, scheduled packet routes | governance/retention/packet route files using `require_tenant_roles` | Governance, release, retention, legal hold, packet records | already protected | Route group generally uses enabled tenant membership and tenant-keyed filters. Spot checks should continue during each feature PR because these modules contain many object-specific helper lookups. |

### Manually Authenticated Portfolio and Governance Routes

| Routes | File | Tenant-owned objects | Classification | Evidence and risk |
| --- | --- | --- | --- | --- |
| `GET/POST /tenant-remediations`, `/tenant-remediations/rollup`, `/open`, `/overdue`, `/from-insight/{tenant_id}`, `GET/PATCH/POST /tenant-remediations/{remediation_id}` | `backend/app/routes/tenant_remediations.py` | Tenant remediation / CAPA-like action records | missing tenant membership scoping; raw object lookup before authorization | Routes call `app.auth.get_current_user(authorization)` manually, then list all remediations or operate by raw tenant/remediation IDs. No `TenantMembership` check gates tenant-specific reads or mutations. |
| `GET /tenant-insights/top-risks`, `/tenant-insights/rollup`, `/tenant-insights/{tenant_id}` | `backend/app/routes/tenant_insights.py` | Tenant insight records | missing tenant membership scoping; raw object lookup before authorization | Manual token auth is present, but top-risk/rollup endpoints return portfolio-wide tenant insight data and `{tenant_id}` lookup is not membership-checked. |
| `GET/POST /portfolio-tenants`, `/portfolio-tenants/rollup`, `/rescore`, `/generate-board-briefing`, `GET/PATCH /portfolio-tenants/{tenant_id}` | `backend/app/routes/portfolio_tenants.py` | Tenant/customer portfolio records | missing tenant membership scoping; raw object lookup before authorization | Manual token auth is present, but listing, rescoring, board briefing generation, and raw tenant ID read/update are not scoped by tenant membership or global admin role. |
| `GET /enterprise-audit-events`, `/rollup`, `/narrative` | `backend/app/routes/enterprise_audit.py` | Enterprise audit events | missing tenant membership scoping | Manual auth only. Audit event reads and rollups are portfolio-wide and should be tenant-scoped unless explicitly global-admin-only. |
| `GET /enterprise-access-control/decisions`, `/rollup`, `/narrative`, `/policies`, `/check` | `backend/app/routes/enterprise_access_control.py` | Access decision records / policy checks | missing tenant membership scoping | Manual auth only. Decision and rollup endpoints can expose cross-tenant access governance state. |
| Governance packet CRUD/export/delivery/download routes | `backend/app/routes/governance_packet_exports.py` | Governance packets, generated artifacts, deliveries | missing tenant membership scoping; raw object lookup before authorization | Manual auth only. Packet/export/download helpers operate by packet/export IDs and file paths without proving tenant ownership. |
| Portfolio briefing export/download/distribution routes | `backend/app/routes/portfolio_briefing_exports.py` | Portfolio briefing exports, artifacts, deliveries | missing tenant membership scoping; raw object lookup before authorization | Manual auth only. Export/download/distribution helpers operate by briefing/export IDs and artifact paths without tenant ownership checks. |
| Portfolio briefing schedules/deliveries/recurring scheduler routes | `backend/app/routes/portfolio_briefing_schedules.py`, `backend/app/routes/portfolio_briefing_deliveries.py`, `backend/app/routes/portfolio_briefing_recurring_scheduler.py` | Briefing schedules and delivery records | missing tenant membership scoping | These files use the same manual auth pattern and should be reviewed with the portfolio briefing export patch. |
| Executive briefing dashboard/decisions/escalations/KPI scheduler/snapshots route group | `backend/app/routes/executive_briefing_dashboard.py`, `backend/app/routes/executive_decisions.py`, `backend/app/routes/executive_escalations.py`, `backend/app/routes/executive_kpi_scheduler.py`, `backend/app/routes/executive_kpi_snapshots.py` | Executive decision, escalation, KPI, and briefing records | missing tenant membership scoping | These route files use manual auth patterns in the scan and should be moved to tenant membership scoping or explicitly restricted to global admins. |

### Platform Admin Route Groups

| Routes | File | Tenant-owned objects | Classification | Evidence and risk |
| --- | --- | --- | --- | --- |
| Tenant membership admin routes | `backend/app/routes/tenant_admin.py` | `TenantMembership` | already protected | Restricted to `admin` role and intended to manage membership state globally. Consider expanding accepted global admin roles for consistency, but object scoping is intentionally platform-admin. |
| Tenant onboarding/bootstrap routes | `backend/app/routes/tenant_onboarding.py` | Tenant onboarding and membership bootstrap records | already protected | Restricted to `admin` role. Intended global administration path. |

## Cross-Cutting Observations

1. There are now three authorization patterns for tenant-owned inspection data:
   - object-specific helpers in `inspections.py`
   - scoped row/query helpers in `history.py` and `alerts.py`
   - `require_tenant_roles` for many newer tenant modules

2. `require_tenant_roles` uses enabled `TenantMembership`, which is the right tenant access source. However, it resolves the requested tenant from `X-Tenant-ID` headers, so routes that use it should continue to ensure object lookups are constrained to that resolved tenant ID.

3. Several older analytics/reporting routes still use role-only authorization and raw `Inspection` queries. These are not public, but they can expose cross-tenant operational, vendor, site, QA, and model feedback data to non-global roles such as `spd_manager`, `vendor_user`, or `viewer`.

4. Several portfolio and governance routes use a separate manual `app.auth.get_current_user(authorization)` pattern. That is authentication only; it does not enforce role requirements, global admin-only access, or tenant membership scope.

5. Raw object lookup before authorization appears in both fixed and unfixed paths. The fixed paths maintain safe 404/403 semantics before returning or mutating data. Unfixed paths load by raw object ID and then return, mutate, dispatch, or download artifacts without proving tenant ownership.

## Recommended Next Patch

The next highest-risk route group to patch is:

`backend/app/routes/tenant_remediations.py`, `backend/app/routes/tenant_insights.py`, and `backend/app/routes/portfolio_tenants.py`.

Why this group first:

- It contains read and mutation routes, not only analytics.
- It operates on tenant/customer portfolio state and CAPA-like remediation records.
- It has raw `{tenant_id}` and `{remediation_id}` lookup paths.
- It uses manual authentication without role enforcement or `TenantMembership` scoping.
- A patch can be small and reviewable by introducing a shared tenant membership/global-admin authorization helper for this group and constraining list/rollup endpoints to authorized tenants.

Suggested follow-up order:

1. Patch tenant remediations, tenant insights, and portfolio tenant routes.
2. Patch unauthenticated `/agent/*` and `/analytics/powerbi` routes by adding auth plus membership-scoped inspection access.
3. Patch role-only inspection analytics/export families: vendor, tenant, site, review, model performance, board reporting, digest, executive digest.
4. Patch manually authenticated governance/portfolio briefing packet/export/download routes with tenant-owned object constraints and artifact ownership checks.
5. Deduplicate inspection/history/alert tenant membership helpers into a central object authorization module to reduce future drift.

## Validation

Documentation-only change. No Python files were modified, so no `python -m py_compile` command was required.
