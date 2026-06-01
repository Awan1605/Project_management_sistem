"""
Template Tags Arviga Project Manager
======================================
Custom template tags yang tersedia di seluruh template:
- get_settings
- get_ai_settings
- effective_theme
- effective_layout
- cache_bust
- get_item
"""

import os
import re
from datetime import datetime

from django import template
from django.contrib.auth.models import User
from django.utils.html import escape
from django.utils.safestring import mark_safe

from arva.models import WebsiteSettings, AISettings, UserNotification
from ..forms import sanitize_rich_text_html

register = template.Library()


# ============================================================
# SETTINGS
# ============================================================

@register.simple_tag
def get_settings():
    """Ambil pengaturan website global."""
    return WebsiteSettings.objects.first()


@register.simple_tag
def get_ai_settings():
    """Ambil pengaturan AI aktif."""
    try:
        return AISettings.get_current()
    except:
        return None


# ============================================================
# THEME & LAYOUT
# ============================================================

@register.simple_tag
def effective_theme(user, settings):
    """Hitung tema efektif."""

    # User custom preference
    if getattr(user, "is_authenticated", False):

        profile = getattr(user, "userprofile", None)

        if profile:
            pref = getattr(profile, "theme_preference", None)

            if pref in ["light", "dark", "auto"]:
                return pref

    # Website default theme
    if settings and getattr(settings, "theme_mode", None):
        return settings.theme_mode

    # Fallback
    return "light"


@register.simple_tag
def effective_layout(user):
    """Hitung layout efektif."""

    if getattr(user, "is_authenticated", False):

        profile = getattr(user, "userprofile", None)

        if profile:
            layout = getattr(profile, "layout_preference", None)

            if layout in ["sidebar", "classic"]:
                return layout

    return "sidebar"


# ============================================================
# STATIC CACHE
# ============================================================

@register.simple_tag
def cache_bust(file_path):
    """Tambah cache busting."""

    try:
        from django.conf import settings as django_settings

        cleaned = (
            file_path
            .replace("{% static '", "")
            .replace("' %}", "")
            .replace("static/", "")
        )

        full_path = os.path.join(
            django_settings.BASE_DIR,
            cleaned
        )

        if os.path.exists(full_path):

            mtime = os.path.getmtime(full_path)

            version = datetime.fromtimestamp(
                mtime
            ).strftime("%Y%m%d%H%M")

            return f"?v={version}"

    except:
        pass

    return ""


# ============================================================
# FILTERS
# ============================================================

@register.filter
def get_item(mapping, key):
    """Ambil item dict berdasarkan key."""

    if mapping is None:
        return None

    return mapping.get(key)


# ============================================================
# NOTIFICATIONS
# ============================================================

@register.simple_tag
def recent_notifications(user, limit=8):
    """Notifikasi terbaru."""

    if not getattr(user, "is_authenticated", False):
        return []

    return (
        UserNotification.objects
        .filter(
            recipient=user,
            is_read=False
        )
        .select_related(
            "actor",
            "task",
            "comment"
        )[:limit]
    )


@register.simple_tag
def unread_notification_count(user):
    """Jumlah notifikasi belum dibaca."""

    if not getattr(user, "is_authenticated", False):
        return 0

    return UserNotification.objects.filter(
        recipient=user,
        is_read=False
    ).count()


# ============================================================
# MENTION & URL
# ============================================================

MENTION_RE = re.compile(
    r'(^|\s)@([A-Za-z0-9_.+-]{2,150})'
)

URL_RE = re.compile(
    r'(?P<url>(?:https?://|www\.)[^\s<]+)',
    re.IGNORECASE
)


@register.filter
def mentionize(value):
    """Render mention username."""

    text = value or ""

    escaped = escape(text)

    usernames = {
        m.group(2)
        for m in MENTION_RE.finditer(text)
    }

    existing = set(
        User.objects.filter(
            username__in=usernames
        ).values_list(
            "username",
            flat=True
        )
    ) if usernames else set()

    def _replace(match):

        prefix = match.group(1) or ""
        username = match.group(2)

        if username in existing:
            return (
                f'{prefix}'
                f'<a href="/users/?q={username}" '
                f'class="comment-mention">'
                f'@{username}</a>'
            )

        return f"{prefix}@{username}"

    rendered = MENTION_RE.sub(
        _replace,
        escaped
    )

    def _url_replace(match):

        url = (match.group("url") or "").strip()

        href = (
            url
            if url.lower().startswith(
                ("http://", "https://")
            )
            else f"https://{url}"
        )

        return (
            f'<a href="{href}" '
            f'target="_blank" '
            f'rel="noopener noreferrer nofollow">'
            f'{url}</a>'
        )

    rendered = URL_RE.sub(
        _url_replace,
        rendered
    ).replace("\n", "<br>")

    return mark_safe(rendered)


# ============================================================
# RICH TEXT
# ============================================================

@register.filter
def safe_richtext(value):
    """Sanitize rich text."""

    return mark_safe(
        sanitize_rich_text_html(value or "")
    )