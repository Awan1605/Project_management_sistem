from datetime import timedelta
from django.core.cache import cache
from django.utils.timezone import now
from .models import UserActivity
from django.shortcuts import render

class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_ts = int(now().timestamp())
            last_ts = request.session.get("last_activity_ts")
            if not last_ts or (current_ts - last_ts) >= 60:
                UserActivity.objects.update_or_create(
                    user=request.user,
                    defaults={'last_activity': now()}
                )
                request.session["last_activity_ts"] = current_ts

        return self.get_response(request)

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from arva.models import WebsiteSettings

        settings = cache.get("website_settings")
        if settings is None:
            settings = WebsiteSettings.objects.first()
            cache.set("website_settings", settings, 30)
        if settings and settings.maintenance_mode and not request.user.is_superuser:
            return render(request, "arva/maintenance.html")

        return self.get_response(request)
