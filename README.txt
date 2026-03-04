Arva - Trello Pro Final Version
===============================

Fitur utama:
- Django + MySQL
- Trello-like board (lists & cards) dengan drag & drop (jQuery UI)
- Role per project: Admin, Member, Viewer (Owner selalu Admin)
- Task hanya terlihat oleh:
  - Admin: semua task
  - Member/assignee: hanya task yang di-assign ke dia
- Activity log, archive list & card
- My Cards (semua card yang di-assign ke user)
- Comment, attachment, checklist
- AJAX full (tanpa reload halaman)

Instalasi singkat:
1. Buat virtualenv dan install requirements:
   pip install -r requirements.txt

2. Buat database MySQL:
   CREATE DATABASE arviga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

3. Sesuaikan DATABASES di arviga/settings.py bila perlu.

4. Jalankan migrasi:
   python manage.py migrate

5. Buat superuser:
   python manage.py createsuperuser

6. Jalankan server:
   python manage.py runserver

Login, buat project, atur member & role di menu Team & Roles, dan gunakan board seperti Trello.
