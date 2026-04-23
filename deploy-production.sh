#!/bin/bash
# ============================================================
# Production Deployment Script - Arva Kanban
# ============================================================
# Run this script on your production server (Ubuntu/Debian)
# Usage: sudo bash deploy-production.sh
# ============================================================

set -e  # Exit on error

echo "🚀 Starting Arva Kanban Production Deployment..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Variables
APP_DIR="/var/www/kanban"
APP_USER="www-data"
DOMAIN="yourdomain.com"
EMAIL="admin@yourdomain.com"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing System Dependencies...${NC}"
apt update
apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib libpq-dev git curl

echo -e "${YELLOW}Step 2: Setting up PostgreSQL Database...${NC}"
sudo -u postgres psql << EOF
CREATE DATABASE kanban_db;
CREATE USER kanban_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';
ALTER ROLE kanban_user SET client_encoding TO 'utf8';
ALTER ROLE kanban_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE kanban_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE kanban_db TO kanban_user;
EOF

echo -e "${GREEN}✓ Database created${NC}"

echo -e "${YELLOW}Step 3: Cloning/Updating Application...${NC}"
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR"
    git pull origin main
else
    git clone <YOUR_GIT_REPO_URL> "$APP_DIR"
    cd "$APP_DIR"
fi

echo -e "${YELLOW}Step 4: Setting up Python Virtual Environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

echo -e "${GREEN}✓ Dependencies installed${NC}"

echo -e "${YELLOW}Step 5: Configuring Environment...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${RED}⚠️  Please edit .env file with your production values${NC}"
    echo -e "${RED}   nano $APP_DIR/.env${NC}"
    read -p "Press Enter after you've configured .env..."
fi

if [ ! -f "arviga/settings.py" ]; then
    cp arviga/settings.example.py arviga/settings.py
fi

echo -e "${YELLOW}Step 6: Running Migrations...${NC}"
python manage.py migrate --noinput

echo -e "${YELLOW}Step 7: Collecting Static Files...${NC}"
python manage.py collectstatic --noinput

echo -e "${YELLOW}Step 8: Initializing RAG Database...${NC}"
python manage.py rag_initial_sync

echo -e "${YELLOW}Step 9: Setting Permissions...${NC}"
chown -R $APP_USER:$APP_USER "$APP_DIR"
chmod -R 755 "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo -e "${GREEN}✓ Permissions set${NC}"

echo -e "${YELLOW}Step 10: Configuring Gunicorn...${NC}"
cat > /etc/systemd/system/kanban.service << EOF
[Unit]
Description=Arva Kanban Django Application
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn \\
    --access-logfile - \\
    --workers 3 \\
    --bind unix:$APP_DIR/kanban.sock \\
    arviga.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable kanban
systemctl start kanban

echo -e "${GREEN}✓ Gunicorn configured and started${NC}"

echo -e "${YELLOW}Step 11: Configuring Nginx...${NC}"
cat > /etc/nginx/sites-available/kanban << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 30d;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/kanban.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }

    # Block access to sensitive files
    location ~ /\.(env|git|htaccess) {
        deny all;
    }
}
EOF

ln -sf /etc/nginx/sites-available/kanban /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

echo -e "${GREEN}✓ Nginx configured${NC}"

echo -e "${YELLOW}Step 12: Setting up SSL (Let's Encrypt)...${NC}"
apt install -y certbot python3-certbot-nginx
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email $EMAIL

echo -e "${GREEN}✓ SSL certificate installed${NC}"

echo -e "${YELLOW}Step 13: Setting up Firewall...${NC}"
ufw allow 'Nginx Full'
ufw allow OpenSSH
ufw --force enable

echo -e "${GREEN}✓ Firewall configured${NC}"

echo -e "${YELLOW}Step 14: Setting up Database Backup...${NC}"
mkdir -p /var/backups/kanban
cat > /etc/cron.d/kanban-backup << EOF
0 2 * * * root /usr/bin/pg_dump -U kanban_user kanban_db > /var/backups/kanban/db_\$(date +\%Y\%m\%d_\%H\%M\%S).sql
30 2 * * 0 root find /var/backups/kanban -name "*.sql" -mtime +7 -delete
EOF

echo -e "${GREEN}✓ Backup cron job created${NC}"

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Edit .env file with your production values"
echo "2. Create superuser: cd $APP_DIR && source venv/bin/activate && python manage.py createsuperuser"
echo "3. Initialize Google OAuth: python manage.py init_google_oauth"
echo "4. Test your site: https://$DOMAIN"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "View logs: journalctl -u kanban -f"
echo "Restart app: systemctl restart kanban"
echo "Check status: systemctl status kanban"
echo "Nginx logs: tail -f /var/log/nginx/error.log"
echo ""
