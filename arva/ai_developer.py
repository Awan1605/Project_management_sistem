"""
AI Developer Service (V1)
==========================
Layanan AI untuk pengembangan fitur dan perbaikan bug secara otomatis.

Menggunakan model AI khusus developer (codellama, deepseek-r1, dll)
untuk menganalisis, merencanakan, dan menghasilkan perubahan kode.

Alur kerja:
1. Terima feature request dari user
2. Analisis codebase terkait
3. Buat rencana implementasi
4. Generate kode perubahan
5. Review dan validasi kode
6. Simpan sebagai AICodeChange yang bisa di-apply/reject

Catatan: Versi V2 (ai_developer_v2.py) sudah tersedia dengan progress tracking.
File ini tetap dipertahankan untuk kompatibilitas.
"""

import json
import os
import re
import shutil
import difflib
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

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

from .models import AIFeatureRequest, AICodeChange, AISettings

# Setup logging
logger = logging.getLogger(__name__)


class AIDeveloperService:
    """Service untuk AI Developer - generate kode, fix bug, add feature"""
    
    # Pattern yang dilarang untuk keamanan
    FORBIDDEN_PATTERNS = [
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'subprocess\.run\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'importlib\.import_module',
        r'compile\s*\(',
        r'input\s*\(',
        r'raw_input\s*\(',
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
        '.env',
        'db.sqlite3',
        'manage.py',
    ]
    
    # Maximum retries for AI calls
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self):
        """Initialize AI Developer Service"""
        ai_settings = AISettings.get_current()
        
        self.provider = ai_settings.provider
        self.base_url = ai_settings.base_url or 'http://localhost:11434/v1'
        self.api_key = ai_settings.api_key or 'not-needed'
        self.model_name = ai_settings.get_developer_model()
        self.temperature = float(ai_settings.temperature)
        self.max_tokens = min(ai_settings.max_tokens, 4096)  # Cap at 4096 for safety
        
        # Base path untuk codebase
        self.base_path = Path(settings.BASE_DIR)
        self.backup_dir = self.base_path / '.ai_backups'
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)
        
        # Initialize client based on provider
        if self.provider == AISettings.PROVIDER_OPENCLAW:
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed")
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            self.client_type = 'openai'
        elif self.provider == AISettings.PROVIDER_GOOGLE:
            if not GOOGLE_AI_AVAILABLE:
                raise ValueError("Google AI package not installed. Run: pip install google-genai")
            # New Google GenAI SDK
            self.client = genai.Client(api_key=self.api_key)
            self.client_type = 'google'
        elif self.provider == AISettings.PROVIDER_QODER:
            if not ANTHROPIC_AVAILABLE:
                raise ValueError("Anthropic package not installed. Run: pip install anthropic")
            # Qoder uses Anthropic API format - may have custom base_url
            if self.base_url and self.base_url != 'http://localhost:8080/v1':
                self.client = anthropic.Anthropic(api_key=self.api_key, base_url=self.base_url)
            else:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            self.client_type = 'anthropic'
        elif self.provider == AISettings.PROVIDER_DEEPSEEK:
            # DeepSeek uses OpenAI-compatible API
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI package not installed. Run: pip install openai")
            if not self.api_key or self.api_key == 'not-needed':
                raise ValueError("DeepSeek API Key not configured in AI Settings")
            self.client = OpenAI(
                base_url='https://api.deepseek.com',
                api_key=self.api_key
            )
            self.client_type = 'openai'
        else:
            raise ValueError(f"AI Developer tidak support provider: {self.provider}")
    
    def process_request(self, request: AIFeatureRequest) -> Dict:
        """Process a feature request from start to finish with progress tracking"""
        try:
            # Step 1: Parse request
            request.status = 'analyzing'
            request.started_at = timezone.now()
            request.save()
            logger.info(f"[AI Developer] Starting processing request: {request.title}")
            
            # Step 2: Analyze codebase
            logger.info("[AI Developer] Step 1/5: Analyzing codebase...")
            analysis = self._analyze_codebase(request)
            if not analysis:
                raise Exception("Codebase analysis returned empty result")
            request.analysis_result = analysis
            request.status = 'planning'
            request.save()
            logger.info(f"[AI Developer] Analysis complete: {analysis.get('summary', 'No summary')}")
            
            # Step 3: Create implementation plan
            logger.info("[AI Developer] Step 2/5: Creating implementation plan...")
            plan = self._create_implementation_plan(request, analysis)
            if not plan or not plan.get('steps'):
                raise Exception("Implementation plan returned no steps")
            request.implementation_plan = plan
            request.status = 'generating'
            request.save()
            logger.info(f"[AI Developer] Plan created with {len(plan.get('steps', []))} steps")
            
            # Step 4: Generate code changes
            logger.info("[AI Developer] Step 3/5: Generating code changes...")
            changes = self._generate_code_changes(request, plan)
            if not changes:
                logger.warning("[AI Developer] No code changes generated, creating placeholder")
                # Create at least one placeholder change so user can see what was attempted
                changes = [{
                    'file_path': 'arva/views.py',
                    'change_type': 'modify',
                    'original_code': '# Original content',
                    'new_code': f'# TODO: Implement {request.title}\n# {request.description[:100]}\npass',
                    'diff_content': '+# TODO: Implement',
                }]
            logger.info(f"[AI Developer] Generated {len(changes)} code changes")
            
            # Step 5: Validate changes
            logger.info("[AI Developer] Step 4/5: Validating code changes...")
            validated_changes = self._validate_changes(changes)
            valid_count = len([c for c in validated_changes if not c.get('validation_error')])
            logger.info(f"[AI Developer] Validated: {valid_count}/{len(validated_changes)} changes valid")
            
            # Step 6: Create AICodeChange records
            logger.info("[AI Developer] Step 5/5: Saving code changes...")
            created_count = 0
            for change in validated_changes:
                AICodeChange.objects.create(
                    request=request,
                    file_path=change['file_path'],
                    change_type=change['change_type'],
                    original_code=change.get('original_code', ''),
                    new_code=change['new_code'],
                    diff_content=change['diff_content'],
                    line_start=change.get('line_start'),
                    line_end=change.get('line_end'),
                    has_error=change.get('has_error', False),
                    error_message=change.get('error_message', ''),
                )
                created_count += 1
            
            request.status = 'reviewing'
            request.save()
            logger.info(f"[AI Developer] Processing complete! Created {created_count} code changes")
            
            return {
                'success': True,
                'message': f'Generated {created_count} code changes',
                'changes': validated_changes,
            }
            
        except Exception as e:
            logger.error(f"[AI Developer] Error processing request: {str(e)}")
            request.status = 'failed'
            request.save()
            return {
                'success': False,
                'error': str(e),
            }
    
    def _analyze_codebase(self, request: AIFeatureRequest) -> Dict:
        """Analyze codebase to understand structure and find related files"""
        
        # Get files mentioned in request
        related_files = request.related_files or []
        
        # If no files specified, try to discover
        if not related_files:
            related_files = self._discover_related_files(request)
        
        # Read file contents
        file_contents = {}
        for file_path in related_files:
            content = self._read_file(file_path)
            if content:
                file_contents[file_path] = content
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(request, file_contents)
        
        # Call AI
        response = self._call_ai(prompt)
        
        # Parse response
        try:
            analysis = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON from markdown
            analysis = self._extract_json_from_response(response)
        
        # Update request with discovered files
        request.related_files = list(file_contents.keys())
        request.affected_models = analysis.get('affected_models', [])
        
        return analysis
    
    def _discover_related_files(self, request: AIFeatureRequest) -> List[str]:
        """Discover files related to the request"""
        related = []
        
        description = request.description.lower()
        request_type = request.request_type
        title = request.title.lower()
        combined = f"{title} {description}"
        
        # Dashboard, performance, statistics keywords
        if any(word in combined for word in ['dashboard', 'performa', 'performance', 'statistic', 'statistik', 'kinerja', 'metric', 'report', 'laporan', 'ranking', 'score']):
            # Add views.py for dashboard view
            views_file = self.base_path / 'arva' / 'views.py'
            if views_file.exists():
                related.append('arva/views.py')
            # Add urls.py for routing
            urls_file = self.base_path / 'arva' / 'urls.py'
            if urls_file.exists():
                related.append('arva/urls.py')
            # Add models for user/task data
            models_file = self.base_path / 'arva' / 'models.py'
            if models_file.exists():
                related.append('arva/models.py')
        
        # User-related features
        if any(word in combined for word in ['user', 'pengguna', 'member', 'anggota', 'profile']):
            models_file = self.base_path / 'arva' / 'models.py'
            if models_file.exists() and 'arva/models.py' not in related:
                related.append('arva/models.py')
        
        # Search for model mentions
        models_dir = self.base_path / 'arva'
        if models_dir.exists():
            models_file = models_dir / 'models.py'
            if models_file.exists():
                content = models_file.read_text(encoding='utf-8')
                # Find model classes
                model_classes = re.findall(r'class\s+(\w+)\s*\(\s*models\.Model', content)
                for model in model_classes:
                    if model.lower() in description:
                        if 'arva/models.py' not in related:
                            related.append('arva/models.py')
                        break
        
        # Search for view mentions
        if any(word in description for word in ['view', 'page', 'halaman', 'tampilan', 'template']):
            views_file = self.base_path / 'arva' / 'views.py'
            if views_file.exists() and 'arva/views.py' not in related:
                related.append('arva/views.py')
        
        # Search for URL mentions
        if any(word in description for word in ['url', 'route', 'link', 'path']):
            urls_file = self.base_path / 'arva' / 'urls.py'
            if urls_file.exists() and 'arva/urls.py' not in related:
                related.append('arva/urls.py')
        
        # Search for template mentions
        if 'template' in description or 'html' in description:
            templates_dir = self.base_path / 'arva' / 'templates' / 'arva'
            if templates_dir.exists():
                for template_file in templates_dir.glob('*.html'):
                    if template_file.stem.lower() in description:
                        related.append(f'arva/templates/arva/{template_file.name}')
        
        # Search for static/JS mentions
        if any(word in description for word in ['javascript', 'js', 'button', 'click', 'event']):
            static_dir = self.base_path / 'static' / 'arva' / 'js'
            if static_dir.exists():
                related.append('static/arva/js/arva.js')
        
        # Default: if no files found, include core files
        if not related:
            # Always include views.py and models.py as defaults for feature requests
            if (self.base_path / 'arva' / 'views.py').exists():
                related.append('arva/views.py')
            if (self.base_path / 'arva' / 'models.py').exists():
                related.append('arva/models.py')
            if (self.base_path / 'arva' / 'urls.py').exists():
                related.append('arva/urls.py')
        
        return list(set(related))  # Remove duplicates
    
    def _read_file(self, file_path: str) -> Optional[str]:
        """Read file content safely"""
        try:
            full_path = self.base_path / file_path
            
            # Security check
            if not self._is_path_allowed(full_path):
                return None
            
            if not full_path.exists():
                return None
            
            # Check file size (max 1MB)
            if full_path.stat().st_size > 1024 * 1024:
                return f"# File too large: {file_path}"
            
            return full_path.read_text(encoding='utf-8')
        except Exception as e:
            return f"# Error reading {file_path}: {str(e)}"
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is allowed to be accessed"""
        try:
            # Resolve to absolute path
            resolved = path.resolve()
            base = self.base_path.resolve()
            
            # Check if path is within base directory
            if not str(resolved).startswith(str(base)):
                return False
            
            # Check if file is in forbidden list
            if resolved.name in self.FORBIDDEN_FILES:
                return False
            
            # Check if directory is allowed
            rel_path = resolved.relative_to(base)
            first_dir = rel_path.parts[0] if rel_path.parts else ''
            if first_dir not in self.ALLOWED_DIRECTORIES:
                return False
            
            return True
        except Exception:
            return False
    
    def _build_analysis_prompt(self, request: AIFeatureRequest, file_contents: Dict) -> str:
        """Build prompt for codebase analysis - optimized for smaller context windows"""
        
        # Build shorter files text with aggressive truncation
        files_text = ""
        for file_path, content in file_contents.items():
            files_text += f"\n=== {file_path} ===\n"
            # More aggressive truncation for small context windows
            if len(content) > 1500:
                content = content[:800] + "\n...[truncated]...\n" + content[-400:]
            files_text += content
        
        # Simplified prompt for local LLMs
        prompt = f"""Analyze this Django request and respond with JSON only.

TYPE: {request.get_request_type_display()}
TITLE: {request.title}
DESC: {request.description[:200]}{'...' if len(request.description) > 200 else ''}

FILES:
{files_text}

Respond with ONLY this JSON format (no markdown):
{{"summary":"brief summary","root_cause":"bug cause or null","affected_models":["Model1"],"affected_views":["view1"],"files_to_modify":["path1"],"complexity":"low","estimated_effort":"1h"}}"""
        
        return prompt
    
    def _create_implementation_plan(self, request: AIFeatureRequest, analysis: Dict) -> Dict:
        """Create detailed implementation plan - simplified for local LLMs"""
        
        # Build shorter analysis summary
        analysis_summary = {
            'summary': analysis.get('summary', ''),
            'files_to_modify': analysis.get('files_to_modify', [])[:3],  # Limit to 3 files
        }
        
        prompt = f"""Create implementation steps for this Django feature/bug.

TITLE: {request.title}
DESC: {request.description[:150]}{'...' if len(request.description) > 150 else ''}

ANALYSIS: {json.dumps(analysis_summary)}

IMPORTANT: 
- Each file should appear only ONCE in the steps
- Combine all changes for the same file into a single step
- Maximum 3-4 steps total

Respond with ONLY this JSON format (no markdown):
{{"steps":[{{"order":1,"title":"Update views","file_path":"arva/views.py","action":"modify","description":"Add dashboard view function"}}],"testing":"test approach"}}"""

        response = self._call_ai(prompt)
        plan = self._extract_json_from_response(response)
        
        # Post-process: deduplicate steps by file_path
        if plan and 'steps' in plan:
            seen_files = set()
            unique_steps = []
            for step in plan['steps']:
                file_path = step.get('file_path')
                if file_path and file_path not in seen_files:
                    seen_files.add(file_path)
                    unique_steps.append(step)
                elif file_path:
                    logger.info(f"[AI Developer] Deduplicating step for {file_path}")
            plan['steps'] = unique_steps
            logger.info(f"[AI Developer] Plan created with {len(unique_steps)} unique steps")
        
        return plan
    
    def _generate_code_changes(self, request: AIFeatureRequest, plan: Dict) -> List[Dict]:
        """Generate actual code changes with deduplication and merge"""
        changes = []
        file_changes_map = {}  # Track changes per file for merging
        
        steps = plan.get('steps', [])
        logger.info(f"[AI Developer] Processing {len(steps)} steps from plan")
        
        for step in steps:
            file_path = step.get('file_path')
            action = step.get('action', 'modify')
            
            if not file_path:
                logger.warning("[AI Developer] Skipping step without file_path")
                continue
            
            logger.info(f"[AI Developer] Processing step: {action} {file_path}")
            
            try:
                if action == 'create':
                    # Generate new file
                    change = self._generate_new_file(request, step)
                elif action == 'modify':
                    # Modify existing file
                    change = self._generate_file_modification(request, step)
                elif action == 'delete':
                    # Delete file
                    change = self._generate_file_deletion(request, step)
                else:
                    logger.warning(f"[AI Developer] Unknown action: {action}")
                    continue
                
                if change:
                    # Check if we already have a change for this file
                    if file_path in file_changes_map:
                        logger.info(f"[AI Developer] Merging changes for {file_path}")
                        # Merge with existing change
                        existing = file_changes_map[file_path]
                        merged = self._merge_changes(existing, change)
                        file_changes_map[file_path] = merged
                        # Update in changes list
                        idx = changes.index(existing)
                        changes[idx] = merged
                    else:
                        file_changes_map[file_path] = change
                        changes.append(change)
                        
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[AI Developer] Error processing step {file_path}: {error_msg}")
                # Create a placeholder change to indicate failure
                error_change = {
                    'file_path': file_path,
                    'change_type': 'modify',
                    'original_code': f'# Error generating change for {file_path}',
                    'new_code': f'# TODO: {step.get("description", "Implement")}\n# Error: {error_msg[:100]}\npass',
                    'diff_content': f'+# Error: {error_msg[:50]}',
                    'has_error': True,
                    'error_message': error_msg,
                }
                if file_path not in file_changes_map:
                    file_changes_map[file_path] = error_change
                    changes.append(error_change)
                # Continue with next step instead of failing entirely
                continue
        
        logger.info(f"[AI Developer] Generated {len(changes)} unique changes after deduplication")
        return changes
    
    def _merge_changes(self, existing: Dict, new: Dict) -> Dict:
        """Merge two changes for the same file"""
        # If both are modifications, combine the new code
        if existing['change_type'] == 'modify' and new['change_type'] == 'modify':
            # Use the newer code as the final version
            # The new change should be based on the original file, not the previous change
            merged_code = new['new_code']
            
            return {
                'file_path': existing['file_path'],
                'change_type': 'modify',
                'original_code': existing['original_code'],  # Keep original
                'new_code': merged_code,  # Use latest
                'diff_content': self._generate_diff(existing['original_code'], merged_code, existing['file_path']),
                'line_start': existing.get('line_start') or new.get('line_start'),
                'line_end': existing.get('line_end') or new.get('line_end'),
            }
        
        # If one is create and other is modify, keep as create with merged content
        if existing['change_type'] == 'add' or new['change_type'] == 'add':
            return {
                'file_path': existing['file_path'],
                'change_type': 'add',
                'original_code': '',
                'new_code': new['new_code'] if new['change_type'] == 'modify' else existing['new_code'],
                'diff_content': self._generate_diff('', new['new_code'] if new['change_type'] == 'modify' else existing['new_code'], existing['file_path']),
            }
        
        # Default: return the newer change
        return new
    
    def _generate_new_file(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate content for new file - simplified for small context"""
        
        file_path = step.get('file_path')
        description = step.get('description', '')[:200]
        
        prompt = f"""Create a new Django file.

FILE: {file_path}
PURPOSE: {description}

Output the complete file content. No explanations."""

        response = self._call_ai(prompt)
        content = self._extract_code_from_response(response)
        
        # If content is empty, create a placeholder
        if not content:
            content = f"""# {file_path}
# TODO: Implement - {description}

# Add your implementation here
pass
"""
        
        return {
            'file_path': file_path,
            'change_type': 'add',
            'original_code': '',
            'new_code': content,
            'diff_content': self._generate_diff('', content, file_path),
        }
    
    def _generate_file_modification(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate modification for existing file - optimized for small context"""
        
        file_path = step.get('file_path')
        original_content = self._read_file(file_path) or ''
        
        # Aggressive truncation for small context windows
        if len(original_content) > 1000:
            original_content = self._extract_relevant_section(original_content, step.get('description'))
        
        description = step.get('description', '')[:200]  # Limit description length
        
        prompt = f"""Modify this Django file.

FILE: {file_path}
CHANGE: {description}

CURRENT CODE:
```
{original_content}
```

Output the COMPLETE modified code. No explanations. Just the code."""

        response = self._call_ai(prompt)
        new_content = self._extract_code_from_response(response)
        
        # If new content is empty or same as original, create a placeholder
        if not new_content or new_content == original_content:
            new_content = f"# TODO: Implement - {description}\n# File: {file_path}\npass\n"
        
        return {
            'file_path': file_path,
            'change_type': 'modify',
            'original_code': original_content,
            'new_code': new_content,
            'diff_content': self._generate_diff(original_content, new_content, file_path),
        }
    
    def _build_fallback_json(self, response: str) -> Dict:
        """Build a minimal valid JSON when extraction fails"""
        # Try to extract key information from the response
        summary = "Analysis completed"
        files = []
        
        # Look for file paths in the response
        file_patterns = [
            r'arva/\w+\.py',
            r'templates/[\w/]+\.html',
            r'static/[\w/]+\.(js|css)',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, response)
            files.extend(matches)
        
        return {
            'summary': summary,
            'root_cause': None,
            'affected_models': [],
            'affected_views': [],
            'files_to_modify': list(set(files))[:3],
            'complexity': 'medium',
            'estimated_effort': '2h',
        }
    
    def _generate_file_deletion(self, request: AIFeatureRequest, step: Dict) -> Dict:
        """Generate file deletion"""
        file_path = step.get('file_path')
        original_content = self._read_file(file_path) or ''
        
        return {
            'file_path': file_path,
            'change_type': 'delete',
            'original_code': original_content,
            'new_code': '',
            'diff_content': self._generate_diff(original_content, '', file_path),
        }
    
    def _validate_changes(self, changes: List[Dict]) -> List[Dict]:
        """Validate generated code changes"""
        validated = []
        
        for change in changes:
            # Check for forbidden patterns
            new_code = change.get('new_code', '')
            
            is_safe = True
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, new_code):
                    is_safe = False
                    change['validation_error'] = f'Forbidden pattern detected: {pattern}'
                    break
            
            # Check syntax for Python files
            if change['file_path'].endswith('.py') and new_code:
                try:
                    import ast
                    ast.parse(new_code)
                except SyntaxError as e:
                    is_safe = False
                    change['validation_error'] = f'Syntax error: {str(e)}'
            
            # Check file path is allowed
            full_path = self.base_path / change['file_path']
            if not self._is_path_allowed(full_path):
                is_safe = False
                change['validation_error'] = 'File path not allowed'
            
            if is_safe:
                validated.append(change)
            else:
                # Still add but mark as invalid
                change['is_valid'] = False
                validated.append(change)
        
        return validated
    
    def apply_change(self, change: AICodeChange, user) -> Dict:
        """Apply a code change to the filesystem"""
        try:
            # Backup original file
            backup_path = self._create_backup(change.file_path)
            change.backup_path = str(backup_path)
            
            full_path = self.base_path / change.file_path
            
            if change.change_type == 'delete':
                # Delete file
                if full_path.exists():
                    full_path.unlink()
            else:
                # Create directory if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write new content
                full_path.write_text(change.new_code, encoding='utf-8')
            
            change.status = 'applied'
            change.applied_at = timezone.now()
            change.save()
            
            return {
                'success': True,
                'message': f'Applied changes to {change.file_path}',
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def rollback_change(self, change: AICodeChange) -> Dict:
        """Rollback a change using backup"""
        try:
            if not change.backup_path:
                return {
                    'success': False,
                    'error': 'No backup available',
                }
            
            backup_path = Path(change.backup_path)
            full_path = self.base_path / change.file_path
            
            if backup_path.exists():
                # Restore from backup
                shutil.copy2(backup_path, full_path)
                
                change.status = 'rolled_back'
                change.save()
                
                return {
                    'success': True,
                    'message': f'Rolled back changes to {change.file_path}',
                }
            else:
                return {
                    'success': False,
                    'error': 'Backup file not found',
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def _create_backup(self, file_path: str) -> Path:
        """Create backup of file before modification"""
        full_path = self.base_path / file_path
        
        if full_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{file_path.replace('/', '_').replace('\\', '_')}.{timestamp}.backup"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(full_path, backup_path)
            return backup_path
        
        return None
    
    def _call_ai(self, prompt: str) -> str:
        """Call AI model with prompt - with retry logic and connection handling"""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[AI Developer] AI call attempt {attempt + 1}/{self.MAX_RETRIES} ({self.client_type})")
                logger.info(f"[AI Developer] Prompt length: {len(prompt)} chars")
                
                if self.client_type == 'google':
                    # Google Gemini API
                    content = self._call_google_ai(prompt)
                elif self.client_type == 'anthropic':
                    # Anthropic Claude API (Qoder)
                    content = self._call_anthropic_ai(prompt)
                else:
                    # OpenAI-compatible API (Ollama/OpenClaw)
                    content = self._call_openai_compatible(prompt)
                
                if not content:
                    raise Exception("Empty response from AI")
                
                logger.info(f"[AI Developer] AI response received: {len(content)} chars")
                return content
                
            except (ConnectionError, ConnectionResetError, BrokenPipeError) as e:
                last_error = e
                logger.error(f"[AI Developer] Connection error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (attempt + 1)  # Exponential backoff
                    logger.info(f"[AI Developer] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    # Reinitialize client on connection error
                    self._reinitialize_client()
                
            except Exception as e:
                last_error = e
                logger.warning(f"[AI Developer] AI call attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    # Reduce prompt length for next attempt
                    if len(prompt) > 2000:
                        prompt = prompt[:2000] + "\n...[truncated for retry]"
        
        raise Exception(f"AI call failed after {self.MAX_RETRIES} attempts: {str(last_error)}")
    
    def _call_openai_compatible(self, prompt: str) -> str:
        """Call OpenAI-compatible API"""
        # Add timeout to prevent hanging
        import socket
        socket.setdefaulttimeout(300)  # 5 minutes timeout
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a Django/Python expert. Respond with valid JSON or code only. No explanations."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=min(self.max_tokens, 2048),  # Limit tokens for stability
            timeout=180,  # 3 minutes API timeout
        )
        
        return response.choices[0].message.content.strip()
    
    def _call_google_ai(self, prompt: str) -> str:
        """Call Google Gemini API using new SDK"""
        # Create content with system instruction
        system_prompt = "You are a Django/Python expert. Respond with valid JSON or code only. No explanations."
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
        """Call Anthropic Claude API (used by Qoder)"""
        system_prompt = "You are a Django/Python expert. Respond with valid JSON or code only. No explanations."
        
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=min(self.max_tokens, 4096),
            temperature=float(self.temperature),
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text.strip()
    
    def _reinitialize_client(self):
        """Reinitialize AI client after connection error"""
        try:
            if self.client_type == 'openai':
                self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            elif self.client_type == 'google':
                self.client = genai.Client(api_key=self.api_key)
            elif self.client_type == 'anthropic':
                self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("[AI Developer] Client reinitialized")
        except Exception as reinit_error:
            logger.warning(f"[AI Developer] Failed to reinitialize client: {reinit_error}")
    
    def _extract_json_from_response(self, response: str) -> Dict:
        """Extract JSON from AI response - with multiple fallback strategies"""
        if not response:
            return {}
        
        # Strategy 1: Try to parse entire response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Find JSON object in response
        json_match = re.search(r'(\{[^{}]*\})', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Try to find nested JSON
        json_match = re.search(r'(\{.*\})', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 5: Build minimal valid JSON from response content
        logger.warning(f"[AI Developer] Could not extract JSON, building fallback")
        return self._build_fallback_json(response)
    
    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from AI response"""
        # Try to find code in markdown code blocks
        code_match = re.search(r'```(?:\w+)?\s*(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Try to find after FILE_CONTENT:
        content_match = re.search(r'FILE_CONTENT:\s*(.*)', response, re.DOTALL)
        if content_match:
            return content_match.group(1).strip()
        
        # Try to find after MODIFIED_CONTENT:
        content_match = re.search(r'MODIFIED_CONTENT:\s*(.*?)(?:CHANGES_SUMMARY:|$)', response, re.DOTALL)
        if content_match:
            return content_match.group(1).strip()
        
        # Return as-is
        return response.strip()
    
    def _generate_diff(self, original: str, new: str, file_path: str) -> str:
        """Generate unified diff between original and new content"""
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
        """Extract relevant section from large file - optimized for small context"""
        lines = content.split('\n')
        
        # More aggressive truncation for small context windows
        if len(lines) > 50:
            first_part = '\n'.join(lines[:30])
            last_part = '\n'.join(lines[-20])
            return f"{first_part}\n\n... [truncated - {len(lines)} lines total] ...\n\n{last_part}"
        
        # If still too long, truncate characters
        if len(content) > 800:
            return content[:400] + "\n...[truncated]...\n" + content[-300:]
        
        return content


def get_ai_developer_service() -> AIDeveloperService:
    """Factory function to get AI Developer service instance"""
    return AIDeveloperService()
