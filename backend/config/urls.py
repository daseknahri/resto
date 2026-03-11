from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from rest_framework import routers

from config.shared_api_urls import shared_api_urlpatterns
from menu.views import (
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
    OwnerDashboardView,
    OwnerReservationDetailView,
    OwnerReservationExportView,
    OwnerReservationBulkReminderView,
    OwnerReservationBulkStatusView,
    OwnerReservationReminderView,
    OwnerReservationReminderResultView,
    OwnerReservationBulkReminderResultView,
    OwnerReservationTimelineView,
    OwnerReservationListView,
    TierUpgradeTargetsView,
    TierUpgradeRequestListCreateView,
)
from tenancy.api import ImageDeleteView, ImageUploadView, ProfileView, TenantMetaView

tenant_router = routers.DefaultRouter()
tenant_router.register(r"categories", CategoryViewSet, basename="category")
tenant_router.register(r"dishes", DishViewSet, basename="dish")
tenant_router.register(r"dish-options", DishOptionViewSet, basename="dish-option")
tenant_router.register(r"tables", TableLinkViewSet, basename="table-link")

urlpatterns = [
    *shared_api_urlpatterns,
    path("api/meta/", TenantMetaView.as_view(), name="tenant-meta"),
    path("api/profile/", ProfileView.as_view(), name="tenant-profile"),
    path("api/uploads/image/", ImageUploadView.as_view(), name="image-upload"),
    path("api/uploads/image-delete/", ImageDeleteView.as_view(), name="image-delete"),
    path("api/order-handoff/", OrderHandoffView.as_view(), name="order-handoff"),
    path("api/checkout-intent/", CheckoutIntentView.as_view(), name="checkout-intent"),
    path("api/analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("api/table-context/<slug:table_slug>/", TableContextView.as_view(), name="table-context"),
    path("api/tables/bulk-generate/", TableBulkGenerateView.as_view(), name="table-bulk-generate"),
    path("api/owner/reservations/", OwnerReservationListView.as_view(), name="owner-reservations"),
    path("api/owner/dashboard/", OwnerDashboardView.as_view(), name="owner-dashboard"),
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
    path("api/", include(tenant_router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
