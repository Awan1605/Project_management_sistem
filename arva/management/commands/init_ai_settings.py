"""Management command untuk inisialisasi pengaturan AI default.

Menjalankan: python manage.py init_ai_settings

Membuat AISettings default jika belum ada di database.
Mengambil GEMINI_API_KEY dari settings.py jika tersedia.
Jika tidak ada, membuat pengaturan kosong yang bisa dikonfigurasi via admin panel.
"""

from django.core.management.base import BaseCommand
from arva.models import AISettings
from django.conf import settings as django_settings


class Command(BaseCommand):
    """Command untuk inisialisasi pengaturan AI default."""
    help = 'Inisialisasi pengaturan AI default dari settings.py'

    def handle(self, *args, **kwargs):
        self.stdout.write('Menginisialisasi pengaturan AI...')
        
        # Cek apakah pengaturan sudah ada
        if AISettings.objects.exists():
            self.stdout.write(self.style.WARNING('Pengaturan AI sudah ada. Melewati inisialisasi.'))
            return
        
        # Buat pengaturan default
        gemini_api_key = getattr(django_settings, 'GEMINI_API_KEY', '')
        
        if not gemini_api_key:
            self.stdout.write(self.style.ERROR('GEMINI_API_KEY tidak ditemukan di settings.py'))
            self.stdout.write(self.style.WARNING('Membuat pengaturan AI kosong. Silakan konfigurasi via admin panel.'))
        
        AISettings.objects.create(
            provider=AISettings.PROVIDER_GOOGLE,
            api_key=gemini_api_key,
            model_name='gemini-2.5-flash',
            temperature=0.7,
            max_tokens=2048,
            ai_priority_enabled=True,
            ai_chat_enabled=True,
        )
        
        self.stdout.write(self.style.SUCCESS('Berhasil membuat pengaturan AI default!'))
        self.stdout.write(self.style.SUCCESS('Konfigurasi AI tersedia di Admin Panel: /admin/arva/aisettings/'))
