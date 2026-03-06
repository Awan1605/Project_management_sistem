from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

def user_avatar_path(instance, filename):
    return "avatars/user_{0}/{1}".format(instance.user.id, filename)

def logo_path(instance, filename):
    return f"branding/logo/{filename}"

def favicon_path(instance, filename):
    return f"branding/favicon/{filename}"

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

class UserProfile(models.Model):
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

    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        if self.avatar_icon:
            return f"/static/arva/img/profile/{self.avatar_icon}"
        return "/static/arva/img/default-avatar.png"

class Project(models.Model):
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

class SubProject(models.Model):
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

class ProjectMember(models.Model):
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

class Label(models.Model):
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, default='primary')

    def __str__(self):
        return self.name

class TaskList(models.Model):
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

class Task(models.Model):
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
        return bool(self.due_date and self.due_date < timezone.localdate())

    @property
    def is_due_today(self):
        return bool(self.due_date and self.due_date == timezone.localdate())

    @property
    def is_due_soon(self):
        if not self.due_date:
            return False
        return 0 <= (self.due_date - timezone.localdate()).days <= 2

    @property
    def checklist_percent(self):
        total = self.checklist_total
        if total == 0:
            return 0
        return int((self.checklist_done / total) * 100)

class Comment(models.Model):
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
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name

class ChecklistItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    content = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.content

class ActivityLog(models.Model):
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
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} Activity"

class AIChatMessage(models.Model):
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
