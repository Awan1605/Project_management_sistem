# 🚀 Deployment Guide - Arva Kanban

## 📋 Pre-Deployment Checklist

### ✅ Files Prepared for Commit

**Core Application Files:**
- ✅ `arva/ai_services.py` - AI chat improvements
- ✅ `arva/signals.py` - Async RAG sync & attachment extraction
- ✅ `arva/views/ai.py` - AI chat view updates
- ✅ `arva/views/task.py` - Task delete permission fix
- ✅ `arva/templates/arva/ai_chat.html` - Mobile responsive + avatar
- ✅ `arva/document_extractor.py` - NEW: Document content extraction
- ✅ `arva/rag_knowledge.py` - NEW: RAG vector database
- ✅ `arva/rag_search.py` - NEW: RAG search functionality
- ✅ `arva/management/commands/rag_initial_sync.py` - NEW: RAG sync command
- ✅ `arva/management/commands/init_google_oauth.py` - NEW: Google OAuth init
- ✅ `requirements.txt` - Updated dependencies
- ✅ `static/arva/css/pages/ai_chat.css` - Mobile responsive
- ✅ `static/arva/css/pages/user_list.css` - Mobile responsive
- ✅ `.gitignore` - Updated to exclude sensitive files

### ❌ Files NOT Committed (Sensitive/Auto-generated)

**Environment-Specific:**
- ❌ `arviga/settings.py` - Contains secrets (use `settings.example.py` as template)
- ❌ `.env` - API keys, database credentials
- ❌ `db.sqlite3` - Local database

**Auto-Generated:**
- ❌ `arva/migrations/0002_*.py` to `0016_*.py` - Django migrations
- ❌ `.rag_chromadb/` - RAG vector database
- ❌ `__pycache__/` - Python cache
- ❌ `venv/` - Virtual environment

**Local Development:**
- ❌ `models/*.gguf` - Local LLM models (large files)
- ❌ `media/avatars/` - User uploaded avatars
- ❌ `media/attachments/` - Task attachments
- ❌ `setup-hosting.sh` - Deployment script
- ❌ `local_ai_server.py` - Local AI server
- ❌ Documentation files (`.md` files)

---

## 🛠️ Deployment Steps

### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd kanban
```

### Step 2: Setup Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Copy settings template
cp arviga/settings.example.py arviga/settings.py

# Copy environment template
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

### Step 5: Environment Variables (.env)

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (for production, use PostgreSQL/MySQL)
# SQLite is fine for development
# DATABASE_URL=sqlite:///db.sqlite3

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# AI Provider (choose one)
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-chat

# OR OpenAI
# AI_PROVIDER=openai
# OPENAI_API_KEY=your-openai-api-key
# OPENAI_MODEL=gpt-3.5-turbo

# OR Ollama (local)
# AI_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.2

# Email (for notifications)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Step 6: Generate Django Secret Key

```python
# Run in Python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Step 7: Apply Migrations

```bash
# Create migrations from models
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### Step 8: Create Superuser

```bash
python manage.py createsuperuser
```

### Step 9: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Step 10: Initialize RAG Database

```bash
# Sync existing data to RAG
python manage.py rag_initial_sync
```

### Step 11: Test Locally

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

---

## 🌐 Production Deployment

### Option A: Deploy to VPS (Ubuntu/Debian)

#### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx postgresql
```

#### 2. Setup PostgreSQL (Recommended for Production)

```bash
sudo -u postgres psql
CREATE DATABASE kanban_db;
CREATE USER kanban_user WITH PASSWORD 'your-password';
ALTER ROLE kanban_user SET client_encoding TO 'utf8';
ALTER ROLE kanban_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE kanban_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE kanban_db TO kanban_user;
\q
```

Update `.env`:
```env
DATABASE_URL=postgresql://kanban_user:your-password@localhost:5432/kanban_db
```

Install PostgreSQL adapter:
```bash
pip install psycopg2-binary
```

#### 3. Configure Gunicorn

```bash
pip install gunicorn

# Create systemd service
sudo nano /etc/systemd/system/kanban.service
```

```ini
[Unit]
Description=Arva Kanban Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/kanban
Environment="PATH=/path/to/kanban/venv/bin"
ExecStart=/path/to/kanban/venv/bin/gunicorn \
    --access-logfile - \
    --workers 3 \
    --bind unix:/path/to/kanban/kanban.sock \
    arviga.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start kanban
sudo systemctl enable kanban
```

#### 4. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/kanban
```

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /path/to/kanban/staticfiles/;
    }

    location /media/ {
        alias /path/to/kanban/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/kanban/kanban.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/kanban /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Setup SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

### Option B: Deploy to Docker

#### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "arviga.wsgi:application"]
```

#### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./media:/app/media
    env_file:
      - .env
    depends_on:
      - db

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_DB=kanban_db
      - POSTGRES_USER=kanban_user
      - POSTGRES_PASSWORD=your-password

volumes:
  postgres_data:
```

#### 3. Build & Run

```bash
docker-compose up -d
```

---

## 🔧 Post-Deployment

### 1. Initialize Google OAuth

```bash
python manage.py init_google_oauth
```

### 2. Configure AI Settings

Login as admin → AI Settings → Configure your AI provider

### 3. Test RAG Sync

```bash
python manage.py rag_initial_sync
```

### 4. Setup Backup (Database)

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp db.sqlite3 /backup/db_${DATE}.sqlite3

# Or for PostgreSQL
pg_dump kanban_db > /backup/db_${DATE}.sql
```

### 5. Setup Monitoring

```bash
# Check logs
sudo journalctl -u kanban -f

# Check Gunicorn
sudo systemctl status kanban

# Check Nginx
sudo systemctl status nginx
```

---

## 📊 Performance Optimization

### 1. Enable Database Connection Pooling (PostgreSQL)

```env
# Add to .env
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### 2. Setup Redis Cache (Optional)

```bash
pip install django-redis
```

```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### 3. Optimize Static Files

```python
# settings.py
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
```

---

## 🛡️ Security Checklist

- ✅ Set `DEBUG = False`
- ✅ Set proper `ALLOWED_HOSTS`
- ✅ Use strong `SECRET_KEY`
- ✅ Enable HTTPS/SSL
- ✅ Setup database backups
- ✅ Keep dependencies updated
- ✅ Monitor error logs
- ✅ Setup firewall (UFW)
- ✅ Use strong passwords
- ✅ Enable rate limiting

---

## 🆘 Troubleshooting

### Issue: Migrations not working

```bash
# Reset migrations (development only!)
find arva/migrations -name "0*.py" -delete
python manage.py makemigrations
python manage.py migrate
```

### Issue: Static files not loading

```bash
python manage.py collectstatic --clear
python manage.py collectstatic
```

### Issue: RAG not working

```bash
# Check ChromaDB
ls -la .rag_chromadb/

# Re-sync
python manage.py rag_initial_sync
```

### Issue: AI not responding

```bash
# Test API key
curl -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
     https://api.deepseek.com/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'
```

---

## 📞 Support

If you encounter any issues:
1. Check Django logs: `python manage.py runserver --verbosity 2`
2. Check browser console for JavaScript errors
3. Verify `.env` configuration
4. Ensure all migrations applied

---

**Happy Deploying! 🚀✨**
