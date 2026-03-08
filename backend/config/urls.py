from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
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
from menu.views import (
    AnalyticsEventIngestView,
    AnalyticsSummaryView,
    CategoryViewSet,
    CheckoutIntentView,
    DishOptionViewSet,
    DishViewSet,
    OrderHandoffView,
    TableBulkGenerateView,
    TableContextView,
    TableLinkViewSet,
)
from sales.views import (
    AdminReservationAlertsView,
    AdminTenantLifecycleView,
    AdminTenantListView,
    AdminTierUpgradeRequestDecisionView,
    AdminTierUpgradeRequestListView,
    AdminAuditLogViewSet,
    LeadOnboardingPackageView,
    LeadProvisionPreviewView,
    OwnerReservationDetailView,
    OwnerReservationExportView,
    OwnerReservationBulkReminderView,
    OwnerReservationBulkStatusView,
    OwnerReservationReminderView,
    OwnerReservationReminderResultView,
    OwnerReservationBulkReminderResultView,
    OwnerReservationTimelineView,
    OwnerReservationListView,
    LeadResendActivationView,
    LeadViewSet,
    ProvisionLeadViewSet,
    ProvisioningJobViewSet,
    TierUpgradeTargetsView,
    TierUpgradeRequestListCreateView,
)
from tenancy.api import ImageDeleteView, ImageUploadView, ProfileView, TenantMetaView

router = routers.DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"dishes", DishViewSet, basename="dish")
router.register(r"dish-options", DishOptionViewSet, basename="dish-option")
router.register(r"tables", TableLinkViewSet, basename="table-link")
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"lead-provision", ProvisionLeadViewSet, basename="lead-provision")
router.register(r"provision-jobs", ProvisioningJobViewSet, basename="provision-jobs")
router.register(r"admin-audit-logs", AdminAuditLogViewSet, basename="admin-audit-logs")

urlpatterns = [
    path("api/health/", health_view, name="health"),
    path("api/meta/", TenantMetaView.as_view(), name="tenant-meta"),
    path("api/profile/", ProfileView.as_view(), name="tenant-profile"),
    path("api/uploads/image/", ImageUploadView.as_view(), name="image-upload"),
    path("api/uploads/image-delete/", ImageDeleteView.as_view(), name="image-delete"),
    path("api/activate/", ActivationView.as_view(), name="activate"),
    path("api/login/", LoginView.as_view(), name="login"),
    path("api/logout/", LogoutView.as_view(), name="logout"),
    path("api/session/", SessionView.as_view(), name="session"),
    path("api/password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("api/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("api/order-handoff/", OrderHandoffView.as_view(), name="order-handoff"),
    path("api/checkout-intent/", CheckoutIntentView.as_view(), name="checkout-intent"),
    path("api/analytics/events/", AnalyticsEventIngestView.as_view(), name="analytics-events"),
    path("api/analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("api/table-context/<slug:table_slug>/", TableContextView.as_view(), name="table-context"),
    path("api/tables/bulk-generate/", TableBulkGenerateView.as_view(), name="table-bulk-generate"),
    path("api/lead-provision-preview/<int:lead_id>/", LeadProvisionPreviewView.as_view(), name="lead-provision-preview"),
    path("api/lead-resend-activation/<int:lead_id>/", LeadResendActivationView.as_view(), name="lead-resend-activation"),
    path("api/lead-onboarding-package/<int:lead_id>/", LeadOnboardingPackageView.as_view(), name="lead-onboarding-package"),
    path("api/admin-reservation-alerts/", AdminReservationAlertsView.as_view(), name="admin-reservation-alerts"),
    path("api/admin-tenants/", AdminTenantListView.as_view(), name="admin-tenants"),
    path("api/admin-tenants/<int:tenant_id>/lifecycle/", AdminTenantLifecycleView.as_view(), name="admin-tenant-lifecycle"),
    path("api/owner/reservations/", OwnerReservationListView.as_view(), name="owner-reservations"),
    path("api/owner/reservations/export/", OwnerReservationExportView.as_view(), name="owner-reservations-export"),
    path("api/owner/reservations/bulk-reminder/", OwnerReservationBulkReminderView.as_view(), name="owner-reservations-bulk-reminder"),
    path("api/owner/reservations/bulk-reminder-result/", OwnerReservationBulkReminderResultView.as_view(), name="owner-reservations-bulk-reminder-result"),
    path("api/owner/reservations/bulk-status/", OwnerReservationBulkStatusView.as_view(), name="owner-reservations-bulk-status"),
    path("api/owner/reservations/<int:lead_id>/reminder/", OwnerReservationReminderView.as_view(), name="owner-reservation-reminder"),
    path("api/owner/reservations/<int:lead_id>/reminder-result/", OwnerReservationReminderResultView.as_view(), name="owner-reservation-reminder-result"),
    path("api/owner/reservations/<int:lead_id>/timeline/", OwnerReservationTimelineView.as_view(), name="owner-reservation-timeline"),
    path("api/owner/reservations/<int:lead_id>/", OwnerReservationDetailView.as_view(), name="owner-reservation-detail"),
    path("api/tier-upgrade-targets/", TierUpgradeTargetsView.as_view(), name="tier-upgrade-targets"),
    path("api/tier-upgrade-requests/", TierUpgradeRequestListCreateView.as_view(), name="tier-upgrade-requests"),
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
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
