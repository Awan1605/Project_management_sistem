"""
Signals Arviga Project Manager
================================
Django signals yang otomatis dijalankan saat event tertentu:
- clear_ai_chat_on_logout: Hapus riwayat chat AI saat user logout
- create_profile: Buat UserProfile saat user baru dibuat
- fetch_google_avatar: Ambil foto profil Google saat login via Google
- send_welcome_email_on_google_signup: Kirim email selamat datang
"""

import requests, threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_out
from .models import UserProfile, AIChatMessage
from allauth.socialaccount.models import SocialAccount
from django.core.files.base import ContentFile
from allauth.account.signals import user_signed_up
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .utils import EmailThread


@receiver(user_logged_out)
def clear_ai_chat_on_logout(sender, request, user, **kwargs):
    """Hapus riwayat chat AI saat user logout (menjaga privasi)."""
    if user:
        AIChatMessage.objects.filter(user=user).delete()

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Buat UserProfile secara otomatis saat user baru dibuat."""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=SocialAccount)
def fetch_google_avatar(sender, instance, created, **kwargs):
    """Ambil foto profil dari Google dan simpan sebagai avatar user.
    
    Dijalankan saat SocialAccount (akun Google) baru dibuat.
    Foto profil diambil dari extra_data Google dan disimpan ke file lokal.
    """
    if not created:
        return

    user = instance.user
    profile = user.userprofile

    picture_url = instance.extra_data.get("picture")
    if picture_url:
        try:
            response = requests.get(picture_url)
            profile.avatar.save(
                f"google_{user.id}.jpg",
                ContentFile(response.content),
                save=True
            )
        except Exception as e:
            print("Gagal mengambil avatar Google:", e)

@receiver(user_signed_up)
def send_welcome_email_on_google_signup(request, user, **kwargs):
    """Kirim email selamat datang saat user mendaftar via Google.
    
    Menggunakan template email welcome_google.html.
    Pengiriman email dilakukan di thread terpisah agar tidak blocking.
    """
    try:
        dashboard_url = f"https://{request.get_host()}"
        context = {
            "username": user.username,
            "dashboard_url": dashboard_url,
            "year": 2025,
        }

        html_message = render_to_string("email/welcome_google.html", context)
        plain_message = strip_tags(html_message)

        EmailThread(
            subject="Welcome to Arva!",
            message=plain_message,
            html_message=html_message,
            from_email=None,
            recipient_list=[user.email],
        ).start()

    except Exception as e:
        print("Error pengiriman email:", e)