"""
Layanan AI (Artificial Intelligence)
=====================================
Modul inti yang menangani semua interaksi dengan layanan AI eksternal.

Dua layanan utama:
1. AIService - Analisis prioritas task (mendukung banyak provider)
2. AIChatService - Asisten chat AI dengan kesadaran konteks

Provider yang didukung:
- OpenClaw (self-hosted, OpenAI-compatible)
- Google Gemini
- Qoder/Anthropic Claude
- DeepSeek
- Ollama (via OpenAI-compatible API)

Factory function:
- get_ai_service() -> AIService
- get_ai_chat_service() -> AIChatService
"""

import json
import logging
from typing import Dict, List, Optional

from django.utils import timezone
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)

# ============================================================
# IMPORT LIBRARY AI (dengan fallback jika belum terinstall)
# ============================================================

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

if not OPENAI_AVAILABLE:
    try:
        import openai
        OpenAI = openai.OpenAI
        OPENAI_AVAILABLE = True
    except (ImportError, AttributeError):
        pass

# Import Google GenAI untuk provider Gemini
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

# Import Anthropic untuk provider Qoder/Claude
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================
# KELAS DASAR: BaseAIService
# ============================================================

class BaseAIService:
    """Kelas dasar untuk semua layanan AI.
    
    Menyediakan method bersama yang dipakai oleh AIService dan AIChatService:
    - _init_client(): Inisialisasi client berdasarkan provider
    - _build_task_context(): Bangun konteks task untuk analisis
    - _build_analysis_prompt(): Bangun prompt analisis prioritas
    - _parse_json_response(): Parse respons JSON dari AI
    """
    
    def _init_client(self, ai_settings):
        """Inisialisasi client AI berdasarkan provider yang dikonfigurasi.
        
        Menentukan client yang tepat (OpenAI, Google GenAI, atau Anthropic)
        berdasarkan pengaturan provider di database.
        
        Args:
            ai_settings: Objek AISettings dari database
            
        Returns:
            tuple: (client, client_type) dimana client_type adalah string
                   yang mengidentifikasi jenis client untuk routing API call
        """
        provider = ai_settings.provider
        base_url = ai_settings.base_url or 'http://localhost:8080/v1'
        api_key = ai_settings.api_key
        
        if provider == 'openclaw':
            if not OPENAI_AVAILABLE:
                raise ValueError("Package OpenAI belum terinstall. Jalankan: pip install openai")
            client = OpenAI(base_url=base_url, api_key=api_key or 'not-needed')
            return client, 'openai'
            
        elif provider == 'google':
            if not api_key:
                raise ValueError("GEMINI_API_KEY belum dikonfigurasi di AI Settings")
            if not GENAI_AVAILABLE:
                raise ValueError("Package google-genai belum terinstall. Jalankan: pip install google-genai")
            client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
            return client, 'google'
            
        elif provider == 'qoder':
            if not ANTHROPIC_AVAILABLE:
                raise ValueError("Package Anthropic belum terinstall. Jalankan: pip install anthropic")
            if not api_key:
                raise ValueError("API Key belum dikonfigurasi di AI Settings untuk Qoder")
            # Qoder bisa menggunakan proxy endpoint atau Anthropic API langsung
            if base_url and base_url != 'http://localhost:8080/v1':
                client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
            else:
                client = anthropic.Anthropic(api_key=api_key)
            return client, 'anthropic'
            
        elif provider == 'deepseek':
            # DeepSeek menggunakan API yang kompatibel dengan OpenAI
            if not OPENAI_AVAILABLE:
                raise ValueError("Package OpenAI belum terinstall. Jalankan: pip install openai")
            if not api_key:
                raise ValueError("DeepSeek API Key belum dikonfigurasi di AI Settings")
            client = OpenAI(
                base_url='https://api.deepseek.com',
                api_key=api_key
            )
            return client, 'openai'
            
        else:
            # Default ke OpenClaw
            if not OPENAI_AVAILABLE:
                raise ValueError("Package OpenAI belum terinstall. Jalankan: pip install openai")
            client = OpenAI(base_url=base_url, api_key=api_key or 'not-needed')
            return client, 'openai'
    
    def _build_task_context(self, task) -> Dict:
        """Bangun konteks lengkap dari sebuah task untuk analisis AI.
        
        Mengumpulkan informasi task termasuk: judul, deskripsi, deadline,
        progress checklist, assignee, labels, dan status.
        
        Args:
            task: Objek Task dari database
            
        Returns:
            Dict berisi konteks task yang terstruktur
        """
        from .models import Task
        
        # Kumpulkan progress checklist
        checklist_items = list(task.checklist_items.all())
        checklist_progress = {
            'total': len(checklist_items),
            'done': sum(1 for item in checklist_items if item.is_done),
            'items': [item.content for item in checklist_items]
        }
        
        # Hitung hari menuju deadline
        days_until_due = None
        urgency_indicator = ""
        if task.due_date:
            # Pastikan perbandingan date vs date (bukan datetime)
            due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
            days_until_due = (due_date - timezone.localdate()).days
            if days_until_due < 0:
                urgency_indicator = "OVERDUE"
            elif days_until_due == 0:
                urgency_indicator = "DUE TODAY"
            elif days_until_due <= 2:
                urgency_indicator = "URGENT"
        
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description or "",
            'due_date': str(task.due_date) if task.due_date else None,
            'days_until_due': days_until_due,
            'urgency_indicator': urgency_indicator,
            'current_priority': task.priority,
            'project_name': task.project.name,
            'assignees': [u.username for u in task.assignees.all()],
            'checklist_progress': checklist_progress,
            'labels': [label.name for label in task.labels.all()],
            'is_archived': task.is_archived,
            'created_at': str(task.created_at),
            'task_list': task.task_list.name if task.task_list else None,
        }
    
    def _build_analysis_prompt(self, task_context: Dict) -> str:
        """Bangun prompt AI untuk analisis prioritas task.
        
        Jika ada custom prompt di pengaturan AI, gunakan itu.
        Jika tidak, gunakan prompt default yang meminta output JSON terstruktur.
        
        Args:
            task_context: Dict konteks task dari _build_task_context()
            
        Returns:
            String prompt yang siap dikirim ke AI
        """
        from .models import AISettings
        
        # Cek apakah ada custom prompt
        ai_settings = AISettings.get_current()
        if ai_settings.priority_analysis_prompt:
            # Gunakan custom prompt dengan placeholder
            prompt_template = ai_settings.priority_analysis_prompt
            prompt = prompt_template.format(**task_context)
        else:
            # Gunakan prompt default
            prompt = f"""Analisis task berikut dan berikan prioritas komprehensif.

TASK INFORMATION:
Title: {task_context['title']}
Description: {task_context['description']}
Project: {task_context['project_name']}
Current Status: {task_context['task_list']}

DEADLINE ANALYSIS:
Due Date: {task_context['due_date'] or 'No deadline set'}
Days Until Due: {task_context['days_until_due'] if task_context['days_until_due'] is not None else 'N/A'}
Urgency: {task_context['urgency_indicator'] or 'Normal'}

WORK BREAKDOWN:
Checklist Progress: {task_context['checklist_progress']['done']}/{task_context['checklist_progress']['total']} completed
Checklist Items: {', '.join(task_context['checklist_progress']['items'][:5]) if task_context['checklist_progress']['items'] else 'None'}

ASSIGNMENT:
Assignees: {', '.join(task_context['assignees']) if task_context['assignees'] else 'Unassigned'}
Labels: {', '.join(task_context['labels']) if task_context['labels'] else 'None'}

ANALYSIS CRITERIA:
1. Deadline Urgency (40%): Tasks nearing deadline get higher priority. OVERDUE tasks must get score 85-100 (Critical)
2. Complexity/Scope (25%): More complex tasks may need earlier start
3. Dependencies Impact (20%): Tasks blocking others are critical
4. Current Progress (15%): Nearly complete tasks might be prioritized to finish

IMPORTANT: If task is OVERDUE (past due date), priority_score MUST be 85-100 and priority_level MUST be "Critical"

Provide analysis in this exact JSON format:
{{
  "priority_score": <number 1-100>,
  "priority_level": "Critical|High|Medium|Low",
  "complexity": "High|Medium|Low",
  "estimated_hours": <number or null>,
  "reasoning": "<detailed explanation in Indonesian>",
  "recommended_action": "<specific advice in Indonesian>",
  "factors": {{
    "deadline_urgency": <score 1-100>,
    "complexity_score": <score 1-100>,
    "dependency_impact": <score 1-100>,
    "progress_factor": <score 1-100>
  }}
}}

Respond ONLY with the JSON, no other text."""
        return prompt
    
    def _parse_json_response(self, response_text: str) -> Dict:
        """Parse respons JSON dari AI, menangani code block markdown.
        
        AI sering mengembalikan JSON dalam blok markdown code (```json ... ```).
        Method ini mengekstrak JSON dari dalam blok tersebut jika ada.
        
        Args:
            response_text: Respons mentah dari AI
            
        Returns:
            Dict hasil parsing JSON
            
        Raises:
            json.JSONDecodeError: Jika respons tidak bisa diparse sebagai JSON
        """
        # Ekstrak JSON dari code block markdown jika ada
        if '```json' in response_text:
            json_str = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            json_str = response_text.split('```')[1].split('```')[0].strip()
        else:
            json_str = response_text
        
        return json.loads(json_str)
    
    def _call_ai_api(self, prompt: str, system_prompt: str = None) -> str:
        """Panggil API AI dengan prompt yang diberikan.
        
        Method ini merouting panggilan ke API yang tepat berdasarkan
        client_type (openai, google, anthropic).
        
        Args:
            prompt: Prompt/pesan yang akan dikirim ke AI
            system_prompt: Opsional, system prompt untuk OpenAI/Anthropic
            
        Returns:
            String respons dari AI
        """
        from .models import AISettings
        
        if self.client_type in ('openai',):
            # OpenAI-compatible API (OpenClaw, DeepSeek, Ollama)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content.strip()
            
        elif self.client_type == 'anthropic':
            # Anthropic Claude API (Qoder)
            messages = [{"role": "user", "content": prompt}]
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=min(self.max_tokens, 4096),
                temperature=self.temperature,
                system=system_prompt or "",
                messages=messages
            )
            return response.content[0].text.strip()
            
        else:
            # Google Gemini API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()


# ============================================================
# KELAS UTAMA: AIService (Analisis Prioritas Task)
# ============================================================

class AIService(BaseAIService):
    """Layanan AI untuk analisis prioritas task.
    
    Mendukung banyak provider AI (OpenClaw, Gemini, Qoder, DeepSeek).
    Menggunakan BaseAIService untuk inisialisasi client dan method pembantu.
    """
    
    def __init__(self):
        """Inisialisasi service dengan pengaturan AI dari database."""
        from .models import AISettings
        ai_settings = AISettings.get_current()
        
        self.provider = ai_settings.provider
        self.model_name = ai_settings.get_active_model()
        self.temperature = float(ai_settings.temperature)
        self.max_tokens = ai_settings.max_tokens
        
        # Inisialisasi client via method base class
        self.client, self.client_type = self._init_client(ai_settings)
    
    def analyze_task(self, task) -> Dict:
        """Analisis satu task dan kembalikan rekomendasi prioritas.
        
        Mengirim konteks task ke AI dan meminta analisis dalam format JSON.
        Hasilnya mencakup: skor prioritas, level, kompleksitas, estimasi jam,
        penalaran, dan faktor-faktor yang mempengaruhi.
        
        Args:
            task: Objek Task yang akan dianalisis
            
        Returns:
            Dict berisi hasil analisis atau error
        """
        try:
            context = self._build_task_context(task)
            prompt = self._build_analysis_prompt(context)
            
            response_text = self._call_ai_api(prompt)
            
            result = self._parse_json_response(response_text)
            
            # Tambahkan metadata
            result['task_id'] = task.id
            result['analyzed_at'] = str(timezone.now())
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                'error': 'Gagal parse respons AI',
                'raw_response': response_text if 'response_text' in locals() else str(e),
                'task_id': task.id
            }
        except Exception as e:
            return {
                'error': str(e),
                'task_id': task.id
            }
    
    def analyze_multiple_tasks(self, tasks: List) -> List[Dict]:
        """Analisis banyak task dan kembalikan daftar yang diurutkan berdasarkan prioritas.
        
        Args:
            tasks: List objek Task yang akan dianalisis
            
        Returns:
            List Dict hasil analisis, diurutkan dari prioritas tertinggi
        """
        results = []
        for task in tasks:
            analysis = self.analyze_task(task)
            if 'error' not in analysis:
                # Boost priority for overdue tasks
                due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                if task.due_date and due_date < timezone.localdate():
                    # Overdue tasks get minimum score of 85 (Critical)
                    current_score = analysis.get('priority_score', 0)
                    boosted_score = max(current_score, 85)
                    analysis['priority_score'] = boosted_score
                    analysis['priority_level'] = 'Critical'
                    days_overdue = (timezone.localdate() - due_date).days
                    analysis['reasoning'] = f"[TERLAMBAT {days_overdue} HARI] " + analysis.get('reasoning', '')
                results.append(analysis)
        
        # Urutkan berdasarkan skor prioritas (tertinggi dulu)
        results.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return results
    
    def get_priority_queue(self, user, project=None, limit=20) -> List[Dict]:
        """Ambil antrean task yang diprioritaskan untuk user.
        
        Mengambil task yang ditugaskan ke user atau milik project user,
        lalu menganalisis dan mengurutkan berdasarkan prioritas.
        
        Args:
            user: User yang task-nya akan dianalisis
            project: Opsional, filter berdasarkan project tertentu
            limit: Jumlah maksimum task yang dianalisis
            
        Returns:
            List Dict hasil analisis yang sudah diurutkan
        """
        from .models import Task
        
        # Ambil task yang ditugaskan ke user atau di project milik user
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            models.Q(assignees=user) | models.Q(project__owner=user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        ).prefetch_related(
            'assignees', 'labels', 'checklist_items'
        )
        
        if project:
            tasks = tasks.filter(project=project)
        
        tasks = tasks[:limit]
        return self.analyze_multiple_tasks(tasks)


# ============================================================
# KELAS: AIChatService (Asisten Chat AI)
# ============================================================

class AIChatService(BaseAIService):
    """Layanan AI Chat Assistant dengan kesadaran konteks task.
    
    Mendukung banyak provider AI. Menggunakan BaseAIService untuk
    inisialisasi client dan method pembantu.
    """
    
    def __init__(self):
        """Inisialisasi chat service dengan pengaturan AI dari database."""
        from .models import AISettings
        ai_settings = AISettings.get_current()
        
        self.provider = ai_settings.provider
        self.model_name = ai_settings.get_active_model()
        self.temperature = float(ai_settings.temperature)
        self.max_tokens = ai_settings.max_tokens
        
        # Inisialisasi client via method base class
        self.client, self.client_type = self._init_client(ai_settings)
    
    def _get_user_tasks_context(self, user) -> str:
        """Ambil konteks task user yang diformat untuk AI.
        
        Mengambil 5 task paling mendesak dan mengurutkannya:
        1. Overdue (paling terlambat dulu)
        2. Hari ini
        3. Mendatang
        
        Format ringkas untuk efisiensi token.
        
        Args:
            user: User yang task-nya akan diambil
            
        Returns:
            String konteks task yang terformat
        """
        from .models import Task, ChecklistItem
        
        # Ambil 5 task paling mendesak
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            models.Q(assignees=user) | models.Q(project__owner=user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        ).prefetch_related(
            'checklist_items'
        ).order_by('due_date')[:5]
        
        if not tasks:
            return "Tidak ada tugas yang sedang aktif untuk user ini."
        
        # Urutkan: Overdue dulu (paling terlambat), lalu hari ini, lalu mendatang
        tasks_list = list(tasks)
        
        # Helper untuk mendapatkan date (handle datetime atau date)
        def get_date(d):
            return d.date() if hasattr(d, 'date') else d
        
        today_date = timezone.localdate()
        overdue = [t for t in tasks_list if t.due_date and get_date(t.due_date) < today_date]
        overdue.sort(key=lambda t: t.due_date)  # Paling terlambat dulu
        
        today = [t for t in tasks_list if t.due_date and get_date(t.due_date) == today_date]
        upcoming = [t for t in tasks_list if not t.due_date or get_date(t.due_date) > today_date]
        upcoming.sort(key=lambda t: t.due_date if t.due_date else timezone.now())
        
        sorted_tasks = overdue + today + upcoming
        
        context_parts = []
        for i, task in enumerate(sorted_tasks, 1):
            # Info deadline dengan format jelas
            deadline_info = ""
            if task.due_date:
                due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                days_until = (due - timezone.localdate()).days
                if days_until < 0:
                    deadline_info = f"TERLAMBAT {abs(days_until)} HARI"
                elif days_until == 0:
                    deadline_info = "HARI INI"
                else:
                    deadline_info = f"{days_until} hari lagi"
            
            # Bangun info task - SANGAT SINGKAT untuk kecepatan
            task_info = f"{i}. {task.title}"
            task_info += f"\n   Status: {task.task_list.name}"
            if deadline_info:
                task_info += f"\n   Deadline: {deadline_info}"
            
            # Tambah deskripsi hanya jika pendek
            if task.description and len(task.description) < 100:
                task_info += f"\n   Info: {task.description}"
            
            # Tambah checklist hanya jika sangat pendek (hemat token)
            checklist = task.checklist_items.all()
            if checklist and len(checklist) <= 2:
                task_info += "\n   Steps:"
                for item in checklist:
                    status = "✓" if item.is_done else "○"
                    task_info += f"\n      {status} {item.content}"
            
            context_parts.append(task_info)
        
        return "\n\n".join(context_parts)
    
    def _extract_task_name(self, message: str) -> str:
        """Ekstrak nama task dari pesan user.
        
        Mencoba menemukan nama task setelah keyword seperti 'task', 'tugas', etc.
        
        Args:
            message: Pesan dari user
            
        Returns:
            String nama task yang diekstrak, atau empty string jika tidak ditemukan
        """
        import re
        
        message_lower = message.lower()
        
        # Pattern umum: "... task [nama] ..." atau "... tugas [nama] ..."
        patterns = [
            r'task\s+["\']?([^"\']+)["\']?',
            r'tugas\s+["\']?([^"\']+)["\']?',
            r'jelaskan\s+(?:task\s+|tugas\s+)?["\']?([^"\']+)["\']?',
            r'detail\s+(?:task\s+|tugas\s+)?["\']?([^"\']+)["\']?',
            r'apa\s+itu\s+(?:task\s+|tugas\s+)?["\']?([^"\']+)["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                # Ambil group 1 (nama task) dan bersihkan
                task_name = match.group(1).strip()
                # Hapus kata-kata umum di akhir
                task_name = re.sub(r'\s+(saya|ini|itu|yang)\s*$', '', task_name)
                return task_name
        
        # Jika tidak match pattern, ambil kata-kata setelah keyword
        keywords = ['task', 'tugas', 'jelaskan', 'detail', 'apa itu']
        for keyword in keywords:
            if keyword in message_lower:
                # Ambil text setelah keyword
                idx = message_lower.find(keyword) + len(keyword)
                remaining = message[idx:].strip()
                # Ambil beberapa kata pertama sebagai nama task
                words = remaining.split()[:5]  # Max 5 kata
                if words:
                    return ' '.join(words)
        
        return ""
    
    def _get_specific_task_context(self, user, task_name_query: str) -> str:
        """Cari dan ambil detail task spesifik berdasarkan nama.
        
        Mencari task yang cocok dengan query nama (partial match).
        
        Args:
            user: User yang mencari task
            task_name_query: Nama atau keyword task yang dicari
            
        Returns:
            String detail task yang terformat, atau pesan tidak ditemukan
        """
        from .models import Task, ChecklistItem
        
        # Cari task yang cocok dengan query (case insensitive, partial match)
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            models.Q(assignees=user) | models.Q(project__owner=user)
        ).filter(
            models.Q(title__icontains=task_name_query) | 
            models.Q(description__icontains=task_name_query)
        ).select_related(
            'project', 'task_list', 'created_by'
        ).prefetch_related(
            'checklist_items', 'assignees'
        ).order_by('-created_at')[:3]  # Ambil max 3 task yang paling cocok
        
        if not tasks:
            return f"Tidak ditemukan task dengan nama '{task_name_query}'. Coba periksa ejaan atau gunakan kata kunci lain."
        
        context_parts = []
        for i, task in enumerate(tasks, 1):
            # Info dasar task
            task_info = f"📌 TASK #{i}: {task.title}"
            
            # Status dan Lokasi
            task_info += f"\n   Status: {task.task_list.name}"
            if task.project:
                task_info += f"\n   Project: {task.project.name}"
            
            # Deadline
            if task.due_date:
                due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                days_until = (due - timezone.localdate()).days
                if days_until < 0:
                    task_info += f"\n   Deadline: TERLAMBAT {abs(days_until)} HARI ({task.due_date})"
                elif days_until == 0:
                    task_info += f"\n   Deadline: HARI INI ({task.due_date})"
                else:
                    task_info += f"\n   Deadline: {days_until} hari lagi ({task.due_date})"
            else:
                task_info += "\n   Deadline: Tidak ditentukan"
            
            # Prioritas
            if task.priority:
                priority_map = {'p0': 'URGENT', 'p1': 'HIGH', 'p2': 'MEDIUM', 'p3': 'LOW'}
                priority_label = priority_map.get(task.priority, task.priority.upper())
                task_info += f"\n   Prioritas: {priority_label}"
            
            # Deskripsi lengkap
            if task.description:
                task_info += f"\n\n   📝 DESKRIPSI:\n   {task.description}"
            
            # Assignees
            assignees = list(task.assignees.all())
            if assignees:
                assignee_names = ', '.join([u.username for u in assignees])
                task_info += f"\n\n   👥 ASSIGNED TO: {assignee_names}"
            
            # Checklist
            checklist = task.checklist_items.all()
            if checklist:
                task_info += f"\n\n   ✅ CHECKLIST ({checklist.filter(is_done=True).count()}/{checklist.count()} selesai):"
                for item in checklist:
                    status = "✓" if item.is_done else "○"
                    task_info += f"\n      {status} {item.content}"
            
            # Cover color jika ada
            if task.cover_color:
                task_info += f"\n\n   🎨 Label Warna: {task.cover_color}"
            
            context_parts.append(task_info)
        
        return "\n\n" + "\n\n".join(context_parts)
    
    def _build_system_prompt(self, user) -> str:
        """Bangun system prompt dengan konteks user.
        
        Jika ada custom prompt di pengaturan AI, gunakan itu.
        Jika tidak, gunakan prompt default yang ringkas.
        
        Args:
            user: User untuk konteks
            
        Returns:
            String system prompt
        """
        from .models import AISettings
        
        ai_settings = AISettings.get_current()
        if ai_settings.chat_system_prompt:
            # Gunakan custom prompt dengan konteks minimal
            return ai_settings.chat_system_prompt.format(
                username=user.username,
                full_name=user.get_full_name() or user.username,
                tasks_context="Lihat aplikasi untuk detail tugas"
            )
        else:
            # Prompt default - SANGAT SINGKAT untuk kecepatan maksimal
            return "AI Task Assistant. Jawab singkat dalam Bahasa Indonesia."
    
    def chat(self, user, message: str, chat_history: List[Dict] = None) -> str:
        """Proses pesan chat dan kembalikan respons AI.
        
        Mendeteksi apakah user bertanya tentang task, dan jika ya,
        menyertakan konteks task saat ini dalam prompt.
        
        Args:
            user: User yang mengirim pesan
            message: Isi pesan dari user
            chat_history: Opsional, riwayat chat untuk konteks
            
        Returns:
            String respons dari AI
        """
        from .models import AISettings
        
        try:
            # Deteksi apakah user bertanya tentang task
            task_keywords = [
                'tugas', 'kerjakan', 'prioritas', 'deadline', 'project', 
                'pekerjaan', 'kerja', 'apa yang harus', 'berapa banyak',
                'ada berapa', 'list tugas', 'daftar tugas', 'task',
                'yang belum', 'yang harus', 'yang perlu'
            ]
            is_task_query = any(keyword in message.lower() for keyword in task_keywords)
            
            # Deteksi apakah user bertanya detail tentang task spesifik
            # Contoh: "jelaskan task public hotspot", "apa itu task X", "detail task Y"
            detail_keywords = ['jelaskan', 'detail', 'apa itu', 'bagaimana', 'kurang paham', 'gak ngerti', 'gak paham']
            is_detail_query = any(keyword in message.lower() for keyword in detail_keywords)
            
            # Bangun system prompt dengan konteks hanya untuk query tentang task
            if is_task_query or is_detail_query:
                
                # Jika user bertanya detail tentang task spesifik, cari task tersebut
                if is_detail_query:
                    # Ekstrak nama task dari pesan
                    task_name = self._extract_task_name(message)
                    specific_context = None
                    
                    # Kata yang diabaikan saat pencarian
                    stop_words = {'bantu', 'jelaskan', 'detail', 'tentang', 'task', 'tugas',
                                  'apa', 'itu', 'ini', 'yang', 'saya', 'untuk', 'tolong',
                                  'coba', 'bisa', 'dong', 'ya', 'kan', 'deh', 'nih'}
                    
                    if task_name:
                        specific_context = self._get_specific_task_context(user, task_name)
                        
                        # Jika tidak ditemukan, coba dengan kata kunci lebih pendek (1-2 kata pertama)
                        if specific_context.startswith('Tidak ditemukan'):
                            short_name = ' '.join(task_name.split()[:2])
                            if short_name != task_name:
                                specific_context = self._get_specific_task_context(user, short_name)
                        
                        # Masih tidak ditemukan, coba tiap kata satu per satu
                        if specific_context.startswith('Tidak ditemukan'):
                            for word in task_name.split():
                                if len(word) > 3 and word.lower() not in stop_words:
                                    result = self._get_specific_task_context(user, word)
                                    if not result.startswith('Tidak ditemukan'):
                                        specific_context = result
                                        break
                    
                    # Jika task_name kosong atau masih tidak ditemukan,
                    # coba cari dari semua kata bermakna dalam pesan
                    if not specific_context or specific_context.startswith('Tidak ditemukan'):
                        words_in_msg = [
                            w for w in message.lower().split()
                            if len(w) > 3 and w not in stop_words
                        ]
                        for word in words_in_msg:
                            result = self._get_specific_task_context(user, word)
                            if not result.startswith('Tidak ditemukan'):
                                specific_context = result
                                break
                    
                    # Jika task ditemukan, berikan penjelasan detail
                    if specific_context and not specific_context.startswith('Tidak ditemukan'):
                        system_prompt = f"""KAMU ADALAH AI TASK ASSISTANT. Jelaskan detail task berikut dengan jelas dan mudah dipahami.

{specific_context}

ATURAN PENTING:
1. Jelaskan task dengan bahasa yang mudah dipahami
2. Soroti hal-hal penting: deadline, prioritas, status
3. Jika ada checklist, jelaskan progressnya
4. Berikan rekomendasi langkah selanjutnya jika relevan
5. Gunakan emoji untuk membuat penjelasan lebih menarik
6. JANGAN tambahkan informasi di luar data yang diberikan

Format Jawaban:
📝 PENJELASAN TASK:
[Berikan penjelasan lengkap tentang task ini dalam paragraf]

📊 STATUS SAAT INI:
- Status: [Status task]
- Progress: [Jika ada checklist]
- Deadline: [Info deadline]

💡 REKOMENDASI:
[Berikan saran langkah selanjutnya]"""
                    else:
                        # Task tidak ditemukan - fallback ke daftar semua task
                        tasks_context = self._get_user_tasks_context(user)
                        return f"Maaf, task yang Anda maksud tidak ditemukan.\n\n💡 Tips: Gunakan kata kunci yang tepat. Berikut daftar tugas Anda saat ini:\n\n{tasks_context}"
                
                # Query umum tentang task (bukan detail spesifik)
                else:
                    tasks_context = self._get_user_tasks_context(user)
                    # Hitung jumlah task yang sebenarnya
                    task_lines = [t for t in tasks_context.split('\n\n') if t.strip() and not t.startswith('Tidak ada')]
                    task_count = len(task_lines)
                    
                    # Jika tidak ada task, berikan respons yang jelas
                    if task_count == 0:
                        return "Saat ini Anda tidak memiliki tugas yang aktif. Semua tugas sudah selesai atau belum ada tugas yang diassign."
                    
                    system_prompt = f"""KAMU ADALAH AI TASK ASSISTANT. Berikan informasi tugas secara AKURAT berdasarkan data berikut.

DATA TUGAS ({task_count} tugas aktif):
{tasks_context}

ATURAN PENTING:
1. SELALU sebutkan JUMLAH TOTAL tugas di awal: "Anda memiliki {task_count} tugas aktif"
2. Jika user bertanya "berapa banyak", jawab dengan jumlah yang tepat: {task_count} tugas
3. Jika user bertanya "apa yang harus dikerjakan", berikan DAFTAR LENGKAP + PRIORITAS
4. Analisa berdasarkan: deadline (overdue paling penting), status, prioritas
5. Format daftar: "✓ [Nama Tugas] - [Status] - [Deadline]"
6. Pilih TOP 2 PRIORITAS (yang paling TERLAMBAT/overdue)
7. JANGAN tambahkan informasi di luar data yang diberikan

Format Jawaban:
📋 ANDA MEMILIKI {task_count} TUGAS AKTIF:
✓ [Tugas 1] - [Status] - [Deadline]
✓ [Tugas 2] - [Status] - [Deadline]
(List semua tugas)

🎯 PRIORITAS UTAMA:
1️⃣ [Tugas Prioritas 1]
   Alasan: [Kenapa harus dikerjakan dulu - berdasarkan deadline/status]

2️⃣ [Tugas Prioritas 2]  
   Alasan: [Kenapa harus dikerjakan kedua]

📌 URUTAN PENGERJAAN:
Selesaikan [Prioritas 1] → Lanjut ke [Prioritas 2] → Kemudian [tugas lainnya]"""
            else:
                system_prompt = "Kamu adalah AI Assistant untuk manajemen tugas. Jawab dalam Bahasa Indonesia."
            
            # Bangun konteks percakapan untuk API
            full_prompt = f"""{system_prompt}

User: {message}

Assistant:"""
            
            # Tambah riwayat chat hanya untuk non-task query (hemat token)
            if chat_history and not is_task_query:
                for msg in chat_history[-2:]:
                    if msg['role'] == 'user':
                        full_prompt += f"\nUser: {msg['content']}"
                    else:
                        full_prompt += f"\nAssistant: {msg['content']}"
                full_prompt += "\nAssistant:"
            
            # Panggil API sesuai tipe client (dengan retry untuk error sementara)
            import time
            last_error = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    if self.client_type == 'openai':
                        # OpenAI-compatible API (OpenClaw, DeepSeek, Ollama)
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message}
                        ]
                        
                        # Tambah riwayat chat jika ada (maks 3 pesan)
                        if chat_history:
                            for msg in chat_history[-3:]:
                                messages.append({"role": msg['role'], "content": msg['content']})
                        
                        response = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=messages,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens
                        )
                        return response.choices[0].message.content.strip()
                        
                    elif self.client_type == 'anthropic':
                        # Anthropic Claude API
                        messages = []
                        
                        # Tambah riwayat chat jika ada
                        if chat_history:
                            for msg in chat_history[-5:]:
                                messages.append({"role": msg['role'], "content": msg['content']})
                        
                        # Tambah pesan saat ini
                        messages.append({"role": "user", "content": full_prompt})
                        
                        response = self.client.messages.create(
                            model=self.model_name,
                            max_tokens=min(self.max_tokens, 4096),
                            temperature=self.temperature,
                            system=system_prompt,
                            messages=messages
                        )
                        return response.content[0].text.strip()
                        
                    else:
                        # Google Gemini API
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=full_prompt
                        )
                        return response.text.strip()
                
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    # Cek apakah ini error sementara (503, overload, timeout)
                    is_temporary = any(x in err_str for x in ['503', 'UNAVAILABLE', 'overloaded', 'timeout', 'rate limit', '429', 'temporarily'])
                    if is_temporary and attempt < max_retries - 1:
                        # Tunggu sebentar lalu coba lagi (2s, 4s)
                        time.sleep(2 * (attempt + 1))
                        continue
                    break
            
            # Semua retry gagal
            err_str = str(last_error) if last_error else 'Unknown error'
            if '503' in err_str or 'UNAVAILABLE' in err_str or 'overloaded' in err_str:
                return "⚠️ Server AI sedang sibuk. Mohon coba lagi dalam 1-2 menit."
            return f"Maaf, terjadi kesalahan: {err_str}. Silakan coba lagi."
        
        except Exception as e:
            return f"Maaf, terjadi kesalahan: {str(e)}. Silakan coba lagi."
    
    def get_work_recommendation(self, user) -> str:
        """Dapatkan rekomendasi AI untuk pekerjaan hari ini.
        
        Mengirim pertanyaan ke AI tentang apa yang harus dikerjakan hari ini
        berdasarkan konteks task user.
        
        Args:
            user: User yang meminta rekomendasi
            
        Returns:
            String rekomendasi dari AI
        """
        prompt = "Berdasarkan daftar tugas saya, apa yang harus saya kerjakan hari ini? Berikan prioritas dan alasannya."
        return self.chat(user, prompt)


# ============================================================
# BACKWARD COMPATIBILITY: Alias class lama
# ============================================================

# GeminiService dan OpenClawService tetap tersedia sebagai alias
# agar kode lama yang mengimpornya tetap berjalan
GeminiService = AIService
OpenClawService = AIService


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def get_ai_service() -> AIService:
    """Factory function untuk mendapatkan instance AIService.
    
    Mengembalikan AIService yang sudah dikonfigurasi sesuai
    pengaturan provider di database.
    
    Returns:
        Instance AIService yang sudah diinisialisasi
        
    Raises:
        ValueError: Jika provider belum dikonfigurasi dengan benar
    """
    return AIService()


def get_ai_chat_service() -> AIChatService:
    """Factory function untuk mendapatkan instance AIChatService.
    
    Mengembalikan AIChatService yang sudah dikonfigurasi sesuai
    pengaturan provider di database.
    
    Returns:
        Instance AIChatService yang sudah diinisialisasi
        
    Raises:
        ValueError: Jika provider belum dikonfigurasi dengan benar
    """
    return AIChatService()
