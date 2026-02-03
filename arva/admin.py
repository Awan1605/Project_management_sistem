from django.contrib import admin
from .models import (
    Project, ProjectMember, SubProject, Task, Label, Comment,
    Attachment, ActivityLog, TaskList, ChecklistItem,
    UserProfile, UserActivity, WebsiteSettings
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
