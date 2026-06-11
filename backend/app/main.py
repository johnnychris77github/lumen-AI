from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import time

from app.core.security_headers import SecurityHeadersMiddleware
from app.core.settings import settings
from app.routes.system import router as system_router
from app.routes.inspect import router as inspect_router
from app.routes.history import router as history_router
from app.routes.reports import router as reports_router
from app.routes.inspections import router as inspections_router
from app.routes.agent import router as agent_router
from app.routes.qa_review import router as qa_review_router
from app.routes.review_analytics import router as review_analytics_router
from app.routes.model_performance import router as model_performance_router
from app.routes.stream import router as stream_router
from app.routes.vendor_analytics import router as vendor_analytics_router
from app.routes.alerts import router as alerts_router
from app.db import Base, engine

app = FastAPI(title="LumenAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_enabled=settings.SECURITY_HEADERS_HSTS_ENABLED,
)


def wait_for_db(max_attempts: int = 30, sleep_seconds: int = 2) -> None:
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Database ready on attempt {attempt}")
            return
        except Exception as exc:
            last_error = exc
            print(f"Database not ready (attempt {attempt}/{max_attempts}): {exc}")
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Database did not become ready: {last_error}")


@app.on_event("startup")
async def _startup() -> None:
    wait_for_db()
    Base.metadata.create_all(bind=engine)


app.include_router(system_router, prefix=settings.API_PREFIX)
app.include_router(inspect_router, prefix=settings.API_PREFIX)
app.include_router(history_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)
app.include_router(inspections_router, prefix=settings.API_PREFIX)

app.include_router(agent_router, prefix=settings.API_PREFIX)

app.include_router(stream_router, prefix=settings.API_PREFIX)

app.include_router(vendor_analytics_router, prefix=settings.API_PREFIX)

app.include_router(alerts_router, prefix=settings.API_PREFIX)

app.include_router(qa_review_router, prefix=settings.API_PREFIX)

app.include_router(review_analytics_router, prefix=settings.API_PREFIX)

app.include_router(model_performance_router, prefix=settings.API_PREFIX)


from app.routes.site_analytics import router as site_analytics_router
from app.routes.executive_digest import router as executive_digest_router
from app.routes.board_reporting import router as board_reporting_router
from app.routes.digest_scheduler import router as digest_scheduler_router

app.include_router(site_analytics_router, prefix=settings.API_PREFIX)

app.include_router(executive_digest_router, prefix=settings.API_PREFIX)

app.include_router(board_reporting_router, prefix=settings.API_PREFIX)

app.include_router(digest_scheduler_router, prefix=settings.API_PREFIX)
from app.routes.digest_delivery import router as digest_delivery_router
from app.services.digest_scheduler_service import start_digest_scheduler
from app.services.retention_scheduler_service import start_retention_scheduler
from app.services.approval_escalation_service import start_approval_escalation_scheduler
from app.services.dunning_automation import start_dunning_scheduler
app.include_router(digest_delivery_router, prefix=settings.API_PREFIX)

from app.routes.digest_subscriptions import router as digest_subscriptions_router

app.include_router(digest_subscriptions_router, prefix=settings.API_PREFIX)

from app.routes.tenant_analytics import router as tenant_analytics_router

app.include_router(tenant_analytics_router, prefix=settings.API_PREFIX)

from app.routes.tenant_admin import router as tenant_admin_router

from app.routes.tenant_scoped_subscriptions import router as tenant_scoped_subscriptions_router

app.include_router(tenant_admin_router, prefix=settings.API_PREFIX)
app.include_router(tenant_scoped_subscriptions_router, prefix=settings.API_PREFIX)

from app.routes.audit_logs import router as audit_logs_router

app.include_router(audit_logs_router, prefix=settings.API_PREFIX)

from app.routes.compliance_exports import router as compliance_exports_router

app.include_router(compliance_exports_router, prefix=settings.API_PREFIX)

from app.routes.retention_admin import router as retention_admin_router

app.include_router(retention_admin_router, prefix=settings.API_PREFIX)

from app.routes.retention_enforcement import router as retention_enforcement_router

app.include_router(retention_enforcement_router, prefix=settings.API_PREFIX)

from app.routes.retention_scheduler import router as retention_scheduler_router

app.include_router(retention_scheduler_router, prefix=settings.API_PREFIX)

from app.routes.governance_console import router as governance_console_router

from app.routes.legal_hold_admin import router as legal_hold_admin_router

app.include_router(governance_console_router, prefix=settings.API_PREFIX)

app.include_router(legal_hold_admin_router, prefix=settings.API_PREFIX)

from app.routes.governance_approvals import router as governance_approvals_router

app.include_router(governance_approvals_router, prefix=settings.API_PREFIX)

from app.routes.approval_notifications import router as approval_notifications_router

app.include_router(approval_notifications_router, prefix=settings.API_PREFIX)

from app.routes.governance_reconciliation import router as governance_reconciliation_router

app.include_router(governance_reconciliation_router, prefix=settings.API_PREFIX)

from app.routes.trust_center import router as trust_center_router

from app.routes.trust_center_exports import router as trust_center_exports_router

app.include_router(trust_center_router, prefix=settings.API_PREFIX)

app.include_router(trust_center_exports_router, prefix=settings.API_PREFIX)

from app.routes.tenant_onboarding import router as tenant_onboarding_router

from app.routes.tenant_setup import router as tenant_setup_router

app.include_router(tenant_onboarding_router, prefix=settings.API_PREFIX)

app.include_router(tenant_setup_router, prefix=settings.API_PREFIX)

from app.routes.usage_metering import router as usage_metering_router

app.include_router(usage_metering_router, prefix=settings.API_PREFIX)

from app.routes.billing import router as billing_router

app.include_router(billing_router, prefix=settings.API_PREFIX)

from app.routes.subscription_lifecycle import router as subscription_lifecycle_router

app.include_router(subscription_lifecycle_router, prefix=settings.API_PREFIX)

from app.routes.dunning import router as dunning_router

app.include_router(dunning_router, prefix=settings.API_PREFIX)

from app.routes.dunning_automation import router as dunning_automation_router

app.include_router(dunning_automation_router, prefix=settings.API_PREFIX)

from app.routes.finance_console import router as finance_console_router

from app.routes.finance_exports import router as finance_exports_router

app.include_router(finance_console_router, prefix=settings.API_PREFIX)

app.include_router(finance_exports_router, prefix=settings.API_PREFIX)

from app.routes.entitlements import router as entitlements_router

app.include_router(entitlements_router, prefix=settings.API_PREFIX)

from app.routes.branding import router as branding_router

app.include_router(branding_router, prefix=settings.API_PREFIX)

from app.routes.notification_templates import router as notification_templates_router

app.include_router(notification_templates_router, prefix=settings.API_PREFIX)

from app.routes.automation_studio import router as automation_studio_router

app.include_router(automation_studio_router, prefix=settings.API_PREFIX)

from app.routes.executive_scorecards import router as executive_scorecards_router

app.include_router(executive_scorecards_router, prefix=settings.API_PREFIX)

from app.routes.briefings import router as briefings_router

app.include_router(briefings_router, prefix=settings.API_PREFIX)

from app.routes.leadership_packets import router as leadership_packets_router

app.include_router(leadership_packets_router, prefix=settings.API_PREFIX)

from app.routes.scheduled_leadership_packets import router as scheduled_leadership_packets_router

app.include_router(scheduled_leadership_packets_router, prefix=settings.API_PREFIX)

from app.routes.distribution_lists import router as distribution_lists_router

app.include_router(distribution_lists_router, prefix=settings.API_PREFIX)

from app.routes.packet_releases import router as packet_releases_router

app.include_router(packet_releases_router, prefix=settings.API_PREFIX)

from app.routes.packet_release_holds import router as packet_release_holds_router

app.include_router(packet_release_holds_router, prefix=settings.API_PREFIX)

from app.routes.release_governance_dashboard import router as release_governance_dashboard_router

app.include_router(release_governance_dashboard_router, prefix=settings.API_PREFIX)

from app.routes.governance_sla import router as governance_sla_router

app.include_router(governance_sla_router, prefix=settings.API_PREFIX)

from app.routes.governance_sla_scanner import router as governance_sla_scanner_router

from app.governance_sla_scanner import start_governance_sla_scanner

app.include_router(governance_sla_scanner_router, prefix=settings.API_PREFIX)

from app.routes.governance_command_center import router as governance_command_center_router

app.include_router(governance_command_center_router, prefix=settings.API_PREFIX)

from app.routes.implementation_readiness import router as implementation_readiness_router

app.include_router(implementation_readiness_router, prefix=settings.API_PREFIX)

from app.routes.customer_health import router as customer_health_router

app.include_router(customer_health_router, prefix=settings.API_PREFIX)

from app.routes.customer_success import router as customer_success_router

app.include_router(customer_success_router, prefix=settings.API_PREFIX)

from app.routes.customer_operations_hub import router as customer_operations_hub_router

app.include_router(customer_operations_hub_router, prefix=settings.API_PREFIX)

from app.routes.account_review_exports import router as account_review_exports_router

app.include_router(account_review_exports_router, prefix=settings.API_PREFIX)

from app.routes.scheduled_account_reviews import router as scheduled_account_reviews_router

app.include_router(scheduled_account_reviews_router, prefix=settings.API_PREFIX)

from app.routes.portfolio_dashboard import router as portfolio_dashboard_router

app.include_router(portfolio_dashboard_router, prefix=settings.API_PREFIX)

from app.routes.portfolio_briefings import router as portfolio_briefings_router
from app.routes.portfolio_briefing_exports import router as portfolio_briefing_exports_router

app.include_router(portfolio_briefings_router, prefix=settings.API_PREFIX)
app.include_router(portfolio_briefing_exports_router, prefix=settings.API_PREFIX)

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema
    app.openapi_schema = get_openapi(
        title=app.title,
        version=getattr(app, "version", "0.1.0"),
        description=getattr(app, "description", None),
        routes=app.routes,
    )
    return app.openapi_schema

app.openapi_schema = None
app.openapi = custom_openapi
