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

import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from ..forms import sanitize_rich_text_html
from arva.models import WebsiteSettings, AISettings, UserNotification
from django.contrib.auth.models import User
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


@register.simple_tag
def recent_notifications(user, limit=8):
    """Ambil notifikasi terbaru untuk user di topbar bell."""
    if not getattr(user, 'is_authenticated', False):
        return []
    return UserNotification.objects.filter(recipient=user, is_read=False).select_related('actor', 'task', 'comment')[:limit]


@register.simple_tag
def unread_notification_count(user):
    """Jumlah notifikasi belum dibaca."""
    if not getattr(user, 'is_authenticated', False):
        return 0
    return UserNotification.objects.filter(recipient=user, is_read=False).count()


MENTION_RE = re.compile(r'(^|\s)@([A-Za-z0-9_.+-]{2,150})')
URL_RE = re.compile(r'(?P<url>(?:https?://|www\.)[^\s<]+)', re.IGNORECASE)


@register.filter
def mentionize(value):
    """Render @username sebagai chip/link mention yang aman."""
    text = value or ''
    escaped = escape(text)
    usernames = {m.group(2) for m in MENTION_RE.finditer(text)}
    existing = set(User.objects.filter(username__in=usernames).values_list('username', flat=True)) if usernames else set()

    def _replace(match):
        prefix = match.group(1) or ''
        username = match.group(2)
        if username in existing:
            return f'{prefix}<a href="/users/?q={username}" class="comment-mention">@{username}</a>'
        return f'{prefix}@{username}'

    rendered = MENTION_RE.sub(_replace, escaped)

    def _url_replace(match):
        url = (match.group('url') or '').strip()
        href = url if url.lower().startswith(('http://', 'https://')) else f'https://{url}'
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer nofollow">{url}</a>'

    rendered = URL_RE.sub(_url_replace, rendered).replace('\n', '<br>')
    return mark_safe(rendered)


@register.filter
def safe_richtext(value):
    return mark_safe(sanitize_rich_text_html(value or ''))
