"""
URL Configuration Utama Arviga Project Manager
=================================================
Mendefinisikan routing URL tingkat atas:
- /admin/ -> Django Admin
- / -> Aplikasi Arva (semua URL di arva/urls.py)
- /accounts/ -> Django Allauth (login/signup via Google, dll)

Juga melayani file media dan statis saat mode DEBUG.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('arva.urls')),
    path('accounts/login/', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('accounts/', include('allauth.urls')),
]

handler403 = 'arva.views.helpers.custom_permission_denied_view'

# Layani file media dan statis saat mode DEBUG (pengembangan lokal)
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
