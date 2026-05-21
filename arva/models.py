"""
Model Arviga Project Manager
=============================
Mendefinisikan seluruh model data aplikasi:
- WebsiteSettings: Pengaturan global website
- UserProfile: Profil tambahan user
- Project: Project/kanban board
- SubProject: Sub-project dalam project
- ProjectMember: Keanggotaan project
- Label: Label/tag untuk task
- TaskList: Kolom/daftar dalam kanban
- Task: Task/card dalam project
- Comment: Komentar pada task
- Attachment: Lampiran file pada task
- ChecklistItem: Item checklist pada task
- ActivityLog: Log aktivitas
- UserActivity: Tracking aktivitas user
- AIChatMessage: Pesan chat AI
- AIFeatureRequest: Request AI Developer
- AISettings: Pengaturan AI
- AICodeChange: Perubahan kode dari AI Developer
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from pathlib import PurePosixPath
from .utils import get_date


def user_avatar_path(instance, filename):
    """Path penyimpanan avatar user: avatars/user_{id}/{filename}"""
    return "avatars/user_{0}/{1}".format(instance.user.id, filename)

def logo_path(instance, filename):
    """Path penyimpanan logo website: branding/logo/{filename}"""
    return f"branding/logo/{filename}"

def favicon_path(instance, filename):
    """Path penyimpanan favicon website: branding/favicon/{filename}"""
    return f"branding/favicon/{filename}"


# ============================================================
# PENGATURAN WEBSITE
# ============================================================

class WebsiteSettings(models.Model):
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_AUTO = "auto"

    THEME_CHOICES = (
        (THEME_LIGHT, "Light"),
        (THEME_DARK, "Dark"),
        (THEME_AUTO, "Auto"),
    )

    site_name = models.CharField(max_length=100, default="Arviga Project Manager")
    logo = models.ImageField(upload_to=logo_path, blank=True, null=True)
    favicon = models.ImageField(upload_to=favicon_path, blank=True, null=True)
    primary_color = models.CharField(max_length=20, default="#09affe")
    theme_mode = models.CharField(max_length=10, choices=THEME_CHOICES, default=THEME_LIGHT)
    navbar_bg = models.CharField(max_length=20, default="#09affe")
    body_bg = models.CharField(max_length=20, default="#f7f7f7")
    text_color = models.CharField(max_length=20, default="#333333")

    footer_text = models.CharField(max_length=200, default="© 2025 Arviga Project Manager")
    support_email = models.EmailField(default="support@arviga.co.id")
    maintenance_mode = models.BooleanField(default=False)

    custom_css = models.TextField(blank=True, null=True)

    def __str__(self):
        return "Website Settings"

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        return "/static/arva/img/default-logo.png"

    @property
    def favicon_url(self):
        if self.favicon:
            return self.favicon.url
        return "/static/arva/img/default-favicon.png"

# ============================================================
# PROFIL USER
# ============================================================

class UserProfile(models.Model):
    """Profil tambahan untuk user.
    
    Menyimpan preferensi tema, layout, avatar, dan informasi Google Auth.
    Memiliki relasi OneToOne dengan User bawaan Django.
    """
    THEME_INHERIT = "inherit"
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_AUTO = "auto"

    THEME_CHOICES = (
        (THEME_INHERIT, "Ikuti Website"),
        (THEME_LIGHT, "Light"),
        (THEME_DARK, "Dark"),
        (THEME_AUTO, "Auto"),
    )
    LAYOUT_SIDEBAR = "sidebar"
    LAYOUT_CLASSIC = "classic"
    LAYOUT_CHOICES = (
        (LAYOUT_SIDEBAR, "Sidebar Layout"),
        (LAYOUT_CLASSIC, "Classic Layout"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    avatar_icon = models.CharField(max_length=100, blank=True, null=True)
    google_id = models.CharField(max_length=100, blank=True, null=True)
    theme_preference = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default=THEME_INHERIT,
    )
    layout_preference = models.CharField(
        max_length=10,
        choices=LAYOUT_CHOICES,
        default=LAYOUT_SIDEBAR,
    )
    
    # Google OAuth verification
    is_verified = models.BooleanField(
        default=True,
        help_text="User sudah diverifikasi oleh admin"
    )
    pending_approval = models.BooleanField(
        default=False,
        help_text="User menunggu approval dari admin (Google OAuth signup)"
    )

    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        if self.avatar_icon:
            return f"/static/arva/img/profile/{self.avatar_icon}"
        return "/static/arva/img/default-avatar.png"

# ============================================================
# PROJECT & KANBAN BOARD
# ============================================================

class Project(models.Model):
    """Model utama project/kanban board.
    
    Project bisa berupa board biasa (kanban) atau project terstruktur.
    Project terstruktur memiliki fitur tambahan: sub-project, prioritas P0-P4,
    status task terstruktur, dan bisa ditutup (closed).
    """
    PRIORITY_P0 = "p0"
    PRIORITY_P1 = "p1"
    PRIORITY_P2 = "p2"
    PRIORITY_P3 = "p3"
    PRIORITY_P4 = "p4"
    PRIORITY_CHOICES = (
        (PRIORITY_P0, "P0 - Urgent"),
        (PRIORITY_P1, "P1 - High"),
        (PRIORITY_P2, "P2 - Medium"),
        (PRIORITY_P3, "P3 - Low"),
        (PRIORITY_P4, "P4 - Very Low"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_private = models.BooleanField(default=False)
    is_project = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    priority = models.CharField(max_length=2, choices=PRIORITY_CHOICES, default=PRIORITY_P2)
    pm_assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_projects')
    start_date = models.DateField(null=True, blank=True)
    start_date_tbd = models.BooleanField(default=False)
    etd = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.is_project:
            if not self.start_date and not self.start_date_tbd:
                errors["start_date"] = "Start Date is required or mark it as TBD."
                errors["start_date_tbd"] = "Mark Start Date as TBD if date is unknown."
            if not self.etd:
                errors["etd"] = "ETD is required when Is Project is enabled."
        if self.start_date and self.start_date_tbd:
            errors["start_date_tbd"] = "Choose either Start Date or TBD, not both."
        if self.start_date and self.etd and self.etd < self.start_date:
            errors["etd"] = "ETD cannot be earlier than Start Date."
        if errors:
            raise ValidationError(errors)

    def get_user_role(self, user):
        if not user.is_authenticated:
            return None
        # Role-based access is deprecated; keep a single legacy role token for UI.
        if not self.is_private:
            return ProjectMember.ROLE_ADMIN
        if self.owner == user:
            return ProjectMember.ROLE_ADMIN
        if self.memberships.filter(user=user).exists():
            return ProjectMember.ROLE_ADMIN
        return None

    def can_user_view(self, user):
        return self.get_user_role(user) is not None

    @property
    def access_scope_label(self):
        return "Private" if self.is_private else "Shared with all users"

    @property
    def shared_user_count(self):
        return self.memberships.count()
    
    @property
    def progress(self):
        total = self.tasks.filter(is_archived=False).count()
        done = self.tasks.filter(is_archived=False, task_list__name__iexact="Done").count()
        if total == 0:
            percent = 0
        else:
            percent = int((done / total) * 100)
        return {"total": total, "done": done, "percent": percent}

    @property
    def subproject_progress(self):
        subs = list(self.subprojects.all())
        total = len(subs)
        if total == 0:
            return {"total": 0, "done": 0, "percent": 0}
        done = sum(1 for sp in subs if sp.progress["percent"] == 100)
        percent = int((done / total) * 100)
        return {"total": total, "done": done, "percent": percent}

# ============================================================
# SUB-PROJECT
# ============================================================

class SubProject(models.Model):
    """Sub-project dalam project terstruktur.
    
    Setiap sub-project memiliki TaskList dan task sendiri.
    Bisa dikonversi menjadi project mandiri.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='subprojects')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    @property
    def progress(self):
        total = self.tasks.filter(is_archived=False).count()
        done = self.tasks.filter(is_archived=False, task_list__name__iexact="Done").count()
        if total == 0:
            percent = 0
        else:
            percent = int((done / total) * 100)
        return {"total": total, "done": done, "percent": percent}

# ============================================================
# KEANGGOTAAN PROJECT
# ============================================================

class ProjectMember(models.Model):
    """Keanggotaan user dalam project.
    
    Catatan: Sistem role sudah disederhanakan.
    Semua member sekarang memiliki role yang sama (ROLE_MEMBER).
    """
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = (
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
        (ROLE_VIEWER, 'Viewer'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.username} @ {self.project.name} ({self.role})"

# ============================================================
# LABEL & TASK LIST
# ============================================================

class Label(models.Model):
    """Label/tag untuk mengkategorikan task."""
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default='primary')

    def __str__(self):
        return self.name

class TaskList(models.Model):
    """Kolom/daftar dalam kanban board.
    
    Contoh: To Do, In Progress, Done.
    Setiap TaskList dimiliki oleh project dan opsional sub-project.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='lists')
    sub_project = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='lists', null=True, blank=True)
    name = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.project.name} - {self.name}"

# ============================================================
# TASK
# ============================================================

class Task(models.Model):
    """Model task/card dalam project.
    
    Task memiliki dua mode:
    1. Board biasa: menggunakan task_list (To Do, In Progress, Done)
    2. Project terstruktur: menggunakan status (-, in_progress, done, infeasible)
       dan prioritas (p0-p4)
    
    Task juga menyimpan hasil analisis AI jika sudah dianalisis.
    """
    PRIORITY_P0 = 'p0'
    PRIORITY_P1 = 'p1'
    PRIORITY_P2 = 'p2'
    PRIORITY_P3 = 'p3'
    PRIORITY_P4 = 'p4'
    PRIORITY_LOW = 'low'      # legacy
    PRIORITY_MEDIUM = 'medium'  # legacy
    PRIORITY_HIGH = 'high'      # legacy
    PRIORITY_CRITICAL = 'critical'  # legacy
    PRIORITY_CHOICES = (
        (PRIORITY_P0, 'P0 - Urgent'),
        (PRIORITY_P1, 'P1 - High'),
        (PRIORITY_P2, 'P2 - Medium'),
        (PRIORITY_P3, 'P3 - Low'),
        (PRIORITY_P4, 'P4 - Very Low'),
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    )
    STATUS_NONE = '-'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_INFEASIBLE = 'infeasible'
    STATUS_CHOICES = (
        (STATUS_NONE, '-'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE, 'Done'),
        (STATUS_INFEASIBLE, 'Infeasible'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    sub_project = models.ForeignKey(SubProject, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    task_list = models.ForeignKey(TaskList, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_P2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NONE)
    start_date = models.DateField(null=True, blank=True)
    start_date_tbd = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    labels = models.ManyToManyField(Label, blank=True, related_name='tasks')
    assignees = models.ManyToManyField(User, blank=True, related_name='assigned_tasks')
    cover_color = models.CharField(max_length=20, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # AI Priority Analysis Fields
    ai_priority_score = models.IntegerField(null=True, blank=True, help_text="AI-calculated priority score (1-100)")
    ai_priority_reason = models.TextField(blank=True, help_text="AI reasoning for priority recommendation")
    ai_complexity = models.CharField(max_length=10, blank=True, help_text="AI-estimated complexity")
    ai_estimated_hours = models.IntegerField(null=True, blank=True, help_text="AI-estimated hours to complete")
    ai_analyzed_at = models.DateTimeField(null=True, blank=True, help_text="Last AI analysis timestamp")

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    @property
    def checklist_total(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        items = cache.get("checklist_items")
        if items is not None:
            return len(items)
        return self.checklist_items.count()

    @property
    def checklist_done(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        items = cache.get("checklist_items")
        if items is not None:
            return sum(1 for item in items if item.is_done)
        return self.checklist_items.filter(is_done=True).count()

    @property
    def is_overdue(self):
        if not self.due_date:
            return False
        return get_date(self.due_date) < timezone.localdate()

    @property
    def is_due_today(self):
        if not self.due_date:
            return False
        return get_date(self.due_date) == timezone.localdate()

    @property
    def is_due_soon(self):
        if not self.due_date:
            return False
        return 0 <= (get_date(self.due_date) - timezone.localdate()).days <= 2

    @property
    def checklist_percent(self):
        total = self.checklist_total
        if total == 0:
            return 0
        return int((self.checklist_done / total) * 100)

# ============================================================
# KOMENTAR, LAMPIRAN, CHECKLIST
# ============================================================

class Comment(models.Model):
    """Komentar pada task. Mendukung threaded comment (balasan)."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user} - {self.content[:30]}'

class Attachment(models.Model):
    """Lampiran file pada task."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, null=True, blank=True, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name

    @property
    def filename(self):
        return PurePosixPath(self.file.name or '').name

    @property
    def is_image(self):
        return PurePosixPath(self.file.name or '').suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

class ChecklistItem(models.Model):
    """Item checklist pada task. Bisa dicentang (is_done) sebagai progress."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    content = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.content

# ============================================================
# LOG AKTIVITAS & TRACKING USER
# ============================================================

class ActivityLog(models.Model):
    """Log aktivitas dalam project.
    
    Mencatat semua aksi penting: buat task, pindah task, komentar, dll.
    Digunakan di halaman Activity Log dan untuk tracking performa.
    """
    ACTION_CHOICES = (
        ('project_created', 'Project Created'),
        ('project_updated', 'Project Updated'),
        ('project_deleted', 'Project Deleted'),
        ('list_created', 'List Created'),
        ('list_renamed', 'List Renamed'),
        ('list_deleted', 'List Deleted'),
        ('list_archived', 'List Archived'),
        ('list_unarchived', 'List Unarchived'),
        ('list_moved', 'List Moved'),
        ('task_created', 'Task Created'),
        ('task_updated', 'Task Updated'),
        ('task_deleted', 'Task Deleted'),
        ('task_archived', 'Task Archived'),
        ('task_unarchived', 'Task Unarchived'),
        ('task_moved', 'Task Moved'),
        ('comment_added', 'Comment Added'),
        ('attachment_added', 'Attachment Added'),
        ('checklist_added', 'Checklist Added'),
        ('checklist_toggled', 'Checklist Toggled'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} by {self.user} at {self.created_at}'

class UserActivity(models.Model):
    """Tracking aktivitas user (terakhir aktif, status online)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} Activity"


class UserNotification(models.Model):
    """Notifikasi kolaborasi (mis. user di-mention pada komentar/reply)."""
    # Keep DB constraints disabled to avoid FK migration failures on existing MySQL schemas.
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='arva_notifications', db_constraint=False)
    actor = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='arva_sent_notifications', db_constraint=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, related_name='user_notifications', db_constraint=False)
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_notifications', db_constraint=False)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        recipient_name = self.recipient.username if self.recipient else "Unknown"
        return f"{recipient_name}: {self.message}"

# ============================================================
# AI CHAT
# ============================================================

class AIChatMessage(models.Model):
    """Pesan dalam percakapan AI Chat.
    
    Setiap user memiliki percakapan sendiri (private).
    Role bisa 'user' atau 'assistant'.
    """
    """Model untuk menyimpan percakapan AI Chat (private per user)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_chat_messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'AI Assistant')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Context yang disimpan saat chat dibuat
    context_tasks = models.JSONField(default=list, blank=True, help_text="Task IDs yang direferensikan")
    
    class Meta:
        ordering = ['created_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.role} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# setting ai

# ============================================================
# AI DEVELOPER
# ============================================================

class AIFeatureRequest(models.Model):
    """Request fitur/bugfix ke AI Developer.
    
    Menyimpan seluruh informasi tentang request: deskripsi,
    status proses, progress tracking, dan hasil code changes.
    """
    """Model untuk menyimpan request fitur baru atau bug fix - Versi Optimal"""
    
    # Pilihan tipe request
    REQUEST_TYPE_CHOICES = (
        ('bugfix', 'Perbaikan Bug'),
        ('feature', 'Fitur Baru'),
        ('improvement', 'Peningkatan'),
        ('refactor', 'Refactor'),
    )
    
    # Pilihan status dengan alur yang lebih detail
    STATUS_CHOICES = (
        ('pending', 'Menunggu'),
        ('validating', 'Memvalidasi Request'),
        ('discovering', 'Menemukan File Terkait'),
        ('analyzing', 'Menganalisis Kode'),
        ('planning', 'Membuat Rencana'),
        ('generating', 'Menghasilkan Kode'),
        ('validating_code', 'Memvalidasi Kode'),
        ('reviewing', 'Menunggu Review'),
        ('applying', 'Menerapkan Perubahan'),
        ('testing', 'Menguji'),
        ('completed', 'Selesai'),
        ('failed', 'Gagal'),
        ('cancelled', 'Dibatalkan'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Rendah'),
        ('medium', 'Sedang'),
        ('high', 'Tinggi'),
        ('critical', 'Kritis'),
    )
    
    # Informasi dasar
    title = models.CharField(max_length=255, verbose_name="Judul")
    description = models.TextField(verbose_name="Deskripsi")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='feature', verbose_name="Tipe Request")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Prioritas")
    
    # Informasi user
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_requests', verbose_name="Dibuat Oleh")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_ai_requests', verbose_name="Ditugaskan Kepada")
    
    # Konteks kode
    related_files = models.JSONField(default=list, blank=True, help_text="Daftar file yang terkait dengan request ini")
    affected_models = models.JSONField(default=list, blank=True, help_text="Model Django yang terpengaruh")
    dependency_graph = models.JSONField(default=dict, blank=True, help_text="Graf dependensi antar file")
    
    # Analisis AI
    analysis_result = models.JSONField(default=dict, blank=True, help_text="Hasil analisis AI terhadap codebase")
    implementation_plan = models.JSONField(default=dict, blank=True, help_text="Rencana implementasi yang dibuat AI")
    complexity_score = models.IntegerField(null=True, blank=True, help_text="Skor kompleksitas (1-100)")
    estimated_effort = models.CharField(max_length=50, blank=True, help_text="Estimasi waktu pengerjaan")
    
    # Progress tracking yang lebih detail
    current_step = models.IntegerField(default=0, help_text="Langkah saat ini dalam proses")
    total_steps = models.IntegerField(default=7, help_text="Total langkah dalam proses")
    step_description = models.CharField(max_length=255, blank=True, help_text="Deskripsi langkah saat ini")
    progress_percent = models.IntegerField(default=0, help_text="Persentase progress (0-100)")
    
    # Informasi pembatalan
    is_cancelled = models.BooleanField(default=False, help_text="Apakah request dibatalkan")
    cancelled_at = models.DateTimeField(null=True, blank=True, help_text="Waktu pembatalan")
    cancel_reason = models.TextField(blank=True, help_text="Alasan pembatalan")
    
    # Error tracking
    error_count = models.IntegerField(default=0, help_text="Jumlah error yang terjadi")
    last_error = models.TextField(blank=True, help_text="Error terakhir yang terjadi")
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Dibuat")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Waktu Diupdate")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Dimulai")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Selesai")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Feature Request'
        verbose_name_plural = 'AI Feature Requests'
    
    def __str__(self):
        return f"[{self.get_request_type_display()}] {self.title}"
    
    @property
    def duration(self):
        """Menghitung durasi dalam detik"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def duration_formatted(self):
        """Format durasi dalam bentuk yang mudah dibaca"""
        duration = self.duration
        if duration is None:
            return "-"
        
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            return f"{hours}j {minutes}m {seconds}d"
        elif minutes > 0:
            return f"{minutes}m {seconds}d"
        else:
            return f"{seconds}d"

    @property
    def status_color(self):
        """Mengembalikan kelas warna Bootstrap berdasarkan status"""
        colors = {
            'pending': 'secondary',
            'validating': 'info',
            'discovering': 'info',
            'analyzing': 'info',
            'planning': 'primary',
            'generating': 'primary',
            'validating_code': 'warning',
            'reviewing': 'warning',
            'applying': 'primary',
            'testing': 'info',
            'completed': 'success',
            'failed': 'danger',
            'cancelled': 'dark',
        }
        return colors.get(self.status, 'secondary')

    @property
    def progress(self):
        """Mengembalikan persentase progress berdasarkan status"""
        # Gunakan progress_percent jika sudah diupdate
        if self.progress_percent > 0:
            return self.progress_percent
            
        progress_map = {
            'pending': 0,
            'validating': 5,
            'discovering': 10,
            'analyzing': 20,
            'planning': 35,
            'generating': 55,
            'validating_code': 70,
            'reviewing': 80,
            'applying': 90,
            'testing': 95,
            'completed': 100,
            'failed': 0,
            'cancelled': 0,
        }
        return progress_map.get(self.status, 0)
    
    def update_progress(self, step, total_steps=None, description=None, percent=None):
        """Update progress request"""
        self.current_step = step
        if total_steps:
            self.total_steps = total_steps
        if description:
            self.step_description = description
        if percent is not None:
            self.progress_percent = percent
        else:
            # Hitung persentase otomatis
            self.progress_percent = int((step / self.total_steps) * 100)
        self.save(update_fields=['current_step', 'total_steps', 'step_description', 'progress_percent', 'updated_at'])
    
    def cancel(self, reason=""):
        """Membatalkan request"""
        self.is_cancelled = True
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason
        self.save(update_fields=['is_cancelled', 'status', 'cancelled_at', 'cancel_reason', 'updated_at'])


class AICodeChange(models.Model):
    """Perubahan kode yang dihasilkan AI Developer.
    
    Setiap code change berisi file path, diff, dan status
    (pending, applied, rejected, failed).
    """
    """Model untuk menyimpan perubahan kode yang dihasilkan AI"""
    
    CHANGE_TYPE_CHOICES = (
        ('add', 'Add'),
        ('modify', 'Modify'),
        ('delete', 'Delete'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied'),
        ('rolled_back', 'Rolled Back'),
    )
    
    # Relations
    request = models.ForeignKey(AIFeatureRequest, on_delete=models.CASCADE, related_name='code_changes')
    
    # File info
    file_path = models.CharField(max_length=500)
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPE_CHOICES, default='modify')
    
    # Code content
    original_code = models.TextField(blank=True, help_text="Kode sebelum perubahan")
    new_code = models.TextField(help_text="Kode setelah perubahan")
    diff_content = models.TextField(help_text="Unified diff format")
    
    # Metadata
    line_start = models.IntegerField(null=True, blank=True, help_text="Baris awal perubahan")
    line_end = models.IntegerField(null=True, blank=True, help_text="Baris akhir perubahan")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_changes')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    
    # Error tracking
    has_error = models.BooleanField(default=False, help_text="True if code generation failed for this change")
    error_message = models.TextField(blank=True, help_text="Error message if generation failed")
    
    # Backup
    backup_path = models.CharField(max_length=500, blank=True, help_text="Path ke backup file")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'AI Code Change'
        verbose_name_plural = 'AI Code Changes'
    
    def __str__(self):
        return f"{self.get_change_type_display()} {self.file_path}"

    def save(self, *args, **kwargs):
        """Override save untuk validasi dan pembersihan kode"""
        # Bersihkan new_code dari JSON wrapper jika ada
        if self.new_code:
            self.new_code = self._clean_code_content(self.new_code)
        if self.original_code:
            self.original_code = self._clean_code_content(self.original_code)
        super().save(*args, **kwargs)

    def _clean_code_content(self, code: str) -> str:
        """Bersihkan kode dari JSON wrapper atau format yang tidak diinginkan"""
        import json
        
        code = code.strip()
        
        # Cek apakah ini JSON wrapper
        if code.startswith('{') and code.endswith('}'):
            try:
                parsed = json.loads(code)
                if isinstance(parsed, dict):
                    # Coba ekstrak dari key yang umum digunakan
                    for key in ['modified_code', 'code', 'new_code', 'content', 'output']:
                        if key in parsed and isinstance(parsed[key], str):
                            # Rekursif untuk kasus nested
                            return self._clean_code_content(parsed[key])
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Cek apakah ini markdown code block dengan JSON di dalamnya
        if code.startswith('```'):
            lines = code.split('\n')
            if len(lines) > 1:
                # Hapus first line (```python atau ```json atau ```)
                # Hapus last line (```)
                inner_code = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
                # Coba parse sebagai JSON lagi
                inner_code = inner_code.strip()
                if inner_code.startswith('{') and inner_code.endswith('}'):
                    try:
                        parsed = json.loads(inner_code)
                        if isinstance(parsed, dict):
                            for key in ['modified_code', 'code', 'new_code', 'content', 'output']:
                                if key in parsed and isinstance(parsed[key], str):
                                    return self._clean_code_content(parsed[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
                return inner_code
            return code
        
        return code

    def validate_for_apply(self) -> tuple:
        """
        Validasi kode sebelum di-apply.
        Returns (is_valid, error_message)
        """
        # Cek untuk template files
        if self.file_path.endswith('.html'):
            return self._validate_django_template()
        
        # Cek untuk Python files
        if self.file_path.endswith('.py'):
            return self._validate_python_code()
        
        # File lain dianggap valid
        return True, None

    def _validate_django_template(self) -> tuple:
        """Validasi Django template syntax"""
        code = self.new_code
        
        # Cek apakah masih ada JSON wrapper yang lolos
        if code.strip().startswith('{') and '"modified_code"' in code:
            return False, "Kode masih dibungkus JSON. Silakan regenerate."
        
        # Cek keseimbangan template tags
        import re
        
        # Cek {{ }} tags
        open_vars = len(re.findall(r'\{\{', code))
        close_vars = len(re.findall(r'\}\}', code))
        if open_vars != close_vars:
            return False, f"Template tag tidak seimbang: {{{{ = {open_vars}, }}}} = {close_vars}"
        
        # Cek {% %} tags
        open_tags = len(re.findall(r'\{%', code))
        close_tags = len(re.findall(r'%\}', code))
        if open_tags != close_tags:
            return False, f"Template tag tidak seimbang: {{% = {open_tags}, %}} = {close_tags}"
        
        # Cek block tags yang harus punya end
        block_tags = ['if', 'for', 'with', 'block', 'comment', 'spaceless', 'autoescape', 'verbatim']
        for tag in block_tags:
            start_pattern = rf'\{{%\s*{tag}\b'
            end_pattern = rf'\{{%\s*end{tag}\s*\%}}'
            starts = len(re.findall(start_pattern, code))
            ends = len(re.findall(end_pattern, code))
            if starts != ends:
                return False, f"Block '{tag}' tidak seimbang: start = {starts}, end = {ends}"
        
        return True, None

    def _validate_python_code(self) -> tuple:
        """Validasi Python syntax"""
        import ast
        try:
            ast.parse(self.new_code)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

    @property
    def status_color(self):
        """Return Bootstrap color class based on status"""
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'applied': 'primary',
            'rolled_back': 'secondary',
        }
        return colors.get(self.status, 'secondary')

    def get_diff(self):
        """Return diff content for display"""
        return self.diff_content

    def apply_change(self):
        """
        Apply this code change to the filesystem.
        Returns True if successful, False otherwise.
        """
        from pathlib import Path
        from django.conf import settings
        from django.utils import timezone
        import shutil
        
        try:
            base_path = Path(settings.BASE_DIR)
            full_path = base_path / self.file_path
            
            # Create backup if file exists
            if full_path.exists():
                backup_dir = base_path / '.ai_backups'
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"{self.file_path.replace('/', '_').replace('\\\\', '_')}.{timezone.now().strftime('%Y%m%d_%H%M%S')}.bak"
                shutil.copy2(full_path, backup_path)
                self.backup_path = str(backup_path)
            
            if self.change_type == 'delete':
                # Delete file
                if full_path.exists():
                    full_path.unlink()
            else:
                # Create directory if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write new content
                full_path.write_text(self.new_code, encoding='utf-8')
            
            self.status = 'applied'
            self.applied_at = timezone.now()
            self.save()
            
            return True
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.save()
            return False


# ============================================================
# PENGATURAN AI
# ============================================================

class AISettings(models.Model):
    """Konfigurasi AI yang bisa diubah via halaman settings.
    
    Menyimpan pengaturan provider, model, API key, parameter AI,
    dan toggle fitur AI (priority, chat).
    Hanya ada satu instance aktif (singleton pattern via get_current()).
    """
    
    # Provider choices
    PROVIDER_GOOGLE = 'google'
    PROVIDER_OPENAI = 'openai'
    PROVIDER_OPENCLAW = 'openclaw'
    PROVIDER_QODER = 'qoder'
    PROVIDER_DEEPSEEK = 'deepseek'
    PROVIDER_CHOICES = (
        (PROVIDER_GOOGLE, 'Google Gemini'),
        (PROVIDER_OPENCLAW, 'Open Claw (Self-hosted)'),
        (PROVIDER_OPENAI, 'OpenAI'),
        (PROVIDER_QODER, 'Qoder (Claude)'),
        (PROVIDER_DEEPSEEK, 'DeepSeek API ⭐ Recommended'),
    )
    
    # Model choices untuk Google Gemini
    GEMINI_MODELS = (
        ('gemini-2.5-flash', 'Gemini 2.5 Flash (Recommended)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
    )
    
    # Model choices untuk OpenAI
    OPENAI_MODELS = (
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
    )
    
    # Model choices untuk DeepSeek API
    DEEPSEEK_MODELS = (
        ('deepseek-chat', 'DeepSeek Chat ⭐ Best for Coding (V3.2)'),
        ('deepseek-reasoner', 'DeepSeek Reasoner ⭐ Thinking Mode (V3.2)'),
    )
    
    # DeepSeek API endpoint
    DEEPSEEK_API_URL = 'https://api.deepseek.com'
    
    # Model choices untuk Open Claw / Ollama (bisa custom)
    # Format: (model_name, display_name) - sesuai dengan nama model di Ollama
    OPENCLAW_MODELS = (
        # === LLAMA FAMILY (Meta) ===
        ('llama3.3:70b', 'Llama 3.3 70B ⭐ NEW - Most Capable'),
        ('llama3.2:3b', 'Llama 3.2 3B - Fast & Efficient'),
        ('llama3.2:1b', 'Llama 3.2 1B - Ultra Fast'),
        ('llama3.1:8b', 'Llama 3.1 8B - Balanced'),
        ('llama3.1:70b', 'Llama 3.1 70B - High Quality'),
        ('llama3:8b', 'Llama 3 8B - Stable'),
        ('llama3:70b', 'Llama 3 70B - Premium'),
        
        # === CODELLAMA (Specialized Coding) ===
        ('codellama:7b', 'CodeLlama 7B - Code Specialist'),
        ('codellama:13b', 'CodeLlama 13B - Better Code'),
        ('codellama:34b', 'CodeLlama 34B - Pro Code'),
        ('codellama:70b', 'CodeLlama 70B - Enterprise Code'),
        
        # === DEEPSEEK (Chinese, Excellent for Code) ===
        ('deepseek-coder:6.7b', 'DeepSeek Coder 6.7B ⚡ Fast Code'),
        ('deepseek-coder:33b', 'DeepSeek Coder 33B - Pro Code'),
        ('deepseek-r1:1.5b', 'DeepSeek R1 1.5B - Reasoning'),
        ('deepseek-r1:7b', 'DeepSeek R1 7B - Better Reasoning'),
        ('deepseek-r1:8b', 'DeepSeek R1 8B ⭐ Recommended'),
        ('deepseek-r1:14b', 'DeepSeek R1 14B - Advanced Reasoning'),
        
        # === QWEN (Alibaba, Multilingual) ===
        ('qwen2.5:0.5b', 'Qwen 2.5 0.5B - Ultra Light'),
        ('qwen2.5:1.5b', 'Qwen 2.5 1.5B - Light'),
        ('qwen2.5:3b', 'Qwen 2.5 3B - Efficient'),
        ('qwen2.5:7b', 'Qwen 2.5 7B ⭐ Balanced'),
        ('qwen2.5:14b', 'Qwen 2.5 14B - High Quality'),
        ('qwen2.5:32b', 'Qwen 2.5 32B - Premium'),
        ('qwen2.5-coder:7b', 'Qwen 2.5 Coder 7B - Code Focus'),
        
        # === MISTRAL (European) ===
        ('mistral:7b', 'Mistral 7B v0.3 ⚡ Fast'),
        ('mistral:nemo', 'Mistral NeMo 12B - Balanced'),
        ('mixtral:8x7b', 'Mixtral 8x7B MoE - High Quality'),
        ('mixtral:8x22b', 'Mixtral 8x22B - Enterprise'),
        ('mistral-small:24b', 'Mistral Small 24B - Premium'),
        
        # === PHI (Microsoft) ===
        ('phi3:mini', 'Phi-3 Mini 3.8B - Ultra Fast'),
        ('phi3:medium', 'Phi-3 Medium 14B - Balanced'),
        
        # === GEMMA (Google) ===
        ('gemma2:2b', 'Gemma 2 2B - Light'),
        ('gemma2:9b', 'Gemma 2 9B ⭐ Recommended'),
        ('gemma2:27b', 'Gemma 2 27B - Premium'),
        
        # === SPECIALIZED MODELS ===
        ('starcoder2:3b', 'StarCoder2 3B - Code'),
        ('starcoder2:7b', 'StarCoder2 7B - Better Code'),
        ('starcoder2:15b', 'StarCoder2 15B - Pro Code'),
        ('codegemma:7b', 'CodeGemma 7B - Google Code'),
        ('command-r:35b', 'Command R 35B - RAG Ready'),
        
        # === UTILITY ===
        ('nomic-embed-text', 'Nomic Embed - Embedding Only'),
        ('mxbai-embed-large', 'MxBai Embed - Large Embedding'),
        ('custom', '🔧 Custom Model (manual input)'),
    )
    
    # Ollama default URL
    OLLAMA_DEFAULT_URL = 'http://localhost:11434/v1'
    
    # Model yang paling direkomendasikan untuk coding
    RECOMMENDED_MODELS = [
        'llama3.3:70b',
        'deepseek-r1:8b',
        'qwen2.5:7b',
        'mistral:7b',
        'codellama:13b',
        'gemma2:9b',
    ]
    
    # Models khusus untuk AI Assistant (Chat, Priority Analysis)
    ASSISTANT_MODELS = (
        # === FAST & EFFICIENT (Real-time Chat) ===
        ('llama3.2:1b', '⚡ Llama 3.2 1B - Ultra Fast'),
        ('llama3.2:3b', '⚡ Llama 3.2 3B - Fast & Efficient'),
        ('phi3:mini', '⚡ Phi-3 Mini 3.8B - Ultra Fast'),
        ('gemma2:2b', '⚡ Gemma 2 2B - Light'),
        
        # === BALANCED (Recommended) ===
        ('qwen2.5:7b', '⭐ Qwen 2.5 7B - Multilingual (Recommended)'),
        ('mistral:7b', '⭐ Mistral 7B - Fast & Capable'),
        ('gemma2:9b', '⭐ Gemma 2 9B - Balanced'),
        ('llama3.1:8b', 'Llama 3.1 8B - Balanced'),
        
        # === PREMIUM (Best Quality) ===
        ('llama3.3:70b', '🏆 Llama 3.3 70B - Most Capable'),
        ('qwen2.5:14b', 'Qwen 2.5 14B - High Quality'),
        ('mixtral:8x7b', 'Mixtral 8x7B MoE - Premium'),
    )
    
    # Models khusus untuk AI Developer (Code, Features, Bugs)
    DEVELOPER_MODELS = (
        # === CODE SPECIALISTS ===
        ('deepseek-coder:6.7b', '⭐ DeepSeek Coder 6.7B - Best for Features & Bugs'),
        ('codellama:7b', 'CodeLlama 7B - Basic Coding'),
        ('codellama:13b', 'CodeLlama 13B - Good for Coding'),
        ('codellama:34b', 'CodeLlama 34B - Pro Coding'),
        ('deepseek-coder:33b', 'DeepSeek Coder 33B - Pro Code'),
        ('qwen2.5-coder:7b', 'Qwen 2.5 Coder 7B - Balanced'),
        ('starcoder2:7b', 'StarCoder2 7B'),
        ('codegemma:7b', 'CodeGemma 7B'),
        
        # === REASONING (Bug Analysis) ===
        ('deepseek-r1:8b', '⭐ DeepSeek R1 8B - Reasoning (Recommended)'),
        ('deepseek-r1:14b', 'DeepSeek R1 14B - Advanced Reasoning'),
        
        # === PREMIUM (Complex Features) ===
        ('llama3.3:70b', '🏆 Llama 3.3 70B - Complex Features'),
        ('llama3.1:70b', 'Llama 3.1 70B - Enterprise'),
        ('mixtral:8x7b', 'Mixtral 8x7B - Premium'),
    )
    
    # General settings
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_OPENCLAW)
    base_url = models.CharField(
        max_length=500, 
        blank=True, 
        default='http://localhost:11434/v1',  # Ollama default
        help_text="Base URL untuk AI provider (Ollama: http://localhost:11434/v1, Open Claw: http://localhost:8080/v1)"
    )
    
    # Endpoint alternatif untuk switching cepat
    ollama_url = models.CharField(
        max_length=500, 
        blank=True, 
        default='http://localhost:11434/v1',
        help_text="Ollama endpoint (auto-switch)"
    )
    
    openclaw_url = models.CharField(
        max_length=500, 
        blank=True, 
        default='http://localhost:8080/v1',
        help_text="Open Claw endpoint (auto-switch)"
    )
    api_key = models.CharField(max_length=500, blank=True, help_text="API Key untuk AI provider (kosongkan jika tidak perlu)")
    model_name = models.CharField(
        max_length=100, 
        default='llama3.2:3b',
        help_text="Model AI default (fallback)"
    )
    
    # Model khusus untuk AI Assistant (Chat, Priority Analysis)
    assistant_model = models.CharField(
        max_length=100,
        default='qwen2.5:7b',
        help_text="Model untuk AI Chat Assistant dan Priority Analysis"
    )
    
    # Model khusus untuk AI Developer (Feature, Bug Fix)
    developer_model = models.CharField(
        max_length=100,
        default='deepseek-coder:6.7b',
        help_text="Model untuk pengembangan fitur dan perbaikan bug"
    )
    
    custom_model_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nama model custom jika memilih 'Custom Model' di Open Claw"
    )
    
    # Custom model untuk assistant
    custom_assistant_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom model untuk AI Assistant"
    )
    
    # Custom model untuk developer
    custom_developer_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom model untuk AI Developer"
    )
    
    # AI Parameters
    temperature = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.7,
        help_text="Kreativitas AI (0.0 = deterministik, 1.0 = sangat kreatif)"
    )
    max_tokens = models.IntegerField(
        default=2048,
        help_text="Maximum tokens untuk response"
    )
    
    # Feature toggles
    ai_priority_enabled = models.BooleanField(
        default=True,
        help_text="Enable/Disable fitur AI Priority Queue"
    )
    ai_chat_enabled = models.BooleanField(
        default=True,
        help_text="Enable/Disable fitur AI Chat Assistant"
    )
    ai_developer_enabled = models.BooleanField(
        default=True,
        help_text="Enable/Disable fitur AI Developer"
    )
    
    # Custom prompts (optional advanced settings)
    priority_analysis_prompt = models.TextField(
        blank=True,
        help_text="Custom prompt untuk analisis prioritas (kosongkan untuk menggunakan default)"
    )
    chat_system_prompt = models.TextField(
        blank=True,
        help_text="Custom system prompt untuk chat (kosongkan untuk menggunakan default)"
    )
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='updated_ai_settings'
    )
    
    class Meta:
        verbose_name = 'AI Settings'
        verbose_name_plural = 'AI Settings'
    
    def __str__(self):
        return f"AI Settings - {self.get_provider_display()} ({self.model_name})"
    
    @classmethod
    def get_current(cls):
        """Get current AI settings (single instance)"""
        settings = cls.objects.first()
        if not settings:
            # Create default settings with Ollama
            settings = cls.objects.create(
                provider=cls.PROVIDER_OPENCLAW,
                base_url=cls.OLLAMA_DEFAULT_URL,  # Default to Ollama
                ollama_url=cls.OLLAMA_DEFAULT_URL,
                openclaw_url='http://localhost:8080/v1',
                api_key='',
                model_name='llama3.2:3b',  # Default model
                temperature=0.7,
                max_tokens=2048,
                ai_priority_enabled=True,
                ai_chat_enabled=True,
                ai_developer_enabled=True,
            )
        return settings
    
    def get_active_model(self):
        """Get the actual model name to use (handles custom models) - fallback"""
        # For Google provider, always use Gemini models
        if self.provider == self.PROVIDER_GOOGLE:
            if self.model_name == 'custom' and self.custom_model_name:
                return self.custom_model_name
            # Default to Gemini model
            return 'gemini-2.5-flash'
        
        # For Qoder provider, use Claude models
        if self.provider == self.PROVIDER_QODER:
            if self.model_name == 'custom' and self.custom_model_name:
                return self.custom_model_name
            return 'claude-3-5-sonnet-20241022'  # Default Claude model
        
        # For DeepSeek provider, use DeepSeek models
        if self.provider == self.PROVIDER_DEEPSEEK:
            if self.model_name == 'custom' and self.custom_model_name:
                return self.custom_model_name
            return 'deepseek-chat'  # Default DeepSeek model
        
        # For OpenAI/OpenClaw provider
        if self.model_name == 'custom' and self.custom_model_name:
            return self.custom_model_name
        return self.model_name
    
    def get_assistant_model(self):
        """Get model for AI Assistant (Chat, Priority Analysis)"""
        # If using Google provider, use Gemini models
        if self.provider == self.PROVIDER_GOOGLE:
            if self.assistant_model == 'custom' and self.custom_assistant_model:
                return self.custom_assistant_model
            return 'gemini-2.5-flash'
        
        # For Qoder provider, use Claude models
        if self.provider == self.PROVIDER_QODER:
            if self.assistant_model == 'custom' and self.custom_assistant_model:
                return self.custom_assistant_model
            return 'claude-3-5-sonnet-20241022'
        
        # For DeepSeek provider, use DeepSeek models
        if self.provider == self.PROVIDER_DEEPSEEK:
            if self.assistant_model == 'custom' and self.custom_assistant_model:
                return self.custom_assistant_model
            return 'deepseek-chat'  # Fast and efficient for chat
        
        # For OpenAI/OpenClaw provider
        if self.assistant_model == 'custom' and self.custom_assistant_model:
            return self.custom_assistant_model
        return self.assistant_model or 'qwen2.5:7b'
    
    def get_developer_model(self):
        """Get model for AI Developer (Features, Bug Fixes, Code)"""
        # If using Google provider, use Gemini models
        if self.provider == self.PROVIDER_GOOGLE:
            if self.developer_model in ['custom'] and self.custom_developer_model:
                return self.custom_developer_model
            return 'gemini-2.5-flash'
        
        # For Qoder provider, use Claude models (excellent for coding)
        if self.provider == self.PROVIDER_QODER:
            if self.developer_model == 'custom' and self.custom_developer_model:
                return self.custom_developer_model
            return 'claude-3-5-sonnet-20241022'  # Claude is great for coding
        
        # For DeepSeek provider (excellent for coding, very cheap)
        if self.provider == self.PROVIDER_DEEPSEEK:
            if self.developer_model == 'custom' and self.custom_developer_model:
                return self.custom_developer_model
            return 'deepseek-chat'  # DeepSeek Chat is best for coding
        
        # For OpenAI/OpenClaw provider
        if self.developer_model == 'custom' and self.custom_developer_model:
            return self.custom_developer_model
        return self.developer_model or 'codellama:13b'


# ============================================================
# AI PRIORITY QUEUE USAGE TRACKING
# ============================================================

class AIPriorityUsage(models.Model):
    """Tracking penggunaan AI Priority Queue per user per hari.
    
    Membatasi penggunaan AI Priority Queue menjadi maksimal 2 kali per hari per user
    untuk menghemat token dan mencegah abuse.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_priority_usage')
    date = models.DateField(default=timezone.now)
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'date']
        verbose_name = 'AI Priority Usage'
        verbose_name_plural = 'AI Priority Usage'
    
    @classmethod
    def can_use_priority_queue(cls, user, max_usage=2):
        """Cek apakah user masih bisa menggunakan AI Priority Queue.
        
        Args:
            user: User yang akan dicek
            max_usage: Maksimal penggunaan per hari (default: 2)
            
        Returns:
            tuple: (can_use: bool, remaining: int, message: str)
        """
        today = timezone.now().date()
        usage, created = cls.objects.get_or_create(
            user=user,
            date=today,
            defaults={'usage_count': 0}
        )
        
        if usage.usage_count >= max_usage:
            return False, 0, f"Anda sudah menggunakan AI Priority Queue {max_usage}x hari ini. Silakan coba lagi besok."
        
        remaining = max_usage - usage.usage_count
        return True, remaining, f"Sisa penggunaan hari ini: {remaining}x"
    
    @classmethod
    def increment_usage(cls, user):
        """Tambah counter penggunaan untuk user.
        
        Args:
            user: User yang menggunakan AI Priority Queue
            
        Returns:
            AIPriorityUsage instance
        """
        today = timezone.now().date()
        usage, created = cls.objects.get_or_create(
            user=user,
            date=today,
            defaults={'usage_count': 0}
        )
        usage.usage_count += 1
        usage.save()
        return usage
    
    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.usage_count}x)"
