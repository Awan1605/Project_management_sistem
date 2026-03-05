# Arviga - Setup Guide

## Libraries Installed ✅

Berikut adalah library yang telah diinstall dan ditambahkan ke requirements.txt:

### New Additions:
1. **google-genai==1.0.0** - Google Gemini AI SDK (menggantikan google.generativeai yang deprecated)
2. **websockets==14.2** - WebSocket support untuk google-genai

### Updated Code:
- File `arva/ai_services.py` telah diupdate untuk menggunakan API baru `google.genai` 
- Model AI diupdate ke `gemini-2.0-flash` (model terbaru)

## Running the Application 🚀

Aplikasi sudah berjalan di: **http://127.0.0.1:8000/**

### Login Credentials:
- **Username**: admin
- **Email**: admin@arviga.co.id  
- **Password**: admin123

## Database Configuration 🗄️

### ✅ MySQL (Production & Development)

Aplikasi sekarang menggunakan **MySQL** dari Laragon dengan konfigurasi berikut:

- **Host**: 127.0.0.1:3306
- **Database**: arviga_db
- **Username**: root
- **Password**: Arviga123!
- **Charset**: utf8mb4

**Status:**
✅ MySQL service running di Laragon
✅ Database `arviga_db` sudah dibuat
✅ Semua migrasi Django sudah di-apply
✅ Server berjalan normal di http://127.0.0.1:8000/

### ⚠️ Troubleshooting MySQL:

**Jika MySQL tidak connect:**
1. Pastikan Laragon running dan MySQL service aktif
2. Cek port 3306 listening: `netstat -ano | findstr ":3306"`
3. Test koneksi manual dengan command:
   ```bash
   python -c "import MySQLdb; conn = MySQLdb.connect(host='127.0.0.1', user='root', passwd='Arviga123!'); print('Connected!')"
   ```

**Jika ada error kolom duplicate:**
```bash
python manage.py migrate arva 0005 --fake
```

**Jika ingin switch ke SQLite (untuk development cepat):**
Buat file `arviga/local_settings.py` dengan isi:
```python
from .settings import *
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## Commands Reference:

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver

# Install all dependencies
pip install -r requirements.txt
```

## Features Available:
✅ Task Board (Trello-like kanban)
✅ Project Management
✅ AI Priority Analysis (Google Gemini)
✅ AI Chat Assistant
✅ Activity Log
✅ My Cards View
✅ Subprojects
✅ Team Members Management
✅ Google OAuth Login
