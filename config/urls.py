"""URL configuration for the arch-olympiad platform."""

from django.contrib import admin
from django.urls import include, path

from problems.views import healthz

urlpatterns = [
    # sonde de santé des hébergeurs : jamais redirigée, jamais authentifiée
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("problems.urls")),
]
