"""
AI Code Analyzer
=================
Layanan AI untuk menganalisis struktur codebase Django.

Menghasilkan informasi tentang:
- Model: Daftar model dengan field dan method
- Views: Daftar view dengan tipe dan method
- URLs: Daftar URL pattern
- Templates: Daftar template dengan relasi extends
- Struktur folder: Pohon folder dan file

Digunakan oleh AI Developer untuk memahami codebase
sebelum menghasilkan perubahan kode.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class ModelInfo:
    """Information about a Django model"""
    name: str
    fields: List[Dict] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    meta_options: Dict = field(default_factory=dict)
    file_path: str = ""
    line_number: int = 0


@dataclass
class ViewInfo:
    """Information about a Django view"""
    name: str
    view_type: str  # function, class, CBV
    url_pattern: Optional[str] = None
    methods: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    file_path: str = ""
    line_number: int = 0


@dataclass
class URLPatternInfo:
    """Information about URL pattern"""
    pattern: str
    view_name: str
    name: Optional[str] = None
    namespace: Optional[str] = None
    file_path: str = ""


@dataclass
class TemplateInfo:
    """Information about a template"""
    name: str
    extends: Optional[str] = None
    blocks: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    file_path: str = ""


@dataclass
class FolderInfo:
    """Information about a folder"""
    name: str
    path: str
    is_folder: bool = True
    size: int = 0
    file_count: int = 0
    children: List['FolderInfo'] = field(default_factory=list)
    file_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class CodebaseAnalysis:
    """Complete codebase analysis result"""
    models: List[ModelInfo] = field(default_factory=list)
    views: List[ViewInfo] = field(default_factory=list)
    urls: List[URLPatternInfo] = field(default_factory=list)
    templates: List[TemplateInfo] = field(default_factory=list)
    static_files: List[str] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    folder_structure: Optional[FolderInfo] = None


class CodebaseAnalyzer:
    """Analyzer untuk struktur codebase Django"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path(settings.BASE_DIR)
        self.analysis = CodebaseAnalysis()
    
    def analyze_full_codebase(self) -> CodebaseAnalysis:
        """Analyze entire codebase"""
        self.analysis = CodebaseAnalysis()
        
        # Find Django apps
        self._find_apps()
        
        # Analyze models
        self._analyze_models()
        
        # Analyze views
        self._analyze_views()
        
        # Analyze URLs
        self._analyze_urls()
        
        # Analyze templates
        self._analyze_templates()
        
        # Find static files
        self._find_static_files()
        
        # Analyze folder structure
        self._analyze_folder_structure()
        
        return self.analysis
    
    def _find_apps(self):
        """Find all Django apps in project"""
        for item in self.base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.') and not item.name.startswith('__'):
                # Check if it's a Django app
                models_file = item / 'models.py'
                apps_file = item / 'apps.py'
                if models_file.exists() or apps_file.exists():
                    self.analysis.apps.append(item.name)
        
        # Also check subdirectories (for apps inside folders like 'apps/')
        for subdir in ['apps', 'applications', 'modules']:
            subdir_path = self.base_path / subdir
            if subdir_path.exists():
                for item in subdir_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        models_file = item / 'models.py'
                        if models_file.exists():
                            self.analysis.apps.append(f"{subdir}/{item.name}")
    
    def _analyze_models(self):
        """Analyze all models.py files"""
        for app_name in self.analysis.apps:
            models_file = self.base_path / app_name / 'models.py'
            if models_file.exists():
                self._parse_models_file(models_file, app_name)
    
    def _parse_models_file(self, file_path: Path, app_name: str):
        """Parse a models.py file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a Django model
                    is_model = False
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            # Check for 'Model' or models.Model pattern
                            if base.id == 'Model' or 'Model' in base.id:
                                is_model = True
                        elif isinstance(base, ast.Attribute):
                            # Check for models.Model, models.ForeignKey, etc.
                            if base.attr == 'Model':
                                is_model = True
                            # Also check if it's models.SomeModel
                            if isinstance(base.value, ast.Name) and base.value.id == 'models':
                                if base.attr == 'Model':
                                    is_model = True
                    
                    if is_model:
                        model_info = ModelInfo(
                            name=node.name,
                            file_path=str(file_path.relative_to(self.base_path)),
                            line_number=node.lineno
                        )
                        
                        # Extract fields
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        field_info = self._parse_field(item.value)
                                        if field_info:
                                            field_info['name'] = target.id
                                            model_info.fields.append(field_info)
                        
                        # Extract methods
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                if not item.name.startswith('_') or item.name == '__str__':
                                    model_info.methods.append(item.name)
                        
                        self.analysis.models.append(model_info)
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _parse_field(self, node) -> Optional[Dict]:
        """Parse a Django model field"""
        field_info = {'type': 'Unknown', 'params': {}}
        
        if isinstance(node, ast.Call):
            # Get field type
            if isinstance(node.func, ast.Attribute):
                field_info['type'] = node.func.attr
            elif isinstance(node.func, ast.Name):
                field_info['type'] = node.func.id
            
            # Get field parameters
            for keyword in node.keywords:
                if isinstance(keyword.value, ast.Constant):
                    field_info['params'][keyword.arg] = keyword.value.value
                # Python 3.8+ uses Constant instead of NameConstant/Str/Num/etc
        
        return field_info
    
    def _analyze_views(self):
        """Analyze all views.py files and views/ directory"""
        for app_name in self.analysis.apps:
            # Check for views.py in app root
            views_file = self.base_path / app_name / 'views.py'
            if views_file.exists():
                self._parse_views_file(views_file, app_name)
            
            # Check for views/ directory (package pattern)
            views_dir = self.base_path / app_name / 'views'
            if views_dir.exists() and views_dir.is_dir():
                for view_file in views_dir.glob('*.py'):
                    if view_file.name != '__init__.py':
                        self._parse_views_file(view_file, app_name)
    
    def _parse_views_file(self, file_path: Path, app_name: str):
        """Parse a views.py file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if it's a view (has request parameter)
                    if node.args.args and len(node.args.args) > 0:
                        first_arg = node.args.args[0].arg
                        if first_arg in ['request', 'req', 'r']:
                            view_info = ViewInfo(
                                name=node.name,
                                view_type='function',
                                file_path=str(file_path.relative_to(self.base_path)),
                                line_number=node.lineno
                            )
                            
                            # Extract decorators
                            for decorator in node.decorator_list:
                                if isinstance(decorator, ast.Name):
                                    view_info.decorators.append(decorator.id)
                                elif isinstance(decorator, ast.Call):
                                    if isinstance(decorator.func, ast.Name):
                                        view_info.decorators.append(decorator.func.id)
                            
                            self.analysis.views.append(view_info)
                
                elif isinstance(node, ast.ClassDef):
                    # Check if it's a class-based view
                    is_view = False
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            if 'View' in base.id or base.id in ['TemplateView', 'ListView', 'DetailView']:
                                is_view = True
                        elif isinstance(base, ast.Attribute):
                            if 'View' in base.attr:
                                is_view = True
                    
                    if is_view:
                        view_info = ViewInfo(
                            name=node.name,
                            view_type='class',
                            file_path=str(file_path.relative_to(self.base_path)),
                            line_number=node.lineno
                        )
                        
                        # Extract methods
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                view_info.methods.append(item.name)
                        
                        self.analysis.views.append(view_info)
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _analyze_urls(self):
        """Analyze urls.py files"""
        for app_name in self.analysis.apps:
            urls_file = self.base_path / app_name / 'urls.py'
            if urls_file.exists():
                self._parse_urls_file(urls_file, app_name)
        
        # Also check project urls
        project_urls = self.base_path / 'arviga' / 'urls.py'
        if project_urls.exists():
            self._parse_urls_file(project_urls, 'arviga')
    
    def _parse_urls_file(self, file_path: Path, app_name: str):
        """Parse a urls.py file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Simple regex-based parsing for URL patterns
            # Look for path() or url() patterns
            path_pattern = r"path\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^,\)]+)"
            url_pattern = r"url\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^,\)]+)"
            
            for match in re.finditer(path_pattern, content):
                pattern = match.group(1)
                view = match.group(2).strip()
                
                url_info = URLPatternInfo(
                    pattern=pattern,
                    view_name=view,
                    file_path=str(file_path.relative_to(self.base_path))
                )
                
                self.analysis.urls.append(url_info)
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _analyze_templates(self):
        """Analyze template files"""
        templates_dir = self.base_path / 'arva' / 'templates' / 'arva'
        if templates_dir.exists():
            for template_file in templates_dir.rglob('*.html'):
                self._parse_template(template_file)
    
    def _parse_template(self, file_path: Path):
        """Parse a template file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            template_info = TemplateInfo(
                name=file_path.name,
                file_path=str(file_path.relative_to(self.base_path))
            )
            
            # Find extends
            extends_match = re.search(r"{%\s*extends\s+['\"]([^'\"]+)['\"]\s*%}", content)
            if extends_match:
                template_info.extends = extends_match.group(1)
            
            # Find blocks
            block_matches = re.findall(r"{%\s*block\s+(\w+)\s*%}", content)
            template_info.blocks = block_matches
            
            # Find includes
            include_matches = re.findall(r"{%\s*include\s+['\"]([^'\"]+)['\"]\s*%}", content)
            template_info.includes = include_matches
            
            self.analysis.templates.append(template_info)
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _find_static_files(self):
        """Find all static files"""
        static_dir = self.base_path / 'static'
        if static_dir.exists():
            for static_file in static_dir.rglob('*'):
                if static_file.is_file():
                    self.analysis.static_files.append(
                        str(static_file.relative_to(self.base_path))
                    )
    
    def find_related_files(self, query: str) -> List[str]:
        """Find files related to a query"""
        related = []
        query_lower = query.lower()
        
        # Check models
        for model in self.analysis.models:
            if model.name.lower() in query_lower:
                related.append(model.file_path)
        
        # Check views
        for view in self.analysis.views:
            if view.name.lower() in query_lower:
                related.append(view.file_path)
        
        # Check templates
        for template in self.analysis.templates:
            if template.name.lower().replace('.html', '') in query_lower:
                related.append(template.file_path)
        
        return list(set(related))
    
    def get_model_relationships(self) -> Dict[str, List[str]]:
        """Get relationships between models"""
        relationships = {}
        
        for model in self.analysis.models:
            related = []
            for field in model.fields:
                field_type = field.get('type', '')
                if 'ForeignKey' in field_type or 'ManyToMany' in field_type or 'OneToOne' in field_type:
                    related.append(field.get('name', ''))
            if related:
                relationships[model.name] = related
        
        return relationships
    
    def generate_codebase_summary(self) -> str:
        """Generate a text summary of the codebase"""
        lines = []
        
        lines.append("=" * 60)
        lines.append("CODEBASE ANALYSIS SUMMARY")
        lines.append("=" * 60)
        
        lines.append(f"\n📁 Apps: {len(self.analysis.apps)}")
        for app in self.analysis.apps:
            lines.append(f"  - {app}")
        
        lines.append(f"\n🗄️  Models: {len(self.analysis.models)}")
        for model in self.analysis.models:
            fields_str = ", ".join([f['name'] for f in model.fields[:5]])
            if len(model.fields) > 5:
                fields_str += f" (+{len(model.fields) - 5} more)"
            lines.append(f"  - {model.name} ({fields_str})")
        
        lines.append(f"\n👁️  Views: {len(self.analysis.views)}")
        for view in self.analysis.views[:10]:  # Limit to 10
            lines.append(f"  - {view.name} ({view.view_type})")
        if len(self.analysis.views) > 10:
            lines.append(f"  ... and {len(self.analysis.views) - 10} more")
        
        lines.append(f"\n🔗 URL Patterns: {len(self.analysis.urls)}")
        
        lines.append(f"\n🎨 Templates: {len(self.analysis.templates)}")
        
        lines.append(f"\n📎 Static Files: {len(self.analysis.static_files)}")
        
        lines.append(f"\n📂 Folder Structure:")
        if self.analysis.folder_structure:
            lines.append(self._folder_to_string(self.analysis.folder_structure, 0))
        
        return "\n".join(lines)
    
    def _analyze_folder_structure(self):
        """Analyze folder structure"""
        # Folders to include in analysis
        include_folders = ['arva', 'arviga', 'templates', 'static', 'media', 'models']
        
        # Folders/files to exclude
        exclude_names = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', 
                         '.idea', '.vscode', 'migrations', 'staticfiles', 
                         '.metadata', '.qoder', '.qodo', 'kanban'}
        
        root = FolderInfo(
            name=self.base_path.name,
            path='',
            is_folder=True
        )
        
        for item in self.base_path.iterdir():
            if item.name in exclude_names or item.name.startswith('.'):
                continue
            
            if item.name in include_folders or item.is_dir():
                folder_info = self._build_folder_tree(item, exclude_names, depth=0, max_depth=3)
                if folder_info:
                    root.children.append(folder_info)
        
        self.analysis.folder_structure = root
    
    def _build_folder_tree(self, path: Path, exclude_names: Set, depth: int = 0, max_depth: int = 3) -> Optional[FolderInfo]:
        """Recursively build folder tree"""
        if depth > max_depth:
            return None
        
        folder_info = FolderInfo(
            name=path.name,
            path=str(path.relative_to(self.base_path)),
            is_folder=path.is_dir()
        )
        
        if path.is_file():
            try:
                folder_info.size = path.stat().st_size
                folder_info.is_folder = False
                
                # Track file type
                ext = path.suffix.lower() or '.no_ext'
                folder_info.file_types[ext] = 1
            except:
                pass
            return folder_info
        
        if not path.is_dir():
            return None
        
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return folder_info
        
        for item in items:
            # Skip excluded items
            if item.name in exclude_names or item.name.startswith('.'):
                continue
            
            # Skip pycache and migrations inside folders
            if item.name == '__pycache__' or item.name == 'migrations':
                continue
            
            child = self._build_folder_tree(item, exclude_names, depth + 1, max_depth)
            if child:
                folder_info.children.append(child)
                folder_info.file_count += child.file_count + (1 if not child.is_folder else 0)
                
                # Merge file types
                for ext, count in child.file_types.items():
                    folder_info.file_types[ext] = folder_info.file_types.get(ext, 0) + count
        
        return folder_info
    
    def _folder_to_string(self, folder: FolderInfo, indent: int) -> str:
        """Convert folder structure to string for display"""
        prefix = "  " * indent
        lines = []
        
        icon = "📁" if folder.is_folder else "📄"
        type_info = ""
        if folder.file_types and folder.is_folder:
            type_info = f" [{dict(list(folder.file_types.items())[:5])}]"
        
        lines.append(f"{prefix}{icon} {folder.name}{type_info}")
        
        for child in folder.children[:20]:  # Limit children
            lines.append(self._folder_to_string(child, indent + 1))
        
        if len(folder.children) > 20:
            lines.append(f"{prefix}  ... and {len(folder.children) - 20} more")
        
        return "\n".join(lines)


def get_codebase_analyzer() -> CodebaseAnalyzer:
    """Factory function to get analyzer instance"""
    return CodebaseAnalyzer()
