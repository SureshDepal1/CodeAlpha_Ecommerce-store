"""URL configuration for the Simple E-commerce Store project."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
]

handler404 = "store.views.custom_404"
handler500 = "store.views.custom_500"

if settings.SERVE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
