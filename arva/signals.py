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
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_out
from .models import UserProfile, AIChatMessage, Attachment
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
    User juga di-set sebagai pending approval.
    """
    if not created:
        return

    user = instance.user
    profile = user.userprofile

    # Set user sebagai pending approval (perlu verifikasi admin)
    profile.is_verified = False
    profile.pending_approval = True
    profile.save()

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


# ============================================================
# RAG AUTO-SYNC SIGNALS
# ============================================================

def get_rag_kb():
    """Get RAG Knowledge Base instance (lazy load)"""
    try:
        from .rag_knowledge import get_rag_knowledge_base
        return get_rag_knowledge_base()
    except Exception:
        return None


@receiver(post_save, sender='arva.Project')
def sync_project_to_rag(sender, instance, created, **kwargs):
    """Auto-sync project ke RAG Knowledge Base saat dibuat atau diupdate (async)."""
    try:
        def async_sync():
            try:
                rag_kb = get_rag_kb()
                if rag_kb:
                    rag_kb.add_project(instance)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[RAG Signal] Error syncing project async: {e}")
        
        # Run in background thread to not block the request
        thread = threading.Thread(target=async_sync)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[RAG Signal] Error starting async sync: {e}")


@receiver(post_save, sender='arva.Task')
def sync_task_to_rag(sender, instance, created, **kwargs):
    """Auto-sync task ke RAG Knowledge Base saat dibuat atau diupdate (async)."""
    try:
        def async_sync():
            try:
                rag_kb = get_rag_kb()
                if rag_kb:
                    rag_kb.add_task(instance)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[RAG Signal] Error syncing task async: {e}")
        
        # Run in background thread to not block the request
        thread = threading.Thread(target=async_sync)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[RAG Signal] Error starting async sync: {e}")


@receiver(post_delete, sender='arva.Project')
def remove_project_from_rag(sender, instance, **kwargs):
    """Remove project dari RAG saat dihapus."""
    try:
        rag_kb = get_rag_kb()
        if rag_kb:
            rag_kb.remove_document(f"project_{instance.id}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[RAG Signal] Error removing project: {e}")


@receiver(post_delete, sender='arva.Task')
def remove_task_from_rag(sender, instance, **kwargs):
    """Remove task dari RAG saat dihapus."""
    try:
        rag_kb = get_rag_kb()
        if rag_kb:
            rag_kb.remove_document(f"task_{instance.id}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[RAG Signal] Error removing task: {e}")


@receiver(post_save, sender='arva.Attachment')
def extract_attachment_content(sender, instance, created, **kwargs):
    """Auto-extract text content dari attachment saat di-upload dan update RAG."""
    if not created:
        return  # Hanya proses saat attachment baru dibuat
    
    try:
        import threading
        from .document_extractor import get_file_summary
        from django.conf import settings
        
        def async_extract():
            try:
                # Dapatkan full path file
                file_path = instance.file.path
                
                # Extract text content
                content_summary = get_file_summary(file_path, max_length=2000)
                
                # Log success
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[Attachment] Extracted {len(content_summary)} chars from {instance.file.name}")
                
                # Update RAG untuk task terkait
                rag_kb = get_rag_kb()
                if rag_kb and instance.task:
                    # Re-sync task ke RAG (akan include attachment content)
                    rag_kb.add_task(instance.task)
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[Attachment Signal] Error extracting content: {e}")
        
        # Run in background thread
        thread = threading.Thread(target=async_extract)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[Attachment Signal] Error starting extraction: {e}")
