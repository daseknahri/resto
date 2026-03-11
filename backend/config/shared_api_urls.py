from django.urls import include, path
from rest_framework import routers

from accounts.views import (
    ActivationView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    SessionView,
)
from config.api import health_view
from menu.views import AnalyticsEventIngestView
from sales.views import (
    AdminReservationAlertsView,
    AdminPlanFeatureFlagListView,
    AdminPlanFeatureFlagUpdateView,
    AdminTenantLifecycleView,
    AdminTenantListView,
    AdminTenantSettingsExportView,
    AdminTenantSettingsImportView,
    AdminTenantTimelineView,
    AdminTierUpgradeRequestDecisionView,
    AdminTierUpgradeRequestListView,
    AdminAuditLogViewSet,
    LeadOnboardingPackageView,
    LeadProvisionPreviewView,
    LeadResendActivationView,
    LeadViewSet,
    ProvisionLeadViewSet,
    ProvisioningJobViewSet,
)

shared_api_router = routers.DefaultRouter()
shared_api_router.register(r"leads", LeadViewSet, basename="lead")
shared_api_router.register(r"lead-provision", ProvisionLeadViewSet, basename="lead-provision")
shared_api_router.register(r"provision-jobs", ProvisioningJobViewSet, basename="provision-jobs")
shared_api_router.register(r"admin-audit-logs", AdminAuditLogViewSet, basename="admin-audit-logs")

shared_api_urlpatterns = [
    path("api/health/", health_view, name="health"),
    path("api/activate/", ActivationView.as_view(), name="activate"),
    path("api/login/", LoginView.as_view(), name="login"),
    path("api/logout/", LogoutView.as_view(), name="logout"),
    path("api/session/", SessionView.as_view(), name="session"),
    path("api/password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("api/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("api/analytics/events/", AnalyticsEventIngestView.as_view(), name="analytics-events"),
    path("api/lead-provision-preview/<int:lead_id>/", LeadProvisionPreviewView.as_view(), name="lead-provision-preview"),
    path("api/lead-resend-activation/<int:lead_id>/", LeadResendActivationView.as_view(), name="lead-resend-activation"),
    path("api/lead-onboarding-package/<int:lead_id>/", LeadOnboardingPackageView.as_view(), name="lead-onboarding-package"),
    path("api/admin-reservation-alerts/", AdminReservationAlertsView.as_view(), name="admin-reservation-alerts"),
    path("api/admin-plan-feature-flags/", AdminPlanFeatureFlagListView.as_view(), name="admin-plan-feature-flags"),
    path(
        "api/admin-plan-feature-flags/<str:plan_code>/",
        AdminPlanFeatureFlagUpdateView.as_view(),
        name="admin-plan-feature-flags-update",
    ),
    path("api/admin-tenants/", AdminTenantListView.as_view(), name="admin-tenants"),
    path("api/admin-tenants/<int:tenant_id>/lifecycle/", AdminTenantLifecycleView.as_view(), name="admin-tenant-lifecycle"),
    path("api/admin-tenants/<int:tenant_id>/timeline/", AdminTenantTimelineView.as_view(), name="admin-tenant-timeline"),
    path(
        "api/admin-tenants/<int:tenant_id>/settings-export/",
        AdminTenantSettingsExportView.as_view(),
        name="admin-tenant-settings-export",
    ),
    path(
        "api/admin-tenants/<int:tenant_id>/settings-import/",
        AdminTenantSettingsImportView.as_view(),
        name="admin-tenant-settings-import",
    ),
    path(
        "api/admin-tier-upgrade-requests/",
        AdminTierUpgradeRequestListView.as_view(),
        name="admin-tier-upgrade-requests",
    ),
    path(
        "api/admin-tier-upgrade-requests/<int:request_id>/decision/",
        AdminTierUpgradeRequestDecisionView.as_view(),
        name="admin-tier-upgrade-request-decision",
    ),
    path("api/", include(shared_api_router.urls)),
]
