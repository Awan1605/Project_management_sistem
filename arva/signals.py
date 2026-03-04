import requests, threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.models import User
from .models import UserProfile
from allauth.socialaccount.models import SocialAccount
from django.core.files.base import ContentFile
from allauth.account.signals import user_signed_up
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .utils import EmailThread

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=SocialAccount)
def fetch_google_avatar(sender, instance, created, **kwargs):
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
            print("Failed to fetch google avatar:", e)

@receiver(user_signed_up)
def send_welcome_email_on_google_signup(request, user, **kwargs):
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
        print("Email sending error:", e)
        
# @receiver(user_signed_up)
# def send_welcome_email_on_google_signup(request, user, **kwargs):
#     print("Register via google:", user.username)
#     subject = "Welcome to Arva!"
#     message = f"""
#         Hi {user.username},

#         Your account has been successfully created using Google login.

#         Welcome to Arviga Project Management System!

#         You can now start organizing your projects and tasks.
#         If you need help, just contact our support.

#         Regards,
#         Arviga Team
#     """
#     send_mail(
#         subject,
#         message,
#         None,
#         [user.email],
#         fail_silently=True,
#     )