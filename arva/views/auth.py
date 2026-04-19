"""
Views Autentikasi
=================
Menangani login, logout, dan registrasi user.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login

from ..forms import RegisterForm


def register(request):
    """Halaman registrasi user baru.
    
    Jika user sudah login, redirect ke halaman project list.
    Jika POST, validasi form dan buat user baru, lalu login otomatis.
    """
    if request.user.is_authenticated:
        return redirect('project_list')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('project_list')
    else:
        form = RegisterForm()
    return render(request, 'arva/auth_register.html', {'form': form})


def custom_logout(request):
    """Logout custom yang kompatibel dengan allauth.
    
    Melakukan Django logout dan membersihkan data session allauth.
    """
    from django.contrib.auth import logout
    
    # Lakukan logout Django (bekerja untuk GET dan POST)
    logout(request)
    
    # Bersihkan data session allauth jika ada
    if 'allauth' in request.session:
        del request.session['allauth']
    
    # Redirect ke halaman login
    return redirect('login')
