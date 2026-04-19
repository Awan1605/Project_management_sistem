🚀 Arva – AI-Powered Project Management System
📌 Overview

Arva adalah aplikasi Project Management berbasis web yang menggabungkan Kanban Board dengan integrasi AI multi-provider untuk membantu manajemen tugas secara lebih efisien.

✨ Features
🧩 Project & Task Management
    Kanban board dengan drag & drop
    Role per project:
    Admin
    Member
    Viewer
    Akses task:
    Admin: semua task
    Member: hanya task yang di-assign

📋 Task Features
    Comment
    Attachment
    Checklist
    Archive (list & card)
    Activity log

👤 User Features
    My Cards (task milik user)
⚡ System
    Full AJAX (tanpa reload halaman)
🤖 AI Integration
    Supported Providers
    Gemini
    OpenAI
    Ollama
    DeepSeek
    Claude
    Capabilities
    AI Priority Queue (analisis prioritas otomatis)
    AI Chat Assistant
    AI Developer (code generation & analysis)
🛠️ Tech Stack
    Backend: Django
    Database: MySQL
    Frontend: HTML, CSS, JavaScript
    Interaction: jQuery + AJAX
⚙️ Installation
    Clone Repository
    git clone https://github.com/Awan1605/Project_management_sistem.git
    cd arva
    Setup Virtual Environment
    python -m venv venv
    source venv/bin/activate   # Linux / Mac
    venv\Scripts\activate      # Windows
    Install Dependencies
    pip install -r requirements.txt
    Setup Database
    CREATE DATABASE arviga_db 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

    Edit konfigurasi di: 
    arviga/settings.py
    Migration
    python manage.py migrate
    Create Superuser
    python manage.py createsuperuser
    Run Server
    python manage.py runserver  
    Akses: 
    http://127.0.0.1:8000
    
🧑‍💻 Usage
    Login ke sistem
    Buat project
    Tambahkan member & role di menu Team & Roles
    Konfigurasi AI di menu AI Settings
    Kelola task di Kanban board
📁 Project Structure
    arva/
    │── arviga/
    │── app/
    │── templates/
    │── static/
    │── manage.py
🔐 Role & Permission
    Admin → full access
    Member → assigned task only
    Viewer → read-only
📊 Future Improvements
    Notifikasi real-time
    Mobile responsive enhancement
    Dashboard analytics
    Integrasi API tambahan
