"""
Utilitas Arviga Project Manager
================================
Fungsi-fungsi pembantu yang dipakai di berbagai modul:
- is_user_online: Cek apakah user sedang online
- EmailThread: Kirim email di thread terpisah (non-blocking)
- get_date: Konversi datetime/date ke date untuk perbandingan aman
"""

from datetime import timedelta, date
from django.utils.timezone import now
from threading import Thread
from django.core.mail import send_mail


def get_date(d):
    """Konversi datetime atau date ke date untuk perbandingan yang aman.
    
    Fungsi ini menangani perbedaan tipe antara datetime.datetime dan datetime.date
    yang sering menyebabkan error: '<' not supported between instances.
    
    Args:
        d: datetime.datetime, datetime.date, atau None
        
    Returns:
        datetime.date atau None jika input None
    """
    if d is None:
        return None
    if hasattr(d, 'date'):
        return d.date()
    return d


def is_user_online(last_activity):
    """Cek apakah user sedang online berdasarkan aktivitas terakhir.
    
    User dianggap online jika aktivitas terakhir dalam 1 menit terakhir.
    
    Args:
        last_activity: DateTime aktivitas terakhir user
        
    Returns:
        bool: True jika user online, False jika tidak
    """
    if not last_activity:
        return False
    return (now() - last_activity) < timedelta(minutes=1)


class EmailThread(Thread):
    """Thread untuk mengirim email secara asynchronous (non-blocking).
    
    Menggunakan Django's send_mail() di thread terpisah
    agar pengiriman email tidak memblokir request utama.
    
    Usage:
        EmailThread(
            subject="Judul",
            message="Isi plain text",
            html_message="<h1>Isi HTML</h1>",
            from_email=None,  # Gunakan DEFAULT_FROM_EMAIL
            recipient_list=["user@example.com"],
        ).start()
    """
    def __init__(self, subject, message, html_message, from_email, recipient_list):
        self.subject = subject
        self.message = message
        self.html_message = html_message
        self.from_email = from_email
        self.recipient_list = recipient_list
        Thread.__init__(self)

    def run(self):
        """Kirim email di background thread."""
        send_mail(
            subject=self.subject,
            message=self.message,
            html_message=self.html_message,
            from_email=self.from_email,
            recipient_list=self.recipient_list,
            fail_silently=True,
        )
