"""
Custom Allauth Adapter
=======================
Adapter custom untuk menangani:
- Verifikasi user Google OAuth oleh admin
- Email notification saat user diverifikasi
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import render
from django.contrib import messages
from .models import UserProfile


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter untuk handle Google OAuth verification."""
    
    def pre_social_login(self, request, sociallogin):
        """Dipanggil sebelum user login/signup via social account.
        
        Cek apakah user sudah ada dan belum verified.
        Jika user baru signup via Google, set pending_approval.
        """
        user = sociallogin.user
        
        # Jika user sudah ada di database
        if user.pk:
            try:
                profile = user.userprofile
                # Jika user belum verified, block login
                if not profile.is_verified:
                    raise ImmediateHttpResponse(
                        render(request, 'arva/auth_pending_approval.html', {
                            'email': user.email,
                        })
                    )
            except UserProfile.DoesNotExist:
                pass
        
        # Jika user baru (akan dibuat), set flag untuk signal
        if not user.pk:
            # Tandai bahwa ini adalah signup baru
            request.session['pending_google_signup'] = True
