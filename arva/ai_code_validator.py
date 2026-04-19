"""
AI Code Validator
==================
Layanan AI untuk memvalidasi kode yang dihasilkan AI Developer.

Melakukan pengecekan:
- Syntax error: Parse kode dengan AST
- Import error: Verifikasi import yang digunakan
- Keamanan: Deteksi pola berbahaya (eval, exec, dll)
- Kompatibilitas: Cek kesesuaian dengan framework Django

Digunakan sebelum menyimpan code change untuk memastikan
kualitas kode yang dihasilkan AI.
"""

import ast
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class CodeValidator:
    """Validator untuk kode yang dihasilkan AI"""
    
    # Pattern berbahaya yang dilarang
    DANGEROUS_PATTERNS = {
        'os_system': {
            'pattern': r'os\.system\s*\(',
            'message': 'Penggunaan os.system() tidak diizinkan',
            'severity': 'critical'
        },
        'subprocess': {
            'pattern': r'subprocess\.(call|run|Popen)\s*\(',
            'message': 'Penggunaan subprocess tidak diizinkan',
            'severity': 'critical'
        },
        'eval': {
            'pattern': r'eval\s*\(',
            'message': 'Penggunaan eval() tidak diizinkan',
            'severity': 'critical'
        },
        'exec': {
            'pattern': r'exec\s*\(',
            'message': 'Penggunaan exec() tidak diizinkan',
            'severity': 'critical'
        },
        'compile': {
            'pattern': r'compile\s*\(',
            'message': 'Penggunaan compile() tidak diizinkan',
            'severity': 'high'
        },
        '__import__': {
            'pattern': r'__import__\s*\(',
            'message': 'Penggunaan __import__() tidak diizinkan',
            'severity': 'high'
        },
        'importlib': {
            'pattern': r'importlib\.(import_module|__import__)',
            'message': 'Dynamic import tidak diizinkan',
            'severity': 'medium'
        },
        'input': {
            'pattern': r'(?<!raw_)input\s*\(',
            'message': 'Penggunaan input() berpotensi berbahaya',
            'severity': 'medium'
        },
        'raw_input': {
            'pattern': r'raw_input\s*\(',
            'message': 'Penggunaan raw_input() berpotensi berbahaya',
            'severity': 'medium'
        },
        'open_file': {
            'pattern': r'open\s*\([^)]*[\"\']w[\"\']',
            'message': 'Penulisan file harus diperhatikan',
            'severity': 'low'
        },
        'hardcoded_secret': {
            'pattern': r'(password|secret|key|token)\s*=\s*[\"\'][^\"\']+[\"\']',
            'message': 'Potensi hardcoded credential',
            'severity': 'high'
        },
        'sql_injection': {
            'pattern': r'\.raw\s*\(|execute\s*\(\s*["\'].*%s',
            'message': 'Potensi SQL injection',
            'severity': 'critical'
        },
    }
    
    # Best practices Django
    DJANGO_BEST_PRACTICES = {
        'use_get_user_model': {
            'check': lambda code: 'from django.contrib.auth.models import User' in code and 'get_user_model()' not in code,
            'message': 'Gunakan get_user_model() daripada import User langsung',
            'severity': 'low'
        },
        'use_timezone_now': {
            'check': lambda code: 'datetime.now()' in code and 'timezone.now()' not in code,
            'message': 'Gunakan timezone.now() untuk Django',
            'severity': 'low'
        },
        'use_render_not_render_to_response': {
            'check': lambda code: 'render_to_response' in code,
            'message': 'Gunakan render() daripada render_to_response()',
            'severity': 'low'
        },
    }
    
    def __init__(self):
        self.issues = []
    
    def validate_python_code(self, code: str, file_path: str = '') -> Dict:
        """Validate Python code"""
        self.issues = []
        
        # 1. Syntax validation
        syntax_valid, syntax_error = self._check_syntax(code)
        if not syntax_valid:
            self.issues.append({
                'type': 'syntax_error',
                'message': f'Syntax error: {syntax_error}',
                'severity': 'critical',
                'line': getattr(syntax_error, 'lineno', 0)
            })
            return self._get_validation_result()
        
        # 2. Security checks
        self._check_security_patterns(code)
        
        # 3. Django best practices
        self._check_django_best_practices(code)
        
        # 4. Import checks
        self._check_imports(code)
        
        # 5. AST-based checks
        self._check_with_ast(code)
        
        return self._get_validation_result()
    
    def validate_javascript_code(self, code: str, file_path: str = '') -> Dict:
        """Validate JavaScript code (basic checks)"""
        self.issues = []
        
        # Check for dangerous patterns in JS
        dangerous_js_patterns = {
            'eval': r'\beval\s*\(',
            'Function_constructor': r'new\s+Function\s*\(',
            'document_write': r'document\.write\s*\(',
            'innerHTML': r'\.innerHTML\s*=',
            'setTimeout_string': r'setTimeout\s*\(\s*["\']',
            'setInterval_string': r'setInterval\s*\(\s*["\']',
        }
        
        for pattern_name, pattern in dangerous_js_patterns.items():
            if re.search(pattern, code):
                self.issues.append({
                    'type': 'security',
                    'message': f'Potensi kode berbahaya: {pattern_name}',
                    'severity': 'high'
                })
        
        # Check for CSRF token in AJAX
        if 'fetch' in code or 'XMLHttpRequest' in code or '$.ajax' in code:
            if 'X-CSRFToken' not in code and 'csrfmiddlewaretoken' not in code:
                self.issues.append({
                    'type': 'security',
                    'message': 'AJAX request harus menyertakan CSRF token',
                    'severity': 'high'
                })
        
        return self._get_validation_result()
    
    def validate_html_template(self, code: str, file_path: str = '') -> Dict:
        """Validate Django HTML template"""
        self.issues = []
        
        # Check for unescaped output
        if '{{ ' in code and '|safe' in code:
            self.issues.append({
                'type': 'security',
                'message': 'Penggunaan |safe filter berpotensi XSS',
                'severity': 'medium'
            })
        
        # Check for proper CSRF token
        if '<form' in code and '{% csrf_token %}' not in code:
            self.issues.append({
                'type': 'security',
                'message': 'Form harus menyertakan {% csrf_token %}',
                'severity': 'high'
            })
        
        # Check for proper block structure
        open_blocks = len(re.findall(r'{%\s*block\s+\w+\s*%}', code))
        close_blocks = len(re.findall(r'{%\s*endblock', code))
        if open_blocks != close_blocks:
            self.issues.append({
                'type': 'syntax',
                'message': f'Block tags tidak seimbang: {open_blocks} open, {close_blocks} close',
                'severity': 'high'
            })
        
        return self._get_validation_result()
    
    def _check_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
        """Check Python syntax"""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)
    
    def _check_security_patterns(self, code: str):
        """Check for dangerous security patterns"""
        for pattern_name, pattern_info in self.DANGEROUS_PATTERNS.items():
            matches = list(re.finditer(pattern_info['pattern'], code, re.IGNORECASE))
            for match in matches:
                # Get line number
                line_num = code[:match.start()].count('\n') + 1
                
                self.issues.append({
                    'type': 'security',
                    'pattern': pattern_name,
                    'message': pattern_info['message'],
                    'severity': pattern_info['severity'],
                    'line': line_num,
                    'context': code[max(0, match.start()-30):min(len(code), match.end()+30)]
                })
    
    def _check_django_best_practices(self, code: str):
        """Check Django best practices"""
        for practice_name, practice_info in self.DJANGO_BEST_PRACTICES.items():
            if practice_info['check'](code):
                self.issues.append({
                    'type': 'best_practice',
                    'message': practice_info['message'],
                    'severity': practice_info['severity']
                })
    
    def _check_imports(self, code: str):
        """Check imports for unused or dangerous modules"""
        try:
            tree = ast.parse(code)
            
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
            
            # Check for dangerous imports
            dangerous_modules = ['pickle', 'marshal', 'ctypes', 'subprocess']
            for imp in imports:
                for dangerous in dangerous_modules:
                    if dangerous in imp:
                        self.issues.append({
                            'type': 'security',
                            'message': f'Modul {dangerous} berpotensi berbahaya',
                            'severity': 'high'
                        })
        
        except Exception:
            pass
    
    def _check_with_ast(self, code: str):
        """Advanced checks using AST"""
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Check for bare except
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        self.issues.append({
                            'type': 'best_practice',
                            'message': 'Hindari penggunaan bare except:',
                            'severity': 'medium',
                            'line': node.lineno
                        })
                
                # Check for mutable default arguments
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            self.issues.append({
                                'type': 'best_practice',
                                'message': f'Hindari mutable default argument di fungsi {node.name}',
                                'severity': 'medium',
                                'line': node.lineno
                            })
                
                # Check for SQL string formatting
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['execute', 'raw', 'extra']:
                            # Check if using string formatting
                            for arg in node.args:
                                if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
                                    self.issues.append({
                                        'type': 'security',
                                        'message': 'SQL query menggunakan string formatting - risiko SQL injection',
                                        'severity': 'critical',
                                        'line': node.lineno
                                    })
        
        except Exception:
            pass
    
    def _get_validation_result(self) -> Dict:
        """Get final validation result"""
        critical = [i for i in self.issues if i.get('severity') == 'critical']
        high = [i for i in self.issues if i.get('severity') == 'high']
        medium = [i for i in self.issues if i.get('severity') == 'medium']
        low = [i for i in self.issues if i.get('severity') == 'low']
        
        is_valid = len(critical) == 0 and len(high) == 0
        
        return {
            'is_valid': is_valid,
            'can_apply_with_warning': len(critical) == 0,
            'issues_count': {
                'critical': len(critical),
                'high': len(high),
                'medium': len(medium),
                'low': len(low),
                'total': len(self.issues)
            },
            'issues': self.issues,
            'critical_issues': critical,
            'high_issues': high,
            'medium_issues': medium,
            'low_issues': low,
        }
    
    def validate_file_change(self, file_path: str, original_code: str, new_code: str) -> Dict:
        """Validate a file change"""
        # Determine file type
        if file_path.endswith('.py'):
            return self.validate_python_code(new_code, file_path)
        elif file_path.endswith('.js'):
            return self.validate_javascript_code(new_code, file_path)
        elif file_path.endswith('.html'):
            return self.validate_html_template(new_code, file_path)
        else:
            return {
                'is_valid': True,
                'can_apply_with_warning': True,
                'issues_count': {'total': 0},
                'issues': [],
                'message': 'File type tidak dikenali, validasi dilewati'
            }


def validate_code(code: str, file_path: str = '', language: str = 'python') -> Dict:
    """Convenience function to validate code"""
    validator = CodeValidator()
    
    if language == 'python' or file_path.endswith('.py'):
        return validator.validate_python_code(code, file_path)
    elif language == 'javascript' or file_path.endswith('.js'):
        return validator.validate_javascript_code(code, file_path)
    elif language == 'html' or file_path.endswith('.html'):
        return validator.validate_html_template(code, file_path)
    else:
        return validator.validate_python_code(code, file_path)
