from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from config.api import health_view

urlpatterns = [
    path("api/health/", health_view, name="public-health"),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
