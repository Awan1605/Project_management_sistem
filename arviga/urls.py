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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('arva.urls')),
    path('accounts/', include('allauth.urls')),
]

# Layani file media dan statis saat mode DEBUG (pengembangan lokal)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
