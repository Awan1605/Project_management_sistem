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
        
        AI sering mengembalikan JSON dalam blok kode (``json ... ```).
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
    
    def chat(self, user, message: str, chat_history: List[Dict] = None) -> str:
        """Proses pesan chat dan kembalikan respons AI menggunakan RAG."""
        import logging
        logger = logging.getLogger(__name__)
        
        message_lower = message.lower()
        
        # Step 1: Intent Detection - SEMANTIC (bukan keyword matching)
        # Gunakan cosine similarity dengan contoh queries
        conversational_examples = [
            "hai", "hello", "terima kasih", "ok", "sip",
            "selamat pagi", "selamat siang", "selamat sore",
            "apa kabar", "how are you"
        ]
        
        # Cek apakah pesan sangat pendek (< 4 kata) dan mirip conversational
        words = message.split()
        if len(words) <= 4:
            # Untuk pesan pendek, cek similarity dengan conversational examples
            from .rag_knowledge import get_rag_knowledge_base
            rag_kb = get_rag_knowledge_base()
            
            if rag_kb:
                try:
                    # Generate embedding untuk user message
                    message_embedding = rag_kb._generate_embedding(message)
                    
                    # Hitung similarity dengan conversational examples
                    import numpy as np
                    max_similarity = 0
                    
                    for example in conversational_examples:
                        example_embedding = rag_kb._generate_embedding(example)
                        # Cosine similarity
                        similarity = np.dot(message_embedding, example_embedding) / (
                            np.linalg.norm(message_embedding) * np.linalg.norm(example_embedding)
                        )
                        max_similarity = max(max_similarity, similarity)
                    
                    # Jika similarity > 0.7, anggap conversational
                    is_conversational = max_similarity > 0.7
                    
                    logger.info(f"[AI Chat] Semantic similarity: {max_similarity:.3f} | Conversational: {is_conversational}")
                    
                except Exception as e:
                    logger.error(f"[AI Chat] Semantic intent detection failed: {e}")
                    # Fallback: always use RAG jika detection gagal
                    is_conversational = False
            else:
                # Jika RAG tidak tersedia, gunakan heuristic sederhana
                is_conversational = any(kw in message_lower for kw in conversational_examples)
        else:
            # Pesan panjang (> 4 kata) = selalu data query, gunakan RAG
            is_conversational = False

        # Step 2: RAG Context Retrieval
        context = ""
        if not is_conversational:
            try:
                from .rag_search import get_rag_search
                rag_search = get_rag_search()
                if rag_search:
                    context = rag_search.build_context(
                        query=message,
                        user=user,
                        max_results=5
                    )
                    logger.info(f"[AI Chat] RAG context retrieved: {len(context)} chars")
            except Exception as e:
                logger.error(f"[RAG] Context retrieval failed: {e}")
        
        # Step 3: Build prompt - DENGAN INSTRUKSI ANTI-HALLUCINATION
        if context:
            from django.utils import timezone
            today = timezone.localdate()
            
            # Format context menjadi lebih mudah dibaca AI
            user_prompt = f"""Pertanyaan user: {message}

TANGGAL HARI INI: {today} (JANGAN gunakan tanggal lain!)

Berikut adalah data tugas dan proyek user dari database:
{context}

PENTING - INSTRUKSI:
1. Jawab HANYA berdasarkan data di atas - JANGGAN buat data baru
2. JANGGAN pernah menyebutkan tanggal "asumsi" - gunakan TANGGAL HARI INI yang diberikan
3. Jika user bertanya tentang "tugas saya", HANYA tampilkan tugas dimana assignee = user yang login
4. Hitung dengan akurat berdasarkan data yang ada
5. JANGGAN mengatakan "dari X tugas yang terdaftar" jika data tidak menunjukkan jumlah pasti
6. Gunakan bahasa Indonesia
7. JANGGAN menambahkan informasi yang tidak ada di context

ATURAN PRIORITAS (untuk pertanyaan "apa yang harus dikerjakan" atau sejenisnya):
- PRIORITAS #1 (URGENT): Tugas yang SUDAH LEWAT DEADLINE dan statusnya belum Done
- PRIORITAS #2 (HIGH): Tugas yang deadline-nya dalam 3 hari ke depan
- PRIORITAS #3 (MEDIUM): Tugas yang statusnya To Do dengan deadline > 3 hari
- SANGAT DILARANG: Menampilkan tugas yang statusnya sudah Done - JANGGAN sebutkan sama sekali!

URUTAN JAWABAN:
1. Tampilkan HANYA tugas yang belum Done (To Do atau In Progress)
2. Urutkan dari yang paling urgent (overdue) ke yang kurang urgent
3. JANGGAN PERNAH menyebutkan tugas Done dalam jawaban - filter out sepenuhnya
4. Jelaskan MENGAPA tugas tertentu jadi prioritas (overdue, deadline dekat, dll)
5. Berikan rekomendasi tindakan yang jelas

ATURAN UNTUK PERTANYAAN TENTANG DOKUMEN/ATTACHMENT:
- Jika user bertanya tentang "dokumen", "file", "attachment", "lampiran" pada task tertentu
- Cek bagian "Attachments:" di context data
- Jika ada attachments, sebutkan SEMUA nama file dan detailnya
- Jika ada bagian "--- Content from [filename] ---", itu adalah ISI DOKUMEN yang sudah di-extract
- JAWAB pertanyaan user berdasarkan isi dokumen tersebut (summary, detail, spesifik info)
- Jika attachments "No attachments", beri tahu user bahwa task tersebut belum punya dokumen
- JANGGAN bilang "saya tidak bisa mengakses" - data sudah tersedia di context!

"""

        else:
            user_prompt = f"""User Question: {message}

The system has no relevant data for this query. Respond in Indonesian."""
        
        # Step 4: Call AI provider (single prompt, no system prompt)
        try:
            return self._call_ai_provider(user_prompt)
        except Exception as e:
            return f"Maaf, terjadi kesalahan: {str(e)}. Silakan coba lagi."
    
    def _call_ai_provider(self, prompt: str) -> str:
        """Call AI provider based on client type (without system prompt)"""
        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if self.client_type == 'openai':
                    return self._call_openai(prompt)
                elif self.client_type == 'anthropic':
                    return self._call_anthropic(prompt)
                else:
                    return self._call_gemini(prompt)
            except Exception as e:
                err_str = str(e)
                is_temporary = any(x in err_str for x in ['503', 'UNAVAILABLE', 'overloaded', 'timeout', 'rate limit', '429', 'temporarily'])
                if is_temporary and attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
    
    def _call_ai_provider_with_system(self, user_prompt: str, system_prompt: str) -> str:
        """Call AI provider with BOTH system prompt and user prompt"""
        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if self.client_type == 'openai':
                    return self._call_openai_with_system(user_prompt, system_prompt)
                elif self.client_type == 'anthropic':
                    return self._call_anthropic_with_system(user_prompt, system_prompt)
                else:
                    # Gemini doesn't have system prompt, prepend it to user prompt
                    full_prompt = f"{system_prompt}\n\n{user_prompt}"
                    return self._call_gemini(full_prompt)
            except Exception as e:
                err_str = str(e)
                is_temporary = any(x in err_str for x in ['503', 'UNAVAILABLE', 'overloaded', 'timeout', 'rate limit', '429', 'temporarily'])
                if is_temporary and attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI-compatible API"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content.strip()
    
    def _call_openai_with_system(self, user_prompt: str, system_prompt: str) -> str:
        """Call OpenAI-compatible API with system prompt"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content.strip()
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response.text.strip()
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude"""
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    
    def _call_anthropic_with_system(self, user_prompt: str, system_prompt: str) -> str:
        """Call Anthropic Claude with system prompt"""
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()
    
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
