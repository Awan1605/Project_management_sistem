from django import template
from arva.models import WebsiteSettings

register = template.Library()

@register.simple_tag
def get_settings():
    return WebsiteSettings.objects.first()

@register.simple_tag
def effective_theme(user, settings):
    if user.is_authenticated:
        pref = getattr(user, "userprofile", None)
        if pref:
            pref = user.userprofile.theme_preference
            if pref in ["light", "dark", "auto"]:
                return pref

    return settings.theme_mode

@register.simple_tag
def effective_layout(user):
    if user.is_authenticated:
        profile = getattr(user, "userprofile", None)
        if profile and profile.layout_preference in ["sidebar", "classic"]:
            return profile.layout_preference
    return "sidebar"

@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    return mapping.get(key)
