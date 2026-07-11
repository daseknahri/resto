from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve as static_serve

from accounts.views import EmailUnsubscribeView
from config.shared_api_urls import build_v1_urlpatterns, shared_api_urlpatterns
from config.sitemap import sitemap_view

urlpatterns = [
    *shared_api_urlpatterns,
    # B1-followup: public one-click email-unsubscribe (CAN-SPAM / Gmail-Yahoo
    # bulk-sender compliance). Customer-facing + platform-level, so it lives on
    # the PUBLIC urlconf. The recipient is encoded in a signed token — no auth.
    path("api/unsubscribe/<str:token>/", EmailUnsubscribeView.as_view(), name="email-unsubscribe"),
    # Public SEO sitemap (public-schema host only). Lists the static SPA pages
    # plus one /order/<slug> per discoverable tenant. See config/sitemap.py.
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path(settings.ADMIN_URL_PREFIX, admin.site.urls),
]

# RISK API-1: additive /api/v1/ alias — same views as the api/ routes above,
# derived generically (not hand-duplicated). See build_v1_urlpatterns().
urlpatterns += build_v1_urlpatterns(urlpatterns)

# OPS-5d B: only register a Django /media handler in DEBUG (dev) or when an
# operator explicitly opts in via SERVE_MEDIA_FROM_DJANGO.  In a normal prod
# deploy nginx (frontend/nginx.conf) owns /media end to end, so the insecure
# django.views.static.serve route is never registered.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "SERVE_MEDIA_FROM_DJANGO", False):
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
