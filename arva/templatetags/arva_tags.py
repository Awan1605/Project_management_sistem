"""
Template Tags Arviga Project Manager
======================================
Custom template tags yang tersedia di seluruh template:
- get_settings: Ambil pengaturan website global
- get_ai_settings: Ambil pengaturan AI
- effective_theme: Hitung tema efektif (user vs website)
- effective_layout: Hitung layout efektif user
- cache_bust: Tambah parameter cache-busting pada URL file statis
- get_item: Ambil item dari dict dengan key
"""

from django import template
from arva.models import WebsiteSettings, AISettings
import os
from datetime import datetime

register = template.Library()


@register.simple_tag
def get_settings():
    """Ambil pengaturan website global dari database."""
    return WebsiteSettings.objects.first()

@register.simple_tag
def get_ai_settings():
    """Ambil pengaturan AI yang sedang aktif dari database."""
    return AISettings.get_current()

@register.simple_tag
def effective_theme(user, settings):
    """Hitung tema efektif untuk user.
    
    Jika user punya preferensi tema sendiri (light/dark/auto), gunakan itu.
    Jika 'inherit' atau belum login, gunakan tema dari pengaturan website.
    """
    if user.is_authenticated:
        pref = getattr(user, "userprofile", None)
        if pref:
            pref = user.userprofile.theme_preference
            if pref in ["light", "dark", "auto"]:
                return pref

    return settings.theme_mode

@register.simple_tag
def effective_layout(user):
    """Hitung layout efektif untuk user.
    
    Default: sidebar. User bisa memilih sidebar atau classic.
    """
    if user.is_authenticated:
        profile = getattr(user, "userprofile", None)
        if profile and profile.layout_preference in ["sidebar", "classic"]:
            return profile.layout_preference
    return "sidebar"

@register.simple_tag
def cache_bust(file_path):
    """Tambah parameter cache-busting berdasarkan waktu modifikasi file.
    
    Menghasilkan ?v=YYYYMMDDHHMM agar browser selalu
    mengambil versi terbaru file statis setelah perubahan.
    """
    try:
        from django.conf import settings as django_settings
        full_path = os.path.join(django_settings.BASE_DIR, file_path.replace('{% static \'', '').replace('\' %}', '').replace('static/', ''))
        if os.path.exists(full_path):
            mtime = os.path.getmtime(full_path)
            timestamp = datetime.fromtimestamp(mtime).strftime('%Y%m%d%H%M')
            return f'?v={timestamp}'
    except:
        pass
    return ''

@register.filter
def get_item(mapping, key):
    """Ambil item dari dictionary berdasarkan key."""
    if mapping is None:
        return None
    return mapping.get(key)
