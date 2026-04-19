<div align="center">

# 🚀 Arva
### AI-Powered Project Management System

</div>

---

## 📌 Overview

Arva adalah aplikasi **Project Management** berbasis web yang menggabungkan **Kanban Board** dengan integrasi **AI multi-provider** untuk membantu manajemen tugas secara lebih efisien.

## ✨ Features
### 🧩 Project & Task Management
- Kanban board dengan drag & drop
- Role per project: **Admin**, **Member**, **Viewer**
- Akses task berdasarkan role:
  - **Admin** → semua task
  - **Member** → hanya task yang di-assign
  - **Viewer** → read-only

### 📋 Task Features
- Comment
- Attachment
- Checklist
- Archive (list & card)
- Activity log

### 👤 User Features
- My Cards (task milik user)

### ⚡ System
- Full AJAX (tanpa reload halaman)

## 🤖 AI Integration
### ☁️ Cloud API Providers
  | Provider | Model Examples | Status |
  |----------|----------------|--------|
  | **Google Gemini** | Gemini 2.0 Flash, Gemini 1.5 Pro, Gemini 1.5 Flash | ✅ |
  | **DeepSeek** | DeepSeek-Chat, DeepSeek-Coder | ✅ |
  | **Claude (Anthropic)** | Claude 3.5 Sonnet, Claude 3 Opus | ✅ |
  | **OpenAI** | GPT-4o, GPT-4 Turbo, GPT-3.5 | ✅ |

### 🖥️ Local AI (Ollama — Multi Vendor)
  | Model | Vendor | Status |
  |-------|--------|--------|
  | Llama 3 | Meta | ✅ |
  | Mistral | Mistral AI | ✅ |
  | Gemma | Google | ✅ |
  | Qwen | Alibaba | ✅ |
  | Phi-3 | Microsoft | ✅ |
  | CodeLlama | Meta | ✅ |
  | + model lainnya via Ollama | — | ✅ |

> 💡 Ollama memungkinkan menjalankan berbagai model AI secara lokal tanpa internet. Semua model yang tersedia di [ollama.com/library](https://ollama.com/library) dapat digunakan.

### Capabilities
- **AI Priority Queue** — analisis prioritas otomatis
- **AI Chat Assistant** — asisten percakapan berbasis AI
- **AI Developer** — code generation & analysis

---
## 🛠️ Tech Stack
  | Layer | Technology |
  |-------|------------|
  | Backend | Django |
  | Database | MySQL |
  | Frontend | HTML, CSS, JavaScript |
  | Interaction | jQuery + AJAX |

---
## ⚙️ Installation
### 1. Clone Repository
```bash
git clone https://github.com/Awan1605/Project_management_sistem.git
cd arva
```
### 2. Setup Virtual Environment
```bash
python -m venv venv
# Linux / Mac
source venv/bin/activate
# Windows
venv\Scripts\activate
```
### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
### 4. Setup Database
```sql
CREATE DATABASE arviga_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;
```
Lalu edit konfigurasi database di: `arviga/settings.py`

### 5. Migration
```bash
python manage.py migrate
```
### 6. Create Superuser
```bash
python manage.py createsuperuser
```
### 7. Run Server
```bash
python manage.py runserver
```
Akses aplikasi di: [http://127.0.0.1:8000](http://127.0.0.1:8000)
---
## 🧑‍💻 Usage
1. Login ke sistem
2. Buat project baru
3. Tambahkan member & atur role di menu **Team & Roles**
4. Konfigurasi AI provider di menu **AI Settings**
5. Kelola task di **Kanban Board**
---
## 📁 Project Structure
```
arva/
├── arviga/
├── app/
├── templates/
├── static/
└── manage.py
```
## 🔐 Role & Permission
| Role | Access |
|------|--------|
| **Admin** | Full access ke semua task & pengaturan |
| **Member** | Hanya task yang di-assign |
| **Viewer** | Read-only |
---
## 📊 Future Improvements
- [ ] Notifikasi real-time
- [ ] Mobile responsive enhancement
- [ ] Dashboard analytics
- [ ] Integrasi API tambahan
