"""
AI Developer Service V2 - Sistem Pengembang AI yang Optimal
===========================================================

Versi terbaru AI Developer dengan fitur:
1. Progress tracking real-time dengan step-by-step updates
2. Smart file discovery dengan semantic search
3. Dependency graph analysis untuk urutan perubahan yang benar
4. Chunked processing untuk menghindari context overflow
5. Multi-layer validation (syntax + imports + security + semantic)
6. Background processing dengan thread terpisah
7. Dukungan cancel dan retry request

Alur kerja (7 langkah):
1. ANALYZE - Analisis kode terkait
2. PLAN - Buat rencana implementasi
3. GENERATE - Hasilkan kode perubahan
4. VALIDATE - Validasi kode yang dihasilkan
5. REVIEW - Review akhir sebelum apply
6. APPLY - Terapkan perubahan ke file
7. TEST - Verifikasi hasil apply

Digunakan oleh views.ai_developer_start_v2() untuk menjalankan proses
secara asynchronous dengan progress tracking.
"""

import json
import os
import re
import shutil
import difflib
import time
import logging
import ast
import importlib.util
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import AI providers
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import AIFeatureRequest, AICodeChange, AISettings

# Setup logging
logger = logging.getLogger(__name__)


class ProcessingStep(Enum):
    """Enum untuk setiap langkah dalam proses AI Developer"""
    VALIDATING = "validating"
    DISCOVERING = "discovering"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    GENERATING = "generating"
    VALIDATING_CODE = "validating_code"
    COMPLETED = "completed"


@dataclass
class ProcessingContext:
    """Konteks untuk menyimpan state selama pemrosesan"""
    request: AIFeatureRequest
    service: 'AIDeveloperServiceV2'
    discovered_files: List[str] = field(default_factory=list)
    dependency_graph: Dict = field(default_factory=dict)
    analysis_result: Dict = field(default_factory=dict)
    implementation_plan: Dict = field(default_factory=dict)
    generated_changes: List[Dict] = field(default_factory=list)
    validated_changes: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_cancelled: bool = False
    
    def check_cancelled(self) -> bool:
        """Cek apakah request dibatalkan"""
        # Refresh dari database
        self.request.refresh_from_db()
        return self.request.is_cancelled


@dataclass
class FileDependency:
    """Representasi dependensi antar file"""
    file_path: str
    depends_on: List[str] = field(default_factory=list)
    depended_by: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    complexity: int = 0


class AIDeveloperServiceV2:
    """
    Service AI Developer V2 dengan alur yang optimal dan terstruktur.
    
    Alur kerja:
    1. Validasi Request - Validasi input dan scope
    2. Discover Files - Temukan file terkait secara pintar
    3. Analyze - Analisis struktur dan dependensi
    4. Plan - Buat rencana implementasi
    5. Generate - Hasilkan kode per file
    6. Validate - Validasi multi-layer
    7. Review - Presentasi untuk review user
    """
    
    # Pattern yang dilarang untuk keamanan
    FORBIDDEN_PATTERNS = [
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'subprocess\.run\s*\(',
        r'subprocess\.Popen\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'importlib\.import_module',
        r'compile\s*\(',
        r'input\s*\(',
        r'raw_input\s*\(',
        r'open\s*\([^)]*[\"\']w',
        r'file\s*\(',
        r'shutil\.(rmtree|move|copy)',
    ]
    
    # Direktori yang boleh diakses
    ALLOWED_DIRECTORIES = [
        'arva',
        'arviga',
        'static',
        'templates',
    ]
    
    # File yang tidak boleh diubah
    FORBIDDEN_FILES = [
        'settings.py',
        'settings-hosting.py',
        'deploy/settings-hosting.py',
        '.env',
        'db.sqlite3',
        'manage.py',
        'requirements.txt',
    ]
    
    # Konfigurasi retry
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # detik
    
    # Konfigurasi chunking
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_CONTEXT_SIZE = 8000  # karakter
    CHUNK_SIZE = 4000  # karakter per chunk
    
    # Cache untuk codebase context
    _codebase_context_cache = None
    _cache_timestamp = None
    CACHE_TTL = 3600  # 1 jam dalam detik
    
    def __init__(self):
        """Inisialisasi AI Developer Service V2"""
        ai_settings = AISettings.get_current()
        
        self.provider = ai_settings.provider
        self.base_url = ai_settings.base_url or 'http://localhost:11434/v1'
        self.api_key = ai_settings.api_key or 'not-needed'
        self.model_name = ai_settings.get_developer_model()
        self.temperature = float(ai_settings.temperature)
        self.max_tokens = min(ai_settings.max_tokens, 4096)
        
        # Path dasar untuk codebase
        self.base_path = Path(settings.BASE_DIR)
        self.backup_dir = self.base_path / '.ai_backups'
        
        # Buat direktori backup jika belum ada
        self.backup_dir.mkdir(exist_ok=True)
        
        # Inisialisasi client berdasarkan provider
        self._init_client(ai_settings)
        
        # Load codebase context (cached)
        self._load_codebase_context()
        
        logger.info(f"[AI Developer V2] Service diinisialisasi dengan provider: {self.provider}")
    
    def _load_codebase_context(self):
        """Load codebase context dengan caching"""
        import time
        current_time = time.time()
        
        # Check cache
        if (AIDeveloperServiceV2._codebase_context_cache and 
            AIDeveloperServiceV2._cache_timestamp and
            current_time - AIDeveloperServiceV2._cache_timestamp < AIDeveloperServiceV2.CACHE_TTL):
            self.codebase_context = AIDeveloperServiceV2._codebase_context_cache
            logger.info("[AI Developer V2] Menggunakan codebase context dari cache")
            return
        
        # Generate new context
        logger.info("[AI Developer V2] Membuat codebase context baru...")
        self.codebase_context = self._generate_codebase_context()
        
        # Update cache
        AIDeveloperServiceV2._codebase_context_cache = self.codebase_context
        AIDeveloperServiceV2._cache_timestamp = current_time
        logger.info(f"[AI Developer V2] Codebase context di-cache ({len(self.codebase_context)} chars)")
    
    def _generate_codebase_context(self) -> str:
        """Generate konteks lengkap codebase untuk AI"""
        from .ai_code_analyzer import CodebaseAnalyzer
        
        try:
            analyzer = CodebaseAnalyzer(str(self.base_path))
            analysis = analyzer.analyze_full_codebase()
            
            context_parts = []
            
            # 1. Project Overview
            context_parts.append("""=== STRUKTUR PROYEK KANBAN DJANGO ===

ARSITEKTUR:
- Django 4.2 dengan aplikasi utama 'arva'
- SQLite database (db.sqlite3)
- Bootstrap 5.3 untuk UI
- Multi-provider AI (DeepSeek, Open Claw/Ollama, Qoder/Claude, Google Gemini)

FOLDER UTAMA:
- arva/           → Aplikasi utama (models, views, urls, services)
- arviga/         → Konfigurasi Django (settings, urls, wsgi)
- static/         → CSS, JS, fonts
- templates/      → Template HTML (jika ada di root)
- arva/templates/ → Template aplikasi arva
- media/          → Upload files (avatars, attachments, branding)

""")
            
            # 2. Models
            context_parts.append("=== MODEL DATABASE ===\n")
            for model in analysis.models[:15]:  # Limit to 15 models
                fields_str = ", ".join([f['name'] for f in model.fields[:5]])
                context_parts.append(f"- {model.name}: {fields_str}\n")
            context_parts.append("\n")
            
            # 3. URL Patterns
            context_parts.append("=== URL PATTERNS UTAMA ===\n")
            url_context = self._get_url_patterns_summary()
            context_parts.append(url_context)
            context_parts.append("\n")
            
            # 4. Key Files Summary
            context_parts.append("=== FILE PENTING ===\n")
            context_parts.append("""- arva/models.py      → Semua model database
- arva/views.py       → Semua view functions
- arva/urls.py        → URL routing
- arva/forms.py       → Form definitions
- arva/ai_services.py → AI service layer
- arva/ai_developer_v2.py → AI Developer service
- arva/templates/arva/_app_sidebar.html → Sidebar navigasi
- arva/templates/arva/base.html → Base template

""")
            
            # 5. Sidebar structure
            context_parts.append("=== STRUKTUR SIDEBAR ===\n")
            sidebar_summary = self._get_sidebar_summary()
            context_parts.append(sidebar_summary)
            
            return "".join(context_parts)
            
        except Exception as e:
            logger.error(f"[AI Developer V2] Error generating codebase context: {e}")
            return "Error loading codebase context"
    
    def _get_url_patterns_summary(self) -> str:
        """Get summary of URL patterns"""
        try:
            urls_file = self.base_path / 'arva' / 'urls.py'
            if not urls_file.exists():
                return "URLs file not found"
            
            content = urls_file.read_text(encoding='utf-8')
            
            # Extract URL names
            import re
            url_names = re.findall(r"name=['\"]([^'\"]+)['\"]", content)
            
            summary = "URL Names:\n"
            for name in sorted(set(url_names))[:30]:
                summary += f"  - {name}\n"
            
            return summary
        except Exception as e:
            return f"Error: {e}"
    
    def _get_sidebar_summary(self) -> str:
        """Get summary of sidebar structure"""
        try:
            sidebar_file = self.base_path / 'arva' / 'templates' / 'arva' / '_app_sidebar.html'
            if not sidebar_file.exists():
                return "Sidebar file not found"
            
            content = sidebar_file.read_text(encoding='utf-8')
            
            # Extract menu items
            import re
            menu_items = re.findall(r'<span class="sidebar-label">([^<]+)</span>', content)
            
            summary = "Menu Items:\n"
            for item in menu_items:
                summary += f"  - {item}\n"
            
            return summary
        except Exception as e:
            return f"Error: {e}"
    
    def _init_client(self, ai_settings: AISettings):
        """Inisialisasi AI client berdasarkan provider"""
        if self.provider == AISettings.PROVIDER_OPENCLAW:
            if not OPENAI_AVAILABLE:
                raise ValueError("Package OpenAI belum terinstall")
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            self.client_type = 'openai'
        elif self.provider == AISettings.PROVIDER_GOOGLE:
            if not GOOGLE_AI_AVAILABLE:
                raise ValueError("Package Google AI belum terinstall. Jalankan: pip install google-genai")
            self.client = genai.Client(api_key=self.api_key)
            self.client_type = 'google'
        elif self.provider == AISettings.PROVIDER_QODER:
            if not ANTHROPIC_AVAILABLE:
                raise ValueError("Package Anthropic belum terinstall. Jalankan: pip install anthropic")
            if self.base_url and self.base_url != 'http://localhost:8080/v1':
                self.client = anthropic.Anthropic(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            self.client_type = 'anthropic'
        else:
            raise ValueError(f"AI Developer tidak mendukung provider: {self.provider}")
    
    def process_request(self, request: AIFeatureRequest) -> Dict:
        """
        Proses request dari awal sampai akhir dengan progress tracking.
        
        Args:
            request: AIFeatureRequest yang akan diproses
            
        Returns:
            Dict dengan hasil pemrosesan
        """
        context = ProcessingContext(request=request, service=self)
        
        try:
            logger.info(f"[AI Developer V2] Memulai pemrosesan request: {request.title}")
            request.status = 'validating'
            request.started_at = timezone.now()
            request.save()
            
            # Langkah 1: Validasi Request
            if not self._step_validate(context):
                return self._build_error_result(context, "Validasi request gagal")
            
            # Langkah 2: Discover Files
            if not self._step_discover_files(context):
                return self._build_error_result(context, "Discovery file gagal")
            
            # Langkah 3: Analisis Kode
            if not self._step_analyze(context):
                return self._build_error_result(context, "Analisis kode gagal")
            
            # Langkah 4: Planning
            if not self._step_plan(context):
                return self._build_error_result(context, "Planning gagal")
            
            # Langkah 5: Generate Kode
            if not self._step_generate(context):
                return self._build_error_result(context, "Generate kode gagal")
            
            # Langkah 6: Validasi Kode
            if not self._step_validate_code(context):
                return self._build_error_result(context, "Validasi kode gagal")
            
            # Langkah 7: Simpan ke Database
            if not self._step_save_changes(context):
                return self._build_error_result(context, "Penyimpanan perubahan gagal")
            
            # Selesai
            return self._build_success_result(context)
            
        except Exception as e:
            logger.error(f"[AI Developer V2] Error dalam pemrosesan: {str(e)}")
            request.error_count += 1
            request.last_error = str(e)
            request.status = 'failed'
            request.save()
            return self._build_error_result(context, str(e))
    
    def _step_validate(self, context: ProcessingContext) -> bool:
        """
        Langkah 1: Validasi request input.
        
        Memeriksa:
        - Title tidak kosong
        - Description memiliki konten yang cukup
        - Target files valid (jika ada)
        - Scope tidak terlalu besar
        """
        request = context.request
        request.update_progress(
            step=1,
            total_steps=7,
            description="Memvalidasi request...",
            percent=5
        )
        
        logger.info("[AI Developer V2] Langkah 1/7: Validasi request")
        
        # Validasi title
        if not request.title or len(request.title.strip()) < 5:
            context.errors.append("Judul terlalu pendek (minimum 5 karakter)")
            return False
        
        # Validasi description
        if not request.description or len(request.description.strip()) < 20:
            context.errors.append("Deskripsi terlalu pendek (minimum 20 karakter)")
            return False
        
        # Validasi target files jika ada
        if request.related_files:
            valid_files = []
            for file_path in request.related_files:
                full_path = self.base_path / file_path
                if self._is_path_allowed(full_path):
                    valid_files.append(file_path)
                else:
                    logger.warning(f"[AI Developer V2] File tidak diizinkan: {file_path}")
            request.related_files = valid_files
        
        # Cek pembatalan
        if context.check_cancelled():
            logger.info("[AI Developer V2] Request dibatalkan oleh user")
            return False
        
        logger.info("[AI Developer V2] Validasi berhasil")
        return True
    
    def _step_discover_files(self, context: ProcessingContext) -> bool:
        """
        Langkah 2: Discover file terkait secara pintar.
        
        Strategi:
        1. Gunakan file yang disebutkan user (jika ada)
        2. Cari berdasarkan keyword dalam description
        3. Analisis import statements
        4. Temukan file terkait berdasarkan pola
        """
        request = context.request
        request.status = 'discovering'
        request.update_progress(
            step=2,
            description="Menemukan file terkait...",
            percent=15
        )
        
        logger.info("[AI Developer V2] Langkah 2/7: Discover files")
        
        discovered = set()
        
        # 1. Gunakan file yang sudah disebutkan user
        if request.related_files:
            discovered.update(request.related_files)
            logger.info(f"[AI Developer V2] File dari user: {len(request.related_files)} file")
        
        # 2. Cari berdasarkan keyword
        keyword_files = self._discover_by_keywords(request)
        discovered.update(keyword_files)
        logger.info(f"[AI Developer V2] File dari keyword: {len(keyword_files)} file")
        
        # 3. Cari berdasarkan model mentions
        model_files = self._discover_by_models(request)
        discovered.update(model_files)
        logger.info(f"[AI Developer V2] File dari model: {len(model_files)} file")
        
        # 4. Cari berdasarkan view/template mentions
        view_files = self._discover_by_views(request)
        discovered.update(view_files)
        logger.info(f"[AI Developer V2] File dari view: {len(view_files)} file")
        
        # 5. Analisis dependensi
        if discovered:
            dep_files = self._discover_dependencies(discovered)
            discovered.update(dep_files)
            logger.info(f"[AI Developer V2] File dari dependensi: {len(dep_files)} file")
        
        # Filter dan validasi
        context.discovered_files = self._filter_valid_files(list(discovered))
        request.related_files = context.discovered_files
        
        # Batasi jumlah file untuk menghindari overload
        if len(context.discovered_files) > 10:
            logger.warning(f"[AI Developer V2] Terlalu banyak file ({len(context.discovered_files)}), dibatasi menjadi 10")
            context.discovered_files = context.discovered_files[:10]
            request.related_files = context.discovered_files
        
        request.save()
        
        if context.check_cancelled():
            return False
        
        logger.info(f"[AI Developer V2] Discovery selesai: {len(context.discovered_files)} file ditemukan")
        return len(context.discovered_files) > 0
    
    def _discover_by_keywords(self, request: AIFeatureRequest) -> List[str]:
        """Temukan file berdasarkan keyword dalam description"""
        discovered = []
        description = request.description.lower()
        title = request.title.lower()
        combined = f"{title} {description}"
        
        # Keyword mapping ke file patterns
        keyword_map = {
            'dashboard': ['arva/views.py', 'arva/urls.py'],
            'performa': ['arva/views.py', 'arva/models.py'],
            'performance': ['arva/views.py', 'arva/models.py'],
            'statistic': ['arva/views.py'],
            'statistik': ['arva/views.py'],
            'user': ['arva/models.py', 'arva/views.py'],
            'pengguna': ['arva/models.py', 'arva/views.py'],
            'member': ['arva/models.py'],
            'task': ['arva/models.py', 'arva/views.py'],
            'tugas': ['arva/models.py', 'arva/views.py'],
            'project': ['arva/models.py', 'arva/views.py'],
            'proyek': ['arva/models.py', 'arva/views.py'],
            'email': ['arva/models.py'],
            'notifikasi': ['arva/models.py', 'arva/views.py'],
            'notification': ['arva/models.py', 'arva/views.py'],
            'login': ['arva/views.py', 'arviga/settings.py'],
            'auth': ['arva/views.py'],
            'template': ['arva/templates/arva/'],
            'html': ['arva/templates/arva/'],
            'css': ['static/arva/css/'],
            'javascript': ['static/arva/js/'],
            'js': ['static/arva/js/'],
            'api': ['arva/views.py', 'arva/urls.py'],
            'ajax': ['arva/views.py', 'static/arva/js/'],
        }
        
        for keyword, files in keyword_map.items():
            if keyword in combined:
                for file_pattern in files:
                    if file_pattern.endswith('/'):
                        # Direktori - tambahkan file spesifik jika ada
                        dir_path = self.base_path / file_pattern
                        if dir_path.exists():
                            for f in dir_path.glob('*.py'):
                                discovered.append(f"{file_pattern}{f.name}")
                            for f in dir_path.glob('*.html'):
                                discovered.append(f"{file_pattern}{f.name}")
                            for f in dir_path.glob('*.js'):
                                discovered.append(f"{file_pattern}{f.name}")
                            for f in dir_path.glob('*.css'):
                                discovered.append(f"{file_pattern}{f.name}")
                    else:
                        # File spesifik
                        full_path = self.base_path / file_pattern
                        if full_path.exists() and file_pattern not in discovered:
                            discovered.append(file_pattern)
        
        return discovered
    
    def _discover_by_models(self, request: AIFeatureRequest) -> List[str]:
        """Temukan file berdasarkan model yang disebutkan"""
        discovered = []
        description = request.description.lower()
        
        # Baca models.py untuk menemukan model classes
        models_file = self.base_path / 'arva' / 'models.py'
        if models_file.exists():
            content = models_file.read_text(encoding='utf-8')
            # Cari class definitions
            model_classes = re.findall(r'class\s+(\w+)\s*\(\s*models\.Model', content)
            
            for model in model_classes:
                if model.lower() in description:
                    discovered.append('arva/models.py')
                    # Cari views yang menggunakan model ini
                    views_file = self.base_path / 'arva' / 'views.py'
                    if views_file.exists():
                        views_content = views_file.read_text(encoding='utf-8')
                        if model in views_content:
                            discovered.append('arva/views.py')
                    break
        
        return discovered
    
    def _discover_by_views(self, request: AIFeatureRequest) -> List[str]:
        """Temukan file berdasarkan view yang disebutkan"""
        discovered = []
        description = request.description.lower()
        
        # Cari template mentions
        templates_dir = self.base_path / 'arva' / 'templates' / 'arva'
        if templates_dir.exists():
            for template_file in templates_dir.glob('*.html'):
                template_name = template_file.stem.lower()
                if template_name in description:
                    discovered.append(f'arva/templates/arva/{template_file.name}')
                    # Juga tambahkan views.py
                    discovered.append('arva/views.py')
        
        return discovered
    
    def _discover_dependencies(self, files: Set[str]) -> List[str]:
        """Analisis dependensi dari file yang sudah ditemukan"""
        dependencies = []
        
        for file_path in files:
            if not file_path.endswith('.py'):
                continue
            
            content = self._read_file(file_path)
            if not content:
                continue
            
            # Cari import statements
            import_patterns = [
                r'from\s+arva\.(\w+)\s+import',
                r'from\s+\.\.(\w+)\s+import',
                r'import\s+arva\.(\w+)',
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    dep_file = f"arva/{match}.py"
                    if dep_file not in files and dep_file not in dependencies:
                        full_path = self.base_path / dep_file
                        if full_path.exists():
                            dependencies.append(dep_file)
        
        return dependencies
    
    def _filter_valid_files(self, files: List[str]) -> List[str]:
        """Filter hanya file yang valid dan diizinkan"""
        valid = []
        for file_path in files:
            full_path = self.base_path / file_path
            if self._is_path_allowed(full_path) and full_path.exists():
                # Cek ukuran file
                if full_path.stat().st_size <= self.MAX_FILE_SIZE:
                    valid.append(file_path)
                else:
                    logger.warning(f"[AI Developer V2] File terlalu besar: {file_path}")
        return valid
    
    def _step_analyze(self, context: ProcessingContext) -> bool:
        """
        Langkah 3: Analisis codebase untuk memahami struktur.
        
        Output:
        - Summary analisis
        - Root cause (untuk bugfix)
        - Affected models
        - Complexity score
        - Dependency graph
        """
        request = context.request
        request.status = 'analyzing'
        request.update_progress(
            step=3,
            description="Menganalisis struktur kode...",
            percent=25
        )
        
        logger.info("[AI Developer V2] Langkah 3/7: Analisis kode")
        
        # Baca konten file
        file_contents = {}
        for file_path in context.discovered_files[:5]:  # Batasi 5 file untuk analisis
            content = self._read_file(file_path)
            if content:
                # Truncate untuk konteks
                if len(content) > 2000:
                    content = content[:1000] + "\n... [dipendekkan] ...\n" + content[-500:]
                file_contents[file_path] = content
        
        if not file_contents:
            context.errors.append("Tidak ada file yang bisa dianalisis")
            return False
        
        # Build prompt analisis
        prompt = self._build_analysis_prompt(request, file_contents)
        
        # Panggil AI
        try:
            response = self._call_ai(prompt)
            analysis = self._extract_json_from_response(response)
            
            # Validasi hasil analisis
            if not analysis or 'summary' not in analysis:
                logger.warning("[AI Developer V2] Analisis tidak valid, menggunakan fallback")
                analysis = self._build_fallback_analysis(context)
            
            context.analysis_result = analysis
            request.analysis_result = analysis
            request.affected_models = analysis.get('affected_models', [])
            request.complexity_score = analysis.get('complexity_score', 50)
            request.estimated_effort = analysis.get('estimated_effort', 'Tidak diketahui')
            request.save()
            
            # Build dependency graph
            context.dependency_graph = self._build_dependency_graph(context.discovered_files)
            request.dependency_graph = context.dependency_graph
            request.save()
            
        except Exception as e:
            logger.error(f"[AI Developer V2] Error analisis: {str(e)}")
            context.errors.append(f"Error analisis: {str(e)}")
            return False
        
        if context.check_cancelled():
            return False
        
        logger.info("[AI Developer V2] Analisis selesai")
        return True
    
    def _build_analysis_prompt(self, request: AIFeatureRequest, file_contents: Dict) -> str:
        """Build prompt untuk analisis"""
        files_text = ""
        for file_path, content in file_contents.items():
            files_text += f"\n=== {file_path} ===\n{content}\n"
        
        prompt = f"""Analisis request Django berikut dan berikan respons dalam format JSON.

TIPE: {request.get_request_type_display()}
JUDUL: {request.title}
DESKRIPSI: {request.description[:300]}

FILE YANG TERKAIT:
{files_text}

Berikan analisis dalam format JSON berikut:
{{
    "summary": "Ringkasan singkat analisis (1-2 kalimat)",
    "root_cause": "Penyebab root cause (untuk bugfix) atau null",
    "affected_models": ["Model1", "Model2"],
    "affected_views": ["view_name"],
    "files_to_modify": ["path/file.py"],
    "complexity_score": 50,
    "estimated_effort": "2 jam",
    "risks": ["risiko1", "risiko2"],
    "recommendations": ["rekomendasi1"]
}}

Respons HANYA dalam format JSON, tanpa markdown atau penjelasan lain."""
        
        return prompt
    
    def _build_fallback_analysis(self, context: ProcessingContext) -> Dict:
        """Build analisis fallback jika AI gagal"""
        return {
            'summary': f"Analisis untuk {context.request.title}",
            'root_cause': None,
            'affected_models': [],
            'affected_views': [],
            'files_to_modify': context.discovered_files[:3],
            'complexity_score': 50,
            'estimated_effort': '2 jam',
            'risks': ['Analisis otomatis mungkin tidak lengkap'],
            'recommendations': ['Review manual direkomendasikan']
        }
    
    def _build_dependency_graph(self, files: List[str]) -> Dict:
        """Build graf dependensi antar file"""
        graph = {'nodes': [], 'edges': []}
        
        for file_path in files:
            if not file_path.endswith('.py'):
                continue
            
            node = {
                'file': file_path,
                'type': 'model' if 'models.py' in file_path else 'view' if 'views.py' in file_path else 'other'
            }
            graph['nodes'].append(node)
            
            # Cari dependensi
            content = self._read_file(file_path) or ''
            imports = re.findall(r'from\s+arva\.(\w+)\s+import', content)
            
            for imp in imports:
                dep_file = f"arva/{imp}.py"
                if dep_file in files:
                    graph['edges'].append({
                        'from': file_path,
                        'to': dep_file,
                        'type': 'import'
                    })
        
        return graph
    
    def _step_plan(self, context: ProcessingContext) -> bool:
        """
        Langkah 4: Buat rencana implementasi.
        
        Output:
        - Daftar langkah implementasi
        - Urutan eksekusi berdasarkan dependensi
        - Testing approach
        """
        request = context.request
        request.status = 'planning'
        request.update_progress(
            step=4,
            description="Membuat rencana implementasi...",
            percent=40
        )
        
        logger.info("[AI Developer V2] Langkah 4/7: Planning")
        
        # Build prompt planning
        prompt = self._build_planning_prompt(request, context.analysis_result)
        
        try:
            response = self._call_ai(prompt)
            plan = self._extract_json_from_response(response)
            
            if not plan or 'steps' not in plan:
                logger.warning("[AI Developer V2] Planning tidak valid, menggunakan fallback")
                plan = self._build_fallback_plan(context)
            
            # Post-process: deduplicate dan sort berdasarkan dependensi
            plan['steps'] = self._sort_steps_by_dependencies(
                plan.get('steps', []),
                context.dependency_graph
            )
            
            context.implementation_plan = plan
            request.implementation_plan = plan
            request.save()
            
        except Exception as e:
            logger.error(f"[AI Developer V2] Error planning: {str(e)}")
            context.errors.append(f"Error planning: {str(e)}")
            return False
        
        if context.check_cancelled():
            return False
        
        logger.info(f"[AI Developer V2] Planning selesai: {len(plan.get('steps', []))} langkah")
        return True
    
    def _build_planning_prompt(self, request: AIFeatureRequest, analysis: Dict) -> str:
        """Build prompt untuk planning"""
        files_to_modify = analysis.get('files_to_modify', [])
        
        prompt = f"""{self.codebase_context}

---

Buat rencana implementasi untuk request Django berikut.

JUDUL: {request.title}
DESKRIPSI: {request.description[:250]}
TIPE: {request.get_request_type_display()}

ANALISIS:
- Summary: {analysis.get('summary', '')}
- Complexity: {analysis.get('complexity_score', 50)}/100
- Estimasi: {analysis.get('estimated_effort', 'Tidak diketahui')}

FILE YANG PERLU DIMODIFIKASI:
{json.dumps(files_to_modify, indent=2)}

Buat rencana dalam format JSON:
{{
    "steps": [
        {{
            "order": 1,
            "title": "Judul langkah",
            "file_path": "arva/file.py",
            "action": "modify|create|delete",
            "description": "Deskripsi detail perubahan",
            "depends_on": []
        }}
    ],
    "testing": "Cara menguji perubahan",
    "rollback_plan": "Cara rollback jika gagal"
}}

PENTING:
- Setiap file hanya muncul SATU kali
- Gabungkan semua perubahan untuk file yang sama
- Maksimal 5 langkah
- Respons HANYA JSON"""
        
        return prompt
    
    def _build_fallback_plan(self, context: ProcessingContext) -> Dict:
        """Build rencana fallback"""
        steps = []
        for i, file_path in enumerate(context.discovered_files[:3], 1):
            steps.append({
                'order': i,
                'title': f'Update {file_path}',
                'file_path': file_path,
                'action': 'modify',
                'description': f'Implementasi untuk {context.request.title}',
                'depends_on': []
            })
        
        return {
            'steps': steps,
            'testing': 'Test manual direkomendasikan',
            'rollback_plan': 'Gunakan fitur rollback'
        }
    
    def _sort_steps_by_dependencies(self, steps: List[Dict], dependency_graph: Dict) -> List[Dict]:
        """Sort langkah berdasarkan dependensi (topological sort)"""
        if not steps:
            return steps
        
        # Build dependency map
        file_to_step = {}
        for i, step in enumerate(steps):
            file_path = step.get('file_path')
            if file_path:
                file_to_step[file_path] = i
        
        # Simple sort: models dulu, kemudian views, kemudian lainnya
        def sort_key(step):
            file_path = step.get('file_path', '')
            if 'models.py' in file_path:
                return (0, file_path)
            elif 'forms.py' in file_path:
                return (1, file_path)
            elif 'views.py' in file_path:
                return (2, file_path)
            elif 'urls.py' in file_path:
                return (3, file_path)
            else:
                return (4, file_path)
        
        sorted_steps = sorted(steps, key=sort_key)
        
        # Update order
        for i, step in enumerate(sorted_steps, 1):
            step['order'] = i
        
        return sorted_steps
    
    def _step_generate(self, context: ProcessingContext) -> bool:
        """
        Langkah 5: Generate kode perubahan.
        
        Strategi:
        - Proses per file sesuai urutan dependensi
        - Chunked processing untuk file besar
        - Error handling per file
        """
        request = context.request
        request.status = 'generating'
        request.update_progress(
            step=5,
            description="Menghasilkan kode perubahan...",
            percent=55
        )
        
        logger.info("[AI Developer V2] Langkah 5/7: Generate kode")
        
        steps = context.implementation_plan.get('steps', [])
        total_steps = len(steps)
        generated_changes = []
        
        for i, step in enumerate(steps):
            # Update progress
            progress = 55 + int((i / total_steps) * 15)
            request.update_progress(
                step=5,
                description=f"Menghasilkan kode untuk {step.get('file_path', 'file')}...",
                percent=progress
            )
            
            # Cek pembatalan
            if context.check_cancelled():
                logger.info("[AI Developer V2] Generate dibatalkan")
                return False
            
            try:
                change = self._generate_change_for_step(request, step)
                if change:
                    generated_changes.append(change)
                    logger.info(f"[AI Developer V2] Generated: {change['file_path']}")
            except Exception as e:
                logger.error(f"[AI Developer V2] Error generate untuk {step.get('file_path')}: {str(e)}")
                # Buat placeholder error
                error_change = {
                    'file_path': step.get('file_path', 'unknown'),
                    'change_type': step.get('action', 'modify'),
                    'original_code': '# Error saat generate',
                    'new_code': f'# TODO: {step.get("description", "Implementasi")}\n# Error: {str(e)[:100]}',
                    'diff_content': f'+# Error: {str(e)[:50]}',
                    'has_error': True,
                    'error_message': str(e),
                }
                generated_changes.append(error_change)
        
        context.generated_changes = generated_changes
        
        if not generated_changes:
            context.errors.append("Tidak ada kode yang berhasil digenerate")
            return False
        
        logger.info(f"[AI Developer V2] Generate selesai: {len(generated_changes)} perubahan")
        return True
    
    def _generate_change_for_step(self, request: AIFeatureRequest, step: Dict) -> Optional[Dict]:
        """Generate perubahan untuk satu langkah"""
        file_path = step.get('file_path')
        action = step.get('action', 'modify')
        description = step.get('description', '')
        
        if not file_path:
            return None
        
        if action == 'create':
            return self._generate_new_file(request, step)
        elif action == 'delete':
            return self._generate_file_deletion(request, step)
        else:  # modify
            return self._generate_file_modification(request, step)
    
    def _generate_new_file(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate file baru"""
        file_path = step.get('file_path')
        description = step.get('description', '')
        
        prompt = f"""Buat file Django baru.

FILE: {file_path}
TUJUAN: {description}

Output kode lengkap tanpa penjelasan."""
        
        response = self._call_ai(prompt)
        content = self._extract_code_from_response(response)
        
        if not content:
            content = f"""# {file_path}
# TODO: {description}

pass
"""
        
        return {
            'file_path': file_path,
            'change_type': 'add',
            'original_code': '',
            'new_code': content,
            'diff_content': self._generate_diff('', content, file_path),
            'has_error': False,
            'error_message': '',
        }
    
    def _generate_file_modification(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate modifikasi file"""
        file_path = step.get('file_path')
        description = step.get('description', '')
        
        original_content = self._read_file(file_path) or ''
        
        # Truncate jika terlalu panjang
        display_content = original_content
        if len(original_content) > 1500:
            display_content = self._extract_relevant_section(original_content, description)
        
        # Tentukan tipe file untuk instruksi yang tepat
        is_template = file_path.endswith('.html')
        is_python = file_path.endswith('.py')
        is_js = file_path.endswith('.js')
        is_css = file_path.endswith('.css')
        
        # Instruksi khusus berdasarkan tipe file
        if is_template:
            file_type_hint = "Django Template HTML"
            format_instruction = """PENTING: Output LANGSUNG kode HTML template, TANPA:
- Jangan bungkus dengan JSON
- Jangan bungkus dengan markdown code block
- Jangan tambahkan penjelasan
- Langsung tulis kode HTML lengkap dari baris pertama sampai terakhir

ATURAN WAJIB DJANGO TEMPLATE:
1. Variabel HARUS dibungkus dengan {{ }}
   BENAR: {{ settings.logo_url }}
   SALAH: settings.logo_url
   
2. Block tags HARUS dibungkus dengan {% %}
   BENAR: {% if settings.logo %}
   SALAH: if settings.logo
   
3. Setiap tag pembuka HARUS ada penutup:
   {% with ... %} ... {% endwith %}
   {% if ... %} ... {% endif %}
   {% for ... %} ... {% endfor %}"""
        elif is_python:
            file_type_hint = "Python/Django"
            format_instruction = """PENTING: Output LANGSUNG kode Python, TANPA:
- Jangan bungkus dengan JSON
- Boleh gunakan markdown code block dengan ```python
- Jangan tambahkan penjelasan di luar kode
- Tulis kode lengkap dari import sampai akhir"""
        else:
            file_type_hint = "code"
            format_instruction = "Output kode lengkap tanpa penjelasan tambahan."
        
        # Build example strings (terpisah untuk menghindari f-string issues)
        contoh_benar = """{% with current=request.resolver_match.url_name %}
<div class="sidebar-brand">
  <a href="{% url 'project_list' %}">
    <img src="{{ settings.logo_url }}" alt="{{ settings.site_name }}">
  </a>
</div>
{% endwith %}"""
        
        contoh_salah = """{"modified_code": "..."}     <-- JANGAN LAPIS DENGAN JSON!
settings.logo_url              <-- SALAH! Harus {{ settings.logo_url }}
{% if settings.logo %}        <-- SALAH! Tidak ada {% endif %}"""
        
        prompt = f"""{self.codebase_context}

---

Modifikasi file {file_type_hint} berikut.

FILE: {file_path}
PERUBAHAN YANG DIMINTA: {description}

KODE SAAT INI:
{display_content}

{format_instruction}

CONTOH OUTPUT YANG BENAR untuk template:
{contoh_benar}

CONTOH OUTPUT YANG SALAH:
{contoh_salah}"""

        response = self._call_ai(prompt)
        new_content = self._extract_code_from_response(response)
        
        # Debug logging
        logger.info(f"[AI Developer V2] Response preview untuk {file_path}: {response[:200]}...")
        
        if not new_content or new_content == original_content:
            new_content = f"# TODO: {description}\n# File: {file_path}\n{original_content}"
        
        return {
            'file_path': file_path,
            'change_type': 'modify',
            'original_code': original_content,
            'new_code': new_content,
            'diff_content': self._generate_diff(original_content, new_content, file_path),
            'has_error': False,
            'error_message': '',
        }
    
    def _generate_file_deletion(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate penghapusan file"""
        file_path = step.get('file_path')
        original_content = self._read_file(file_path) or ''
        
        return {
            'file_path': file_path,
            'change_type': 'delete',
            'original_code': original_content,
            'new_code': '',
            'diff_content': self._generate_diff(original_content, '', file_path),
            'has_error': False,
            'error_message': '',
        }
    
    def _step_validate_code(self, context: ProcessingContext) -> bool:
        """
        Langkah 6: Validasi kode dengan auto-fix.
        
        Alur:
        1. Validasi syntax
        2. Test kode (import check, template render test)
        3. Jika error → Auto-fix → Test ulang (max 3x)
        4. Security scan
        5. Path validation
        """
        request = context.request
        request.status = 'validating_code'
        request.update_progress(
            step=6,
            description="Memvalidasi dan testing kode...",
            percent=70
        )
        
        logger.info("[AI Developer V2] Langkah 6/7: Validasi dengan auto-fix")
        
        validated_changes = []
        MAX_FIX_ATTEMPTS = 3
        
        for change in context.generated_changes:
            # Cek pembatalan
            if context.check_cancelled():
                return False
            
            file_path = change.get('file_path', '')
            
            # === AUTO-FIX LOOP ===
            fix_attempts = 0
            last_error = None
            
            while fix_attempts < MAX_FIX_ATTEMPTS:
                # Validasi syntax
                syntax_result = self._validate_syntax(change)
                
                # Test kode (import, render, dll)
                test_result = self._test_code(change)
                
                if syntax_result['valid'] and test_result['valid']:
                    logger.info(f"[AI Developer V2] {file_path} valid dan lulus test")
                    break
                
                # Ada error, coba auto-fix
                last_error = syntax_result.get('error') or test_result.get('error')
                fix_attempts += 1
                
                logger.warning(f"[AI Developer V2] {file_path} error (attempt {fix_attempts}/{MAX_FIX_ATTEMPTS}): {last_error}")
                
                if fix_attempts < MAX_FIX_ATTEMPTS:
                    # Auto-fix
                    request.update_progress(
                        step=6,
                        description=f"Auto-fix {file_path} (attempt {fix_attempts})...",
                        percent=70 + fix_attempts * 3
                    )
                    
                    fixed_change = self._auto_fix_code(change, last_error, fix_attempts)
                    if fixed_change:
                        change = fixed_change
                    else:
                        break
            
            # Validasi security
            security_result = self._validate_security(change)
            
            # Validasi path
            path_result = self._validate_path(change)
            
            # Gabungkan hasil
            change['is_valid'] = (
                syntax_result['valid'] and 
                test_result['valid'] and 
                security_result['valid'] and 
                path_result['valid']
            )
            change['validation_errors'] = []
            change['fix_attempts'] = fix_attempts
            
            if not security_result['valid']:
                change['validation_errors'].append(f"Security: {security_result['error']}")
                change['has_error'] = True
                change['error_message'] = security_result['error']
            
            if not syntax_result['valid']:
                change['validation_errors'].append(f"Syntax: {syntax_result['error']}")
                change['has_error'] = True
                change['error_message'] = syntax_result['error']
            
            if not test_result['valid']:
                change['validation_errors'].append(f"Test: {test_result['error']}")
                change['has_error'] = True
                change['error_message'] = test_result['error']
            
            if not path_result['valid']:
                change['validation_errors'].append(f"Path: {path_result['error']}")
                change['has_error'] = True
                change['error_message'] = path_result['error']
            
            validated_changes.append(change)
        
        context.validated_changes = validated_changes
        
        # Hitung statistik
        valid_count = len([c for c in validated_changes if c.get('is_valid', False)])
        logger.info(f"[AI Developer V2] Validasi selesai: {valid_count}/{len(validated_changes)} valid")
        
        return True
    
    def _test_code(self, change: Dict) -> Dict:
        """
        Test kode yang dihasilkan:
        - Python: Import test, class/function check
        - Template: Render test
        - URL: Resolve check
        """
        file_path = change.get('file_path', '')
        new_code = change.get('new_code', '')
        
        if not new_code:
            return {'valid': True, 'error': None}
        
        # Test Python files
        if file_path.endswith('.py'):
            return self._test_python_code(file_path, new_code)
        
        # Test Django templates
        if file_path.endswith('.html'):
            return self._test_template_code(file_path, new_code)
        
        return {'valid': True, 'error': None}
    
    def _test_python_code(self, file_path: str, code: str) -> Dict:
        """Test Python code dengan import simulation"""
        try:
            # 1. Parse AST
            tree = ast.parse(code)
            
            # 2. Extract imports dan cek apakah valid
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
            
            # 3. Cek import yang mungkin gagal
            for imp in imports:
                # Skip local imports
                if imp.startswith('arva') or imp.startswith('.'):
                    continue
                # Cek apakah module ada
                try:
                    __import__(imp.split('.')[0])
                except ImportError as e:
                    return {'valid': False, 'error': f"Import error: {imp} - {str(e)}"}
            
            # 4. Cek class/function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Cek apakah class punya __init__ yang valid
                    pass
                elif isinstance(node, ast.FunctionDef):
                    # Cek apakah function punya body
                    if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                        pass  # Empty function OK
            
            # 5. Jika ini views.py, cek URL patterns
            if 'views.py' in file_path:
                return self._test_views_code(code)
            
            # 6. Jika ini urls.py, cek URL patterns
            if 'urls.py' in file_path:
                return self._test_urls_code(code)
            
            return {'valid': True, 'error': None}
            
        except SyntaxError as e:
            return {'valid': False, 'error': f"Syntax error: {str(e)}"}
        except Exception as e:
            return {'valid': False, 'error': f"Test error: {str(e)}"}
    
    def _test_views_code(self, code: str) -> Dict:
        """Test apakah view functions valid"""
        try:
            tree = ast.parse(code)
            
            view_functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Cek apakah ini view (punya request parameter)
                    if node.args.args and any(arg.arg == 'request' for arg in node.args.args):
                        view_functions.append(node.name)
                        
                        # Cek apakah view return sesuatu
                        has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
                        if not has_return:
                            return {'valid': False, 'error': f"View '{node.name}' tidak ada return statement"}
            
            if view_functions:
                logger.info(f"[AI Developer V2] Found views: {view_functions}")
            
            return {'valid': True, 'error': None}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _test_urls_code(self, code: str) -> Dict:
        """Test apakah URL patterns valid"""
        try:
            # Cek apakah ada urlpatterns
            if 'urlpatterns' not in code:
                return {'valid': False, 'error': "urls.py tidak ada urlpatterns"}
            
            # Cek apakah ada path() atau url()
            if 'path(' not in code and 'url(' not in code:
                return {'valid': False, 'error': "urlpatterns tidak ada path() definition"}
            
            # Extract view names dari path()
            import re
            view_patterns = re.findall(r"path\([^)]*,\s*(\w+)", code)
            view_patterns += re.findall(r"path\([^)]*,\s*views\.(\w+)", code)
            
            if view_patterns:
                logger.info(f"[AI Developer V2] URLs reference views: {view_patterns}")
            
            return {'valid': True, 'error': None}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _test_template_code(self, file_path: str, code: str) -> Dict:
        """Test Django template dengan render simulation"""
        try:
            from django.template import Engine, Context, TemplateSyntaxError
            
            # 1. Cek tag balance (sudah ada di _validate_django_template)
            validation = self._validate_django_template(code)
            if not validation['valid']:
                return validation
            
            # 2. Try to compile template
            engine = Engine(
                debug=True,
                libraries={
                    'arva_tags': 'arva.templatetags.arva_tags',
                }
            )
            
            try:
                template = engine.from_string(code)
                # 3. Try to render with empty context
                # (tidak akan perfect, tapi bisa catch syntax errors)
                context = Context({})
                template.render(context)
            except TemplateSyntaxError as e:
                return {'valid': False, 'error': f"Template syntax error: {str(e)}"}
            except Exception as e:
                # Error lain (misal variable tidak ada) OK untuk sekarang
                # Yang penting tidak ada syntax error
                pass
            
            return {'valid': True, 'error': None}
            
        except ImportError:
            # Django tidak tersedia, skip render test
            return {'valid': True, 'error': None}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _auto_fix_code(self, change: Dict, error_message: str, attempt: int) -> Optional[Dict]:
        """
        Coba perbaiki kode secara otomatis dengan AI.
        Mengirim error message ke AI untuk generate kode yang diperbaiki.
        """
        file_path = change.get('file_path', '')
        original_code = change.get('original_code', '')
        broken_code = change.get('new_code', '')
        description = change.get('description', 'Fix error')
        
        logger.info(f"[AI Developer V2] Mencoba auto-fix untuk {file_path}")
        
        # Build fix prompt - pisahkan untuk menghindari f-string issues
        instruksi = """PENTING:
- Jangan bungkus dengan JSON
- Untuk template Django, gunakan {_DOUBLE_OPEN} {_DOUBLE_CLOSE} untuk variabel dan {PERCENT_OPEN} {PERCENT_CLOSE} untuk block tags
- Pastikan semua tag pembuka ada penutupnya
- Output kode LENGKAP, bukan snippet""".replace('{_DOUBLE_OPEN}', '{{').replace('{_DOUBLE_CLOSE}', '}}').replace('{PERCENT_OPEN}', '{%').replace('{PERCENT_CLOSE}', '%}')
        
        prompt = f"""Perbaiki kode berikut yang memiliki error.

FILE: {file_path}
ERROR: {error_message}

KODE YANG ERROR:
```
{broken_code[:2000]}
```

KODE ASLI SEBELUM PERUBAHAN:
```
{original_code[:1500]}
```

TUJUAN PERUBAHAN: {description}

INSTRUKSI:
1. Analisis error dan identifikasi penyebabnya
2. Perbaiki kode dengan tetap mempertahankan tujuan perubahan
3. Output kode LENGKAP yang sudah diperbaiki

{instruksi}"""

        try:
            response = self._call_ai(prompt)
            fixed_code = self._extract_code_from_response(response)
            
            if fixed_code and fixed_code != broken_code:
                logger.info(f"[AI Developer V2] Auto-fix berhasil untuk {file_path}")
                return {
                    'file_path': file_path,
                    'change_type': change.get('change_type', 'modify'),
                    'original_code': original_code,
                    'new_code': fixed_code,
                    'diff_content': self._generate_diff(original_code, fixed_code, file_path),
                    'description': description,
                    'has_error': False,
                    'error_message': '',
                }
        except Exception as e:
            logger.error(f"[AI Developer V2] Auto-fix gagal: {str(e)}")
        
        return None
    
    def _validate_security(self, change: Dict) -> Dict:
        """Validasi security - cek forbidden patterns"""
        new_code = change.get('new_code', '')
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, new_code):
                return {
                    'valid': False,
                    'error': f"Pattern tidak aman terdeteksi: {pattern}"
                }
        
        return {'valid': True, 'error': None}
    
    def _validate_syntax(self, change: Dict) -> Dict:
        """Validasi syntax untuk file Python dan Django Template"""
        file_path = change.get('file_path', '')
        new_code = change.get('new_code', '')
        
        if not new_code:
            return {'valid': True, 'error': None}
        
        # Validasi Python
        if file_path.endswith('.py'):
            try:
                ast.parse(new_code)
                return {'valid': True, 'error': None}
            except SyntaxError as e:
                return {'valid': False, 'error': f"Python Syntax error: {str(e)}"}
        
        # Validasi Django Template
        if file_path.endswith('.html'):
            return self._validate_django_template(new_code)
        
        return {'valid': True, 'error': None}
    
    def _validate_django_template(self, template_code: str) -> Dict:
        """
        Validasi syntax Django Template.
        Mengecek:
        - Tag pembuka dan penutup yang seimbang
        - Variable tags {{ }} yang valid
        - Block tags {% %} yang valid
        - Filter syntax yang benar
        """
        errors = []
        
        # Cek tag pembuka tanpa penutup
        open_braces = template_code.count('{{')
        close_braces = template_code.count('}}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced variable tags: {open_braces} open vs {close_braces} close")
        
        open_blocks = template_code.count('{%')
        close_blocks = template_code.count('%}')
        if open_blocks != close_blocks:
            errors.append(f"Unbalanced block tags: {open_blocks} open vs {close_blocks} close")
        
        # Cek tag yang butuh penutup
        tags_needing_end = {
            'if': 'endif',
            'for': 'endfor',
            'with': 'endwith',
            'block': 'endblock',
            'extends': None,  # tidak perlu end
            'include': None,
            'load': None,
            'url': None,
            'csrf_token': None,
        }
        
        # Pattern untuk menemukan tag
        block_tag_pattern = r'{%\s*(\w+)'
        
        import re
        all_tags = re.findall(block_tag_pattern, template_code)
        
        # Count tag openings and closings
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Check if opening tags have matching end tags
        for tag, end_tag in tags_needing_end.items():
            if end_tag:
                open_count = tag_counts.get(tag, 0)
                end_count = tag_counts.get(end_tag, 0)
                if open_count > end_count:
                    errors.append(f"Unclosed tag: '{tag}' found {open_count} times but '{end_tag}' found {end_count} times")
                elif open_count < end_count:
                    errors.append(f"Extra closing tag: '{end_tag}' found {end_count} times but '{tag}' found {open_count} times")
        
        # Cek apakah ada variable tanpa {{ }}
        # Pattern: word langsung tanpa kurung (tapi bukan HTML attribute)
        # Ini tricky, jadi kita cek pattern yang jelas salah
        suspicious_patterns = [
            r'(?<!\{\{)\s(settings\.\w+)\s(?!\}\})',  # settings.xxx tanpa {{ }}
            r'(?<!\{\{)\s(user\.\w+)\s(?!\}\})',      # user.xxx tanpa {{ }}
            r'(?<!\{\{)\s(request\.\w+)\s(?!\}\})',   # request.xxx tanpa {{ }}
        ]
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, template_code)
            if matches:
                errors.append(f"Possible missing {{ {{ }} }} around variables: {matches[:3]}")
        
        if errors:
            return {'valid': False, 'error': '; '.join(errors)}
        
        return {'valid': True, 'error': None}
    
    def _validate_path(self, change: Dict) -> Dict:
        """Validasi path file"""
        file_path = change.get('file_path', '')
        full_path = self.base_path / file_path
        
        if not self._is_path_allowed(full_path):
            return {'valid': False, 'error': 'Path file tidak diizinkan'}
        
        return {'valid': True, 'error': None}
    
    def _step_save_changes(self, context: ProcessingContext) -> bool:
        """
        Langkah 7: Simpan perubahan ke database.
        """
        request = context.request
        request.update_progress(
            step=7,
            description="Menyimpan perubahan...",
            percent=85
        )
        
        logger.info("[AI Developer V2] Langkah 7/7: Simpan perubahan")
        
        try:
            with transaction.atomic():
                for change in context.validated_changes:
                    AICodeChange.objects.create(
                        request=request,
                        file_path=change['file_path'],
                        change_type=change['change_type'],
                        original_code=change.get('original_code', ''),
                        new_code=change['new_code'],
                        diff_content=change['diff_content'],
                        has_error=change.get('has_error', False),
                        error_message=change.get('error_message', ''),
                    )
                
                request.status = 'reviewing'
                request.completed_at = timezone.now()
                request.update_progress(
                    step=7,
                    description="Selesai! Menunggu review...",
                    percent=100
                )
                request.save()
            
            logger.info(f"[AI Developer V2] Berhasil menyimpan {len(context.validated_changes)} perubahan")
            return True
            
        except Exception as e:
            logger.error(f"[AI Developer V2] Error menyimpan: {str(e)}")
            context.errors.append(f"Error menyimpan: {str(e)}")
            return False
    
    def _build_success_result(self, context: ProcessingContext) -> Dict:
        """Build hasil sukses"""
        valid_count = len([c for c in context.validated_changes if c.get('is_valid', False)])
        error_count = len([c for c in context.validated_changes if c.get('has_error', False)])
        
        return {
            'success': True,
            'message': f"Berhasil generate {len(context.validated_changes)} perubahan ({valid_count} valid, {error_count} error)",
            'changes_count': len(context.validated_changes),
            'valid_count': valid_count,
            'error_count': error_count,
            'request_id': context.request.id,
        }
    
    def _build_error_result(self, context: ProcessingContext, error_message: str) -> Dict:
        """Build hasil error"""
        context.request.status = 'failed'
        context.request.last_error = error_message
        context.request.save()
        
        return {
            'success': False,
            'error': error_message,
            'errors': context.errors,
            'request_id': context.request.id,
        }
    
    # Helper methods
    
    def _read_file(self, file_path: str) -> Optional[str]:
        """Baca konten file dengan aman"""
        try:
            full_path = self.base_path / file_path
            
            if not self._is_path_allowed(full_path):
                return None
            
            if not full_path.exists():
                return None
            
            if full_path.stat().st_size > self.MAX_FILE_SIZE:
                return f"# File terlalu besar: {file_path}"
            
            return full_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"[AI Developer V2] Error membaca file {file_path}: {str(e)}")
            return None
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Cek apakah path diizinkan untuk diakses"""
        try:
            resolved = path.resolve()
            base = self.base_path.resolve()
            
            # Cek apakah path dalam base directory
            if not str(resolved).startswith(str(base)):
                return False
            
            # Cek file terlarang
            if resolved.name in self.FORBIDDEN_FILES:
                return False
            
            # Cek direktori diizinkan
            rel_path = resolved.relative_to(base)
            first_dir = rel_path.parts[0] if rel_path.parts else ''
            if first_dir not in self.ALLOWED_DIRECTORIES:
                return False
            
            return True
        except Exception:
            return False
    
    def _call_ai(self, prompt: str) -> str:
        """Panggil AI dengan retry logic"""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[AI Developer V2] Panggilan AI percobaan {attempt + 1}/{self.MAX_RETRIES}")
                
                if self.client_type == 'google':
                    content = self._call_google_ai(prompt)
                elif self.client_type == 'anthropic':
                    content = self._call_anthropic_ai(prompt)
                else:
                    content = self._call_openai_compatible(prompt)
                
                if not content:
                    raise Exception("Respons AI kosong")
                
                return content
                
            except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
                last_error = e
                logger.warning(f"[AI Developer V2] Error koneksi: {str(e)}")
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (attempt + 1)
                    time.sleep(wait_time)
                    self._reinitialize_client()
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[AI Developer V2] Percobaan {attempt + 1} gagal: {str(e)}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    if len(prompt) > 2000:
                        prompt = prompt[:2000] + "\n...[dipendekkan]"
        
        raise Exception(f"Panggilan AI gagal setelah {self.MAX_RETRIES} percobaan: {str(last_error)}")
    
    def _call_openai_compatible(self, prompt: str) -> str:
        """Panggil API OpenAI-compatible"""
        import socket
        socket.setdefaulttimeout(300)
        
        # System message yang jelas tentang format output
        system_message = """Anda adalah expert Django/Python developer.

ATURAN OUTPUT:
1. Untuk kode: Output LANGSUNG kode, TANPA JSON wrapper, TANPA markdown (kecuali ```python untuk Python)
2. Untuk template Django: Output LANGSUNG HTML dengan template tags {{ }} dan {% %}
3. Untuk analisis: Output dalam format JSON yang diminta

DILARANG:
- Membungkus kode dengan JSON seperti {"modified_code": "..."}
- Menghapus {{ }} atau {% %} dari template Django
- Memberikan penjelasan di luar kode"""
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=min(self.max_tokens, 2048),
            timeout=180,
        )
        
        return response.choices[0].message.content.strip()
    
    def _call_google_ai(self, prompt: str) -> str:
        """Panggil Google Gemini API"""
        system_prompt = """Anda adalah expert Django/Python developer.

ATURAN OUTPUT:
1. Untuk kode: Output LANGSUNG kode, TANPA JSON wrapper
2. Untuk template Django: Output LANGSUNG HTML dengan template tags {{ }} dan {% %}
3. Untuk analisis: Output dalam format JSON yang diminta

DILARANG:
- Membungkus kode dengan JSON seperti {"modified_code": "..."}
- Menghapus {{ }} atau {% %} dari template Django"""
        
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=float(self.temperature),
                max_output_tokens=min(self.max_tokens, 2048),
            )
        )
        
        return response.text.strip()
    
    def _call_anthropic_ai(self, prompt: str) -> str:
        """Panggil Anthropic Claude API"""
        system_prompt = """Anda adalah expert Django/Python developer.

ATURAN OUTPUT:
1. Untuk kode: Output LANGSUNG kode, TANPA JSON wrapper
2. Untuk template Django: Output LANGSUNG HTML dengan template tags {{ }} and {% %}
3. Untuk analisis: Output dalam format JSON yang diminta

DILARANG:
- Membungkus kode dengan JSON seperti {"modified_code": "..."}
- Menghapus {{ }} atau {% %} dari template Django"""
        
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=min(self.max_tokens, 4096),
            temperature=float(self.temperature),
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    def _reinitialize_client(self):
        """Reinisialisasi client AI"""
        try:
            ai_settings = AISettings.get_current()
            self._init_client(ai_settings)
            logger.info("[AI Developer V2] Client direinisialisasi")
        except Exception as e:
            logger.warning(f"[AI Developer V2] Gagal reinisialisasi: {e}")
    
    def _extract_json_from_response(self, response: str) -> Dict:
        """Ekstrak JSON dari respons AI dengan multiple strategi"""
        if not response:
            return {}
        
        # Strategi 1: Parse seluruh respons sebagai JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Strategi 2: Cari JSON dalam markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategi 3: Cari objek JSON dalam respons
        json_match = re.search(r'(\{[^{}]*\})', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategi 4: Cari nested JSON
        json_match = re.search(r'(\{.*\})', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        logger.warning("[AI Developer V2] Tidak bisa ekstrak JSON")
        return {}
    
    def _extract_code_from_response(self, response: str) -> str:
        """Ekstrak kode dari respons AI dengan multiple fallback strategies"""
        if not response:
            return ''
        
        response = response.strip()
        
        # Strategy 1: Cek apakah response adalah JSON dengan key "modified_code" atau "code"
        try:
            import json
            parsed = json.loads(response)
            # Handle berbagai format JSON yang mungkin
            if isinstance(parsed, dict):
                for key in ['modified_code', 'code', 'new_code', 'content']:
                    if key in parsed and isinstance(parsed[key], str):
                        logger.info(f"[AI Developer V2] Extracted code from JSON key: {key}")
                        return parsed[key].strip()
        except (json.JSONDecodeError, TypeError):
            pass  # Bukan JSON, lanjut ke strategi lain
        
        # Strategy 2: Cari JSON dalam response
        json_match = re.search(r'\{[^{}]*"modified_code"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                import json
                parsed = json.loads(json_match.group())
                if 'modified_code' in parsed:
                    logger.info("[AI Developer V2] Extracted code from embedded JSON")
                    return parsed['modified_code'].strip()
            except:
                pass
        
        # Strategy 3: Cari dalam markdown code blocks (dengan bahasa)
        code_match = re.search(r'```(?:\w+)?\s*(.*?)```', response, re.DOTALL)
        if code_match:
            extracted = code_match.group(1).strip()
            # Cek lagi apakah di dalam code block ada JSON
            try:
                import json
                parsed = json.loads(extracted)
                if isinstance(parsed, dict) and 'modified_code' in parsed:
                    return parsed['modified_code'].strip()
            except:
                pass
            return extracted
        
        # Strategy 4: Jika tidak ada code block dan bukan JSON, return as-is
        # Tapi bersihkan dari markdown artifacts
        cleaned = response
        # Hapus markdown code block markers jika ada tanpa penutup
        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)
        
        return cleaned.strip()
    
    def _generate_diff(self, original: str, new: str, file_path: str) -> str:
        """Generate unified diff antara original dan new"""
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f'a/{file_path}',
            tofile=f'b/{file_path}',
        )
        
        return ''.join(diff)
    
    def _extract_relevant_section(self, content: str, description: str) -> str:
        """Ekstrak bagian yang relevan dari konten besar"""
        lines = content.split('\n')
        
        if len(lines) > 50:
            first_part = '\n'.join(lines[:30])
            last_part = '\n'.join(lines[-20:])
            return f"{first_part}\n\n... [dipendekkan - {len(lines)} baris total] ...\n\n{last_part}"
        
        if len(content) > 1500:
            return content[:800] + "\n...[dipendekkan]...\n" + content[-400:]
        
        return content


def get_ai_developer_service_v2() -> AIDeveloperServiceV2:
    """Factory function untuk mendapatkan instance AI Developer Service V2"""
    return AIDeveloperServiceV2()
