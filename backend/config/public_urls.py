from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve as static_serve

from config.shared_api_urls import shared_api_urlpatterns

urlpatterns = [
    *shared_api_urlpatterns,
    path(settings.ADMIN_URL_PREFIX, admin.site.urls),
]

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
