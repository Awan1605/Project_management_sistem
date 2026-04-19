"""Konfigurasi aplikasi Arva.

Mendaftarkan app 'arva' ke Django dan memastikan
signals dimuat saat aplikasi siap.
"""

from django.apps import AppConfig


class ArvaConfig(AppConfig):
    """Konfigurasi aplikasi Arva (Arviga Project Manager)."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'arva'

    def ready(self):
        """Muat signals saat aplikasi siap."""
        import arva.signals