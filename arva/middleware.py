"""
Middleware Arviga Project Manager
====================================
Dua middleware utama:
- LastActivityMiddleware: Tracking aktivitas terakhir user (untuk status online)
- MaintenanceModeMiddleware: Mode maintenance website (hanya superuser bisa akses)
"""

from datetime import timedelta
from django.core.cache import cache
from django.utils.timezone import now
from .models import UserActivity
from django.shortcuts import render


class LastActivityMiddleware:
    """Middleware yang mencatat aktivitas terakhir user.
    
    Update timestamp UserActivity minimal setiap 60 detik.
    Digunakan untuk menampilkan status online di sidebar.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_ts = int(now().timestamp())
            last_ts = request.session.get("last_activity_ts")
            # Update minimal setiap 60 detik (hindari query berlebihan)
            if not last_ts or (current_ts - last_ts) >= 60:
                UserActivity.objects.update_or_create(
                    user=request.user,
                    defaults={'last_activity': now()}
                )
                request.session["last_activity_ts"] = current_ts

        return self.get_response(request)


class MaintenanceModeMiddleware:
    """Middleware yang menampilkan halaman maintenance.
    
    Jika maintenance_mode aktif di WebsiteSettings, semua user
    kecuali superuser akan diarahkan ke halaman maintenance.
    Pengaturan di-cache selama 30 detik untuk performa.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from arva.models import WebsiteSettings

        # Cache pengaturan website selama 30 detik
        settings = cache.get("website_settings")
        if settings is None:
            settings = WebsiteSettings.objects.first()
            cache.set("website_settings", settings, 30)
        
        # Tampilkan halaman maintenance jika aktif dan bukan superuser
        if settings and settings.maintenance_mode and not request.user.is_superuser:
            return render(request, "arva/maintenance.html")

        return self.get_response(request)
