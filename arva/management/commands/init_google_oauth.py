"""
Script untuk setup Google OAuth SocialApp di database
=====================================================
Jalankan sekali saja untuk mendaftarkan Google OAuth di Django admin.

Credentials diambil dari .env file:
- GOOGLE_OAUTH_CLIENT_ID
- GOOGLE_OAUTH_SECRET

Cara pakai:
    python manage.py init_google_oauth
"""

from django.core.management.base import BaseCommand
import os
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Setup Google OAuth SocialApp di database'

    def handle(self, *args, **kwargs):
        self.stdout.write('\n🔧 Setting up Google OAuth...\n')

        # Cek credentials dari environment variables (.env)
        client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
        secret = os.getenv('GOOGLE_OAUTH_SECRET', '')

        if not client_id or client_id == '':
            self.stderr.write('❌ Error: GOOGLE_OAUTH_CLIENT_ID tidak ada di .env')
            return

        if not secret or secret == '':
            self.stderr.write('❌ Error: GOOGLE_OAUTH_SECRET tidak ada di .env')
            return

        # Cek apakah SocialApp sudah ada
        existing_apps = SocialApp.objects.filter(provider='google')
        if existing_apps.count() > 0:
            self.stdout.write(f'⚠️  Ditemukan {existing_apps.count()} SocialApp Google')
            
            # Jika ada duplicate, hapus semua dan buat baru
            if existing_apps.count() > 1:
                self.stdout.write('⚠️  Multiple SocialApp detected! Menghapus semua dan membuat ulang...')
                existing_apps.delete()
            else:
                # Jika hanya 1, update yang sudah ada
                self.stdout.write('✅ SocialApp sudah ada, mengupdate credentials...')
                app = existing_apps.first()
                app.client_id = client_id
                app.secret = secret
                app.save()
                self.stdout.write('✅ SocialApp Google berhasil diupdate!')
                self.stdout.write(f'   Client ID: {client_id[:20]}...')
                self.stdout.write('\n✅ Setup selesai! Google OAuth sudah siap digunakan.\n')
                return
        
        # Buat SocialApp baru
        app = SocialApp.objects.create(
            provider='google',
            name='Google',
            client_id=client_id,
            secret=secret,
        )

        # Tambahkan site yang benar ke SocialApp
        site = Site.objects.get_current()
        app.sites.add(site)

        self.stdout.write('✅ SocialApp Google berhasil dibuat!')
        self.stdout.write(f'   Linked to Site: {site.domain}')

        # Tampilkan informasi
        self.stdout.write('📋 Informasi:')
        self.stdout.write(f'   Client ID: {client_id[:20]}...')
        self.stdout.write(f'   Sites: {list(Site.objects.all())}')
        self.stdout.write('\n✅ Setup selesai! Google OAuth sudah siap digunakan.\n')
