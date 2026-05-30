"""
Admin Interface Arviga Project Manager
========================================
Konfigurasi Django Admin untuk mengelola data melalui panel admin.
Mendaftarkan semua model dengan tampilan list, filter, dan search yang relevan.
"""

from django.contrib import admin
from .models import (
    Project, ProjectMember, SubProject, Task, Label, Comment,
    Attachment, ActivityLog, TaskList, ChecklistItem,
    UserProfile, UserActivity, WebPushSubscription, WebsiteSettings, AIChatMessage, AISettings,
    AIFeatureRequest, AICodeChange
)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    search_fields = ('name', 'owner__username')


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role')
    list_filter = ('role', 'project')
    search_fields = ('project__name', 'user__username')


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'sub_project', 'position', 'is_archived')
    list_filter = ('project', 'sub_project', 'is_archived')
    ordering = ('project', 'sub_project', 'position')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'sub_project', 'task_list', 'priority', 'due_date', 'is_archived')
    list_filter = ('project', 'sub_project', 'task_list', 'priority', 'is_archived')
    search_fields = ('title', 'project__name', 'sub_project__name')


@admin.register(SubProject)
class SubProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'created_at')
    list_filter = ('project',)
    search_fields = ('name', 'project__name')


admin.site.register(Label)
admin.site.register(Comment)
admin.site.register(Attachment)
admin.site.register(ActivityLog)
admin.site.register(ChecklistItem)
admin.site.register(UserProfile)
admin.site.register(UserActivity)
admin.site.register(WebsiteSettings)
admin.site.register(WebPushSubscription)

@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = ('provider', 'assistant_model', 'developer_model', 'base_url', 'temperature', 'ai_priority_enabled', 'ai_chat_enabled', 'updated_at')
    list_filter = ('provider', 'ai_priority_enabled', 'ai_chat_enabled')
    search_fields = ('assistant_model', 'developer_model', 'api_key')
    fieldsets = (
        ('AI Provider Configuration', {
            'description': 'Pilih provider AI dan konfigurasi endpoint',
            'fields': (
                ('provider', 'base_url'),
                ('ollama_url', 'openclaw_url'),
                'api_key',
            )
        }),
        ('AI Assistant Model', {
            'description': 'Model untuk Chat Assistant dan Priority Analysis',
            'fields': (
                'assistant_model',
                'custom_assistant_model',
            )
        }),
        ('AI Developer Model', {
            'description': 'Model untuk pengembangan fitur dan perbaikan bug',
            'fields': (
                'developer_model',
                'custom_developer_model',
            )
        }),
        ('Legacy Model (Fallback)', {
            'description': 'Model default (tidak digunakan jika assistant/developer sudah diset)',
            'fields': ('model_name', 'custom_model_name'),
            'classes': ('collapse',),
        }),
        ('AI Parameters', {
            'description': 'Atur parameter untuk mengontrol perilaku AI',
            'fields': (
                ('temperature', 'max_tokens'),
            )
        }),
        ('Feature Toggles', {
            'description': 'Enable/Disable fitur AI',
            'fields': (
                ('ai_priority_enabled', 'ai_chat_enabled'),
            )
        }),
        ('Custom Prompts (Advanced)', {
            'description': 'Custom prompt untuk analisis AI (opsional - kosongkan untuk menggunakan default)',
            'fields': (
                'priority_analysis_prompt',
                'chat_system_prompt',
            ),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('updated_at',)
    
    def save_model(self, request, obj, form, change):
        # Set updated_by to current user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at', 'content_preview')
    list_filter = ('role', 'user')
    search_fields = ('user__username', 'content')
    readonly_fields = ('user', 'role', 'content', 'created_at', 'context_tasks')
    
    def content_preview(self, obj):
        return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'


class AICodeChangeInline(admin.TabularInline):
    model = AICodeChange
    extra = 0
    readonly_fields = ('file_path', 'change_type', 'status', 'created_at')
    fields = ('file_path', 'change_type', 'status', 'created_at')
    can_delete = False


@admin.register(AIFeatureRequest)
class AIFeatureRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'request_type', 'priority', 'status', 'created_by', 'created_at')
    list_filter = ('request_type', 'priority', 'status', 'created_at')
    search_fields = ('title', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'started_at', 'completed_at', 'updated_at')
    inlines = [AICodeChangeInline]
    fieldsets = (
        ('Request Info', {
            'fields': ('title', 'description', 'request_type', 'priority', 'status')
        }),
        ('Users', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Code Context', {
            'fields': ('related_files', 'affected_models'),
            'classes': ('collapse',)
        }),
        ('AI Analysis', {
            'fields': ('analysis_result', 'implementation_plan'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AICodeChange)
class AICodeChangeAdmin(admin.ModelAdmin):
    list_display = ('file_path', 'request', 'change_type', 'status', 'created_at')
    list_filter = ('change_type', 'status', 'created_at')
    search_fields = ('file_path', 'request__title')
    readonly_fields = ('created_at', 'applied_at', 'reviewed_at')
