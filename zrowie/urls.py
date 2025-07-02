# zrowie/urls.py
from django.contrib import admin
from django.urls import path, include
from django_otp.admin import OTPAdminSite

# Zastąp domyślny admin site przez OTPAdminSite (wymaga 2FA)
admin.site.__class__ = OTPAdminSite

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pacjenci/', include('patients.urls')),
    path('', include('users.urls')),
    path("__reload__/", include("django_browser_reload.urls")),
]