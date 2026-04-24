"""
Views User Approval
====================
Menangani approval/verifikasi user yang mendaftar via Google OAuth.
Hanya admin/superuser yang bisa akses.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Q
from ..models import UserProfile
from .helpers import is_admin


@login_required
@user_passes_test(is_admin)
def pending_users(request):
    """Halaman list user yang menunggu approval.
    
    Hanya bisa diakses oleh admin/superuser.
    Menampilkan semua user dengan pending_approval=True.
    """
    pending_users = User.objects.filter(
        userprofile__pending_approval=True,
        userprofile__is_verified=False
    ).select_related('userprofile').order_by('-date_joined')
    
    return render(request, 'arva/pending_users.html', {
        'pending_users': pending_users,
    })


@login_required
@user_passes_test(is_admin)
def approve_user(request, user_id):
    """Approve user yang pending.
    
    Admin bisa approve user, set is_verified=True dan pending_approval=False.
    Kirim email notifikasi ke user yang di-approve.
    """
    user = get_object_or_404(User, id=user_id)
    profile = user.userprofile
    
    if not profile.pending_approval:
        messages.warning(request, f'User {user.username} sudah diverifikasi sebelumnya.')
        return redirect('pending_users')
    
    # Update status
    profile.is_verified = True
    profile.pending_approval = False
    profile.save()
    
    # Kirim email notifikasi
    try:
        subject = 'Akun Anda Telah Diverifikasi - Arviga Project Manager'
        
        context = {
            'username': user.username,
            'login_url': f"https://task.arviga.co.id/login/",
            'site_name': 'Arviga Project Manager',
        }
        
        html_message = render_to_string('email/user_approved.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=None,  # Use default from settings
            recipient_list=[user.email],
            fail_silently=True,
        )
        
        messages.success(request, f'✅ User {user.username} berhasil diverifikasi! Email notifikasi telah dikirim.')
    except Exception as e:
        messages.success(request, f'✅ User {user.username} berhasil diverifikasi! (Email gagal dikirim: {str(e)})')
    
    return redirect('pending_users')


@login_required
@user_passes_test(is_admin)
def reject_user(request, user_id):
    """Reject user yang pending.
    
    Admin bisa reject user, user akan dihapus dari database.
    """
    user = get_object_or_404(User, id=user_id)
    
    if not user.userprofile.pending_approval:
        messages.warning(request, f'User {user.username} sudah diverifikasi sebelumnya.')
        return redirect('pending_users')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        # Hapus user
        username = user.username
        user_email = user.email
        user.delete()
        
        messages.success(request, f'❌ User {username} berhasil dihapus.')
    
    return redirect('pending_users')
