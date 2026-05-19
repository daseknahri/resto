from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from rest_framework import routers

from accounts.views import (
    OwnerDeliveryRadiusUpdateView,
    OwnerDeliveryZoneView,
    OwnerFlashSaleListView,
    OwnerFlashSaleOptInView,
    OwnerStaffDeleteView,
    OwnerStaffListCreateView,
)
from config.shared_api_urls import shared_api_urlpatterns
from menu.views import (
    AnalyticsSummaryView,
    CategoryViewSet,
    CheckoutIntentView,
    CustomerOrderRateView,
    CustomerOrdersByPhoneView,
    CustomerOrderStatusView,
    DishBulkAvailabilityResetView,
    DishOptionViewSet,
    DishViewSet,
    OptionGroupViewSet,
    OrderHandoffView,
    OwnerAnalyticsExportView,
    OwnerClosureDateDeleteView,
    OwnerClosureDateListCreateView,
    OwnerCommissionStatementView,
    OwnerDataExportView,
    OwnerInvoiceView,
    OwnerCustomerRatingView,
    OwnerPromotionDetailView,
    OwnerPromotionListCreateView,
    OwnerOrderDetailView,
    OwnerOrderExportView,
    OwnerOrderListView,
    OwnerOrderStatusUpdateView,
    OwnerRatingListView,
    OwnerCustomerListView,
    OwnerRevenueChartView,
    OwnerPushSubscribeView,
    OwnerPushVapidKeyView,
    OwnerWaitlistView,
    PlaceOrderView,
    SlotAvailabilityView,
    StaffOrderListView,
    StaffShiftSummaryView,
    SuperCategoryViewSet,
    TableBulkGenerateView,
    TableContextView,
    TableLinkViewSet,
    WaitlistJoinView,
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
from tenancy.api import AppManifestView, ImageDeleteView, ImageUploadView, OwnerDeletionRequestView, ProfileView, TenantMetaView, TranslateView

tenant_router = routers.DefaultRouter()
tenant_router.register(r"super-categories", SuperCategoryViewSet, basename="super-category")
tenant_router.register(r"categories", CategoryViewSet, basename="category")
tenant_router.register(r"dishes", DishViewSet, basename="dish")
tenant_router.register(r"dish-options", DishOptionViewSet, basename="dish-option")
tenant_router.register(r"option-groups", OptionGroupViewSet, basename="option-group")
tenant_router.register(r"tables", TableLinkViewSet, basename="table-link")

urlpatterns = [
    *shared_api_urlpatterns,
    path("api/meta/", TenantMetaView.as_view(), name="tenant-meta"),
    path("app-manifest.json", AppManifestView.as_view(), name="app-manifest"),
    path("api/profile/", ProfileView.as_view(), name="tenant-profile"),
    path("api/uploads/image/", ImageUploadView.as_view(), name="image-upload"),
    path("api/uploads/image-delete/", ImageDeleteView.as_view(), name="image-delete"),
    path("api/translate/", TranslateView.as_view(), name="translate"),
    path("api/order-handoff/", OrderHandoffView.as_view(), name="order-handoff"),
    path("api/checkout-intent/", CheckoutIntentView.as_view(), name="checkout-intent"),
    path("api/place-order/", PlaceOrderView.as_view(), name="place-order"),
    path("api/order-status/<str:order_number>/", CustomerOrderStatusView.as_view(), name="order-status"),
    path("api/orders/by-phone/", CustomerOrdersByPhoneView.as_view(), name="orders-by-phone"),
    path("api/orders/<str:order_number>/rate/", CustomerOrderRateView.as_view(), name="order-rate"),
    path("api/owner/ratings/", OwnerRatingListView.as_view(), name="owner-ratings"),
    path("api/owner/closure-dates/", OwnerClosureDateListCreateView.as_view(), name="owner-closure-dates"),
    path("api/owner/closure-dates/<int:closure_id>/", OwnerClosureDateDeleteView.as_view(), name="owner-closure-date-delete"),
    path("api/staff/orders/", StaffOrderListView.as_view(), name="staff-orders"),
    path("api/staff/shift-summary/", StaffShiftSummaryView.as_view(), name="staff-shift-summary"),
    path("api/owner/orders/", OwnerOrderListView.as_view(), name="owner-orders"),
    path("api/owner/orders/export/", OwnerOrderExportView.as_view(), name="owner-orders-export"),
    path("api/owner/orders/<int:order_id>/", OwnerOrderDetailView.as_view(), name="owner-order-detail"),
    path("api/owner/orders/<int:order_id>/status/", OwnerOrderStatusUpdateView.as_view(), name="owner-order-status"),
    path("api/owner/orders/<int:order_id>/customer-rating/", OwnerCustomerRatingView.as_view(), name="owner-order-customer-rating"),
    path("api/owner/promotions/", OwnerPromotionListCreateView.as_view(), name="owner-promotions"),
    path("api/owner/promotions/<int:promo_id>/", OwnerPromotionDetailView.as_view(), name="owner-promotion-detail"),
    path("api/owner/dishes/reset-availability/", DishBulkAvailabilityResetView.as_view(), name="owner-dishes-reset-availability"),
    path("api/analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("api/owner/analytics/export/", OwnerAnalyticsExportView.as_view(), name="owner-analytics-export"),
    path("api/owner/data-export/", OwnerDataExportView.as_view(), name="owner-data-export"),
    path("api/owner/invoice/", OwnerInvoiceView.as_view(), name="owner-invoice"),
    path("api/owner/commission-statement/", OwnerCommissionStatementView.as_view(), name="owner-commission-statement"),
    path("api/owner/deletion-request/", OwnerDeletionRequestView.as_view(), name="owner-deletion-request"),
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
    path("api/availability/", SlotAvailabilityView.as_view(), name="slot-availability"),
    path("api/waitlist/", WaitlistJoinView.as_view(), name="waitlist-join"),
    path("api/owner/waitlist/", OwnerWaitlistView.as_view(), name="owner-waitlist"),
    path("api/tier-upgrade-targets/", TierUpgradeTargetsView.as_view(), name="tier-upgrade-targets"),
    path("api/tier-upgrade-requests/", TierUpgradeRequestListCreateView.as_view(), name="tier-upgrade-requests"),
    path("api/owner/staff/", OwnerStaffListCreateView.as_view(), name="owner-staff-list"),
    path("api/owner/staff/<int:staff_id>/", OwnerStaffDeleteView.as_view(), name="owner-staff-delete"),
    path("api/owner/flash-sales/", OwnerFlashSaleListView.as_view(), name="owner-flash-sales"),
    path("api/owner/flash-sales/<int:fs_id>/opt-in/", OwnerFlashSaleOptInView.as_view(), name="owner-flash-sale-opt-in"),
    path("api/owner/delivery-zone/", OwnerDeliveryZoneView.as_view(), name="owner-delivery-zone"),
    path("api/owner/delivery-radius/", OwnerDeliveryRadiusUpdateView.as_view(), name="owner-delivery-radius"),
    path("api/owner/push-vapid-key/", OwnerPushVapidKeyView.as_view(), name="owner-push-vapid-key"),
    path("api/owner/push-subscribe/", OwnerPushSubscribeView.as_view(), name="owner-push-subscribe"),
    path("api/owner/customers/", OwnerCustomerListView.as_view(), name="owner-customers"),
    path("api/owner/revenue-chart/", OwnerRevenueChartView.as_view(), name="owner-revenue-chart"),
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
