from django.utils.timezone import now
from .models import UserActivity
from django.shortcuts import render

class LastActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            UserActivity.objects.update_or_create(
                user=request.user,
                defaults={'last_activity': now()}
            )

        return self.get_response(request)

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from arva.models import WebsiteSettings

        settings = WebsiteSettings.objects.first()
        if settings and settings.maintenance_mode and not request.user.is_superuser:
            return render(request, "arva/maintenance.html")

        return self.get_response(request)
