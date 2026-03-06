from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db import transaction, models as dj_models
from django.db.models import Case, IntegerField, Prefetch, Q, Max, When
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.utils.html import strip_tags
from django.utils.timezone import now
from .utils import EmailThread
from .ai_services import get_ai_service, GeminiService, get_ai_chat_service, AIChatService

from .models import (
    Project, ProjectMember, SubProject, Task, Comment, Attachment,
    ActivityLog, TaskList, ChecklistItem, Label,
    UserProfile, UserActivity, WebsiteSettings, AIChatMessage
)
from .forms import (
    RegisterForm, ProjectForm, SubProjectForm, TaskForm,
    CommentForm, AttachmentForm, TaskListForm,
    ChecklistItemForm, ProjectMemberForm, 
    CreateUserInlineForm, UserEditForm, AdminPasswordResetForm,
    AvatarUploadForm, WebsiteSettingsForm
)

User = get_user_model()


STRUCTURED_TASK_PRIORITIES = {
    Task.PRIORITY_P0,
    Task.PRIORITY_P1,
    Task.PRIORITY_P2,
    Task.PRIORITY_P3,
    Task.PRIORITY_P4,
}
STRUCTURED_TASK_STATUSES = {
    Task.STATUS_NONE,
    Task.STATUS_IN_PROGRESS,
    Task.STATUS_DONE,
    Task.STATUS_INFEASIBLE,
}


def get_accessible_projects_queryset(user):
    return Project.objects.filter(
        Q(is_private=False) |
        Q(owner=user) |
        Q(memberships__user=user)
    ).distinct()

def register(request):
    if request.user.is_authenticated:
        return redirect('project_list')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('project_list')
    else:
        form = RegisterForm()
    return render(request, 'arva/auth_register.html', {'form': form})

def custom_logout(request):
    """Custom logout view that works with allauth."""
    from django.contrib.auth import logout
    
    # Perform Django logout (works for both GET and POST)
    logout(request)
    
    # Clear any allauth specific session data if exists
    if 'allauth' in request.session:
        del request.session['allauth']
    
    # Redirect to login page
    return redirect('login')

def get_user_project_or_404(user, pk):
    qs = get_accessible_projects_queryset(user)
    return get_object_or_404(qs, pk=pk)

def get_project_subproject_or_404(project, sub_id):
    return get_object_or_404(SubProject, id=sub_id, project=project)

def get_role(user, project):
    if not project.can_user_view(user):
        return None
    # Legacy templates/endpoints still branch on "admin".
    # With role-based access removed, all project-access users are treated uniformly.
    return ProjectMember.ROLE_ADMIN

def require_role(user, project, allowed_roles):
    # Team/role gating is deprecated. Preserve owner-only control for endpoints
    # that previously required admin, and allow project-access users otherwise.
    normalized = set(allowed_roles or [])
    if normalized == {ProjectMember.ROLE_ADMIN}:
        return project.owner_id == user.id
    return project.can_user_view(user)


def is_project_locked(project):
    return bool(project.is_project and project.is_closed)


def closed_project_error():
    return JsonResponse({
        'success': False,
        'error': 'Project is closed. Re-open the project to make changes.'
    }, status=400)

def sync_project_shares(project, cleaned_data):
    selected_users = cleaned_data.get('shared_users') or User.objects.none()
    selected_ids = set(selected_users.values_list('id', flat=True))

    if project.is_private:
        # Private projects are owner + explicitly shared users only.
        project.memberships.exclude(user_id__in=selected_ids).delete()
        for user in selected_users:
            membership, _ = ProjectMember.objects.get_or_create(
                project=project,
                user=user,
                defaults={'role': ProjectMember.ROLE_MEMBER},
            )
            if membership.role != ProjectMember.ROLE_MEMBER:
                membership.role = ProjectMember.ROLE_MEMBER
                membership.save(update_fields=['role'])
    # Public projects remain transparent; existing memberships still define elevated roles.

@login_required
def user_settings(request):
    profile = request.user.userprofile
    layout_preference = profile.layout_preference
    is_classic = layout_preference == UserProfile.LAYOUT_CLASSIC
    settings_obj = WebsiteSettings.objects.first()
    website_form = None

    if is_classic and request.user.is_superuser:
        if request.method == "POST" and request.POST.get("settings_scope") == "website":
            website_form = WebsiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
            if website_form.is_valid():
                website_form.save()
                messages.success(request, "Website settings updated successfully.")
                return redirect("user_settings")
            messages.error(request, "Error saving website settings.")
        else:
            website_form = WebsiteSettingsForm(instance=settings_obj)

    return render(request, "arva/user_settings.html", {
        "layout_preference": layout_preference,
        "theme_preference": profile.theme_preference,
        "layout_is_classic": is_classic,
        "website_form": website_form,
        "settings": settings_obj,
    })

@login_required
def website_settings(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to manage website settings.")
        return redirect("user_settings")

    if request.user.userprofile.layout_preference == UserProfile.LAYOUT_CLASSIC:
        messages.info(request, "Website settings are available in the unified Settings page (Classic Layout).")
        return redirect("user_settings")

    settings_obj = WebsiteSettings.objects.first()

    if request.method == "POST":
        form = WebsiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Website settings updated successfully.")
            return redirect("website_settings")
        else:
            messages.error(request, "Error saving settings.")
    else:
        form = WebsiteSettingsForm(instance=settings_obj)

    return render(request, "arva/website_settings.html", {
        "form": form,
        "settings": settings_obj
    })

@login_required
@require_POST
def update_user_theme(request):
    theme = request.POST.get("theme")

    if theme not in ["inherit", "light", "dark", "auto"]:
        return JsonResponse({"success": False, "error": "Invalid theme"}, status=400)

    profile = request.user.userprofile
    profile.theme_preference = theme
    profile.save()

    return JsonResponse({"success": True})

@login_required
@require_POST
def update_user_layout(request):
    layout = request.POST.get("layout")

    if layout not in ["sidebar", "classic"]:
        return JsonResponse({"success": False, "error": "Invalid layout"}, status=400)

    profile = request.user.userprofile
    profile.layout_preference = layout
    profile.save(update_fields=["layout_preference"])

    return JsonResponse({"success": True, "layout": layout})

@login_required
def user_list(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission.")
        return redirect('project_list')

    q = request.GET.get('q', '').strip()
    users = User.objects.select_related('userprofile', 'useractivity').annotate(
        last_comment_at=Max('comment__created_at'),
        last_action_at=Max('activitylog__created_at'),
        last_presence_at=Max('useractivity__last_activity'),
    ).order_by('username')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

    users = list(users)
    for u in users:
        candidates = [u.last_comment_at, u.last_action_at, u.last_presence_at]
        candidates = [dt for dt in candidates if dt is not None]
        u.last_activity_at = max(candidates) if candidates else None

    return render(request, 'arva/user_list.html', {
        'users': users,
        'query': q,
    })

@login_required
@require_POST
def create_user_system(request):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    form = CreateUserInlineForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    user = form.save(commit=False)
    user.password = make_password(form.cleaned_data['password'])
    user.save()

    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
    })

@login_required
def user_edit(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission.")
        return redirect('project_list')

    user_obj = get_object_or_404(User, id=user_id)
    profile = user_obj.userprofile

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user_obj)
        avatar_form = AvatarUploadForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and avatar_form.is_valid():
            user_form.save()

            obj = avatar_form.save(commit=False)
            icon = avatar_form.cleaned_data.get("avatar_icon")

            if icon:
                obj.avatar = None
                obj.avatar_icon = icon
            else:
                obj.avatar_icon = None

            obj.save()

            messages.success(request, "User profile updated.")
            return redirect('user_list')
    else:
        user_form = UserEditForm(instance=user_obj)
        avatar_form = AvatarUploadForm(instance=profile)

    memberships = ProjectMember.objects.filter(user=user_obj).select_related('project')
    last_comment = Comment.objects.filter(user=user_obj).aggregate(Max('created_at'))['created_at__max']
    last_task_activity = ActivityLog.objects.filter(user=user_obj).aggregate(Max('created_at'))['created_at__max']
    valid_times = list(filter(None, [last_comment, last_task_activity, user_obj.last_login]))
    last_seen = max(valid_times) if valid_times else None
    # last_seen = max(filter(None, [last_comment, last_task_activity, user_obj.last_login]))

    return render(request, 'arva/user_edit.html', {
        'user_obj': user_obj,
        'user_form': user_form,
        'avatar_form': avatar_form,
        'memberships': memberships,
        'last_seen': last_seen,
    })

@login_required
@require_POST
def user_toggle_active(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    user_obj = get_object_or_404(User, id=user_id)
    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    return JsonResponse({
        'success': True,
        'is_active': user_obj.is_active,
    })

@login_required
@require_POST
def user_reset_password(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    user_obj = get_object_or_404(User, id=user_id)
    form = AdminPasswordResetForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    new_password = form.cleaned_data['password']
    user_obj.password = make_password(new_password)
    user_obj.save()

    return JsonResponse({'success': True})

@login_required
@require_POST
def user_hard_delete(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    user_obj = get_object_or_404(User, id=user_id)

    if user_obj == request.user:
        return JsonResponse({'success': False, 'error': 'Tidak boleh menghapus diri sendiri.'}, status=400)

    if user_obj.is_superuser:
        return JsonResponse({'success': False, 'error': 'Tidak boleh menghapus superuser lain.'}, status=400)

    user_obj.delete()

    return JsonResponse({'success': True})

@login_required
@require_POST
def project_member_update_role(request, pm_id):
    pm = get_object_or_404(ProjectMember, id=pm_id)
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    # Role updates are deprecated; keep memberships as plain project sharing.
    if pm.role != ProjectMember.ROLE_MEMBER:
        pm.role = ProjectMember.ROLE_MEMBER
        pm.save(update_fields=['role'])

    return JsonResponse({'success': True})

@login_required
@require_POST
def project_member_remove(request, pm_id):
    pm = get_object_or_404(ProjectMember, id=pm_id)

    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    pm.delete()

    return JsonResponse({'success': True})

@login_required
def project_list(request):
    accessible_projects = get_accessible_projects_queryset(request.user)
    projects = accessible_projects.annotate(last_task_activity=Max('tasks__updated_at')).prefetch_related(
        'subprojects',
        'memberships__user',
    ).distinct().order_by('-created_at')
    closed_projects = projects.filter(is_project=True, is_closed=True)
    admin_projects = Project.objects.filter(owner=request.user).distinct().order_by('name')
    online_cutoff = now() - timedelta(minutes=1)
    online_users = User.objects.filter(useractivity__last_activity__gte=online_cutoff).order_by('username')

    form = ProjectForm(current_user=request.user)
    project_roles = {project.id: project.get_user_role(request.user) for project in projects}
    return render(request, 'arva/project_list.html', {
        'projects': projects, 
        'project_form': form,
        'online_users': online_users,
        'closed_projects': closed_projects,
        'admin_projects': admin_projects,
        'project_roles': project_roles,
    })


@login_required
def task_search_by_user(request):
    user_query = request.GET.get('user_q', '').strip()
    status = request.GET.get('status', '').strip()
    due = request.GET.get('due', '').strip()
    label_id = request.GET.get('label', '').strip()
    project_id = request.GET.get('project', '').strip()

    accessible_projects = get_accessible_projects_queryset(request.user)
    tasks = Task.objects.filter(
        project__in=accessible_projects,
        is_archived=False,
    ).select_related('project', 'task_list').prefetch_related(
        Prefetch('assignees', queryset=User.objects.select_related('userprofile').order_by('username')),
    ).distinct()

    if user_query:
        tasks = tasks.filter(
            Q(assignees__username__icontains=user_query) |
            Q(assignees__email__icontains=user_query)
        )
    if status:
        tasks = tasks.filter(task_list__name__iexact=status)
    if due:
        tasks = tasks.filter(due_date__lte=due)
    if label_id:
        tasks = tasks.filter(labels__id=label_id)
    if project_id:
        tasks = tasks.filter(project_id=project_id)

    tasks = tasks.order_by('-updated_at')[:200]
    results = []
    for task in tasks:
        assignees = list(task.assignees.all())
        results.append({
            'id': task.id,
            'title': task.title,
            'project_id': task.project_id,
            'project_name': task.project.name,
            'status': task.task_list.name,
            'due_date': task.due_date.isoformat() if task.due_date else '',
            'due_date_display': task.due_date.strftime('%d %b %Y') if task.due_date else 'No due',
            'assignees': [u.username for u in assignees],
            'assignees_display': ', '.join(u.username for u in assignees[:3]) + (f" +{len(assignees)-3}" if len(assignees) > 3 else ''),
            'url': f"/project/{task.project_id}/",
        })

    return JsonResponse({'success': True, 'count': len(results), 'results': results})

@login_required
def my_cards(request):
    accessible_projects = get_accessible_projects_queryset(request.user)
    tasks = Task.objects.filter(
        project__in=accessible_projects,
        is_archived=False
    ).select_related('project', 'task_list').order_by('due_date', 'project__name')
    return render(request, 'arva/my_cards.html', {'tasks': tasks})

@login_required
@require_POST
def project_create(request):
    form = ProjectForm(request.POST, current_user=request.user)
    if form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        sync_project_shares(project, form.cleaned_data)

        TaskList.objects.create(project=project, name='To Do', position=0)
        TaskList.objects.create(project=project, name='In Progress', position=1)
        TaskList.objects.create(project=project, name='Done', position=2)

        ActivityLog.objects.create(
            user=request.user,
            project=project,
            action='project_created',
            description=f"Project '{project.name}' created",
        )
        html = render_to_string('arva/_project_item.html', {
            'project': project,
            'project_role': project.get_user_role(request.user),
        }, request=request)
        return JsonResponse({'success': True, 'html': html, 'project_id': project.id, 'project_name': project.name})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def project_edit(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if project.owner_id != request.user.id:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    form = ProjectForm(request.POST, instance=project, current_user=request.user)
    if form.is_valid():
        form.save()
        sync_project_shares(project, form.cleaned_data)
        return JsonResponse({
            'success': True,
            'name': project.name,
            'description': project.description,
            'is_private': project.is_private,
            'is_project': project.is_project,
            'priority': project.priority,
            'pm_assignee_id': project.pm_assignee_id,
            'start_date': project.start_date.isoformat() if project.start_date else '',
            'start_date_tbd': project.start_date_tbd,
            'etd': project.etd.isoformat() if project.etd else '',
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def subproject_create(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()

    had_subprojects = project.subprojects.exists()
    form = SubProjectForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    subproject = form.save(commit=False)
    subproject.project = project
    subproject.save()

    if not had_subprojects:
        TaskList.objects.filter(project=project, sub_project__isnull=True).update(sub_project=subproject)
        Task.objects.filter(project=project, sub_project__isnull=True).update(sub_project=subproject)

    if not TaskList.objects.filter(project=project, sub_project=subproject).exists():
        TaskList.objects.create(project=project, sub_project=subproject, name='To Do', position=0)
        TaskList.objects.create(project=project, sub_project=subproject, name='In Progress', position=1)
        TaskList.objects.create(project=project, sub_project=subproject, name='Done', position=2)

    ActivityLog.objects.create(
        user=request.user,
        project=project,
        action='project_updated',
        description=f"Sub-project '{subproject.name}' created",
    )

    return JsonResponse({'success': True, 'subproject_id': subproject.id})

@login_required
@require_POST
def subproject_delete(request, subproject_id):
    subproject = get_object_or_404(SubProject, id=subproject_id)
    project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()

    if Task.objects.filter(sub_project=subproject).exists():
        return JsonResponse({'success': False, 'error': 'Sub-project cannot be deleted because it still has tasks.'}, status=400)

    name = subproject.name
    subproject.delete()

    ActivityLog.objects.create(
        user=request.user,
        project=project,
        action='project_updated',
        description=f"Sub-project '{name}' deleted",
    )

    remaining = project.subprojects.order_by('created_at').values_list('id', flat=True)
    redirect_sub = remaining[0] if remaining else None
    return JsonResponse({'success': True, 'redirect_sub': redirect_sub})

@login_required
@require_POST
def subproject_edit(request, subproject_id):
    subproject = get_object_or_404(SubProject, id=subproject_id)
    project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()

    form = SubProjectForm(request.POST, instance=subproject)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    form.save()
    ActivityLog.objects.create(
        user=request.user,
        project=project,
        action='project_updated',
        description=f"Sub-project '{subproject.name}' updated",
    )
    return JsonResponse({'success': True, 'name': subproject.name, 'description': subproject.description})

@login_required
@require_POST
def subproject_move(request, subproject_id):
    subproject = get_object_or_404(SubProject, id=subproject_id)
    source_project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, source_project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(source_project):
        return closed_project_error()

    target_project_id = request.POST.get('project_id')
    if not target_project_id:
        return JsonResponse({'success': False, 'error': 'Missing target project.'}, status=400)

    target_project = get_user_project_or_404(request.user, target_project_id)
    if not require_role(request.user, target_project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(target_project):
        return closed_project_error()

    if str(source_project.id) == str(target_project.id):
        return JsonResponse({'success': True})

    subproject.project = target_project
    subproject.save()

    TaskList.objects.filter(sub_project=subproject).update(project=target_project)
    Task.objects.filter(sub_project=subproject).update(project=target_project)

    ActivityLog.objects.create(
        user=request.user,
        project=source_project,
        action='project_updated',
        description=f"Sub-project '{subproject.name}' moved to '{target_project.name}'",
    )
    ActivityLog.objects.create(
        user=request.user,
        project=target_project,
        action='project_updated',
        description=f"Sub-project '{subproject.name}' moved from '{source_project.name}'",
    )

    return JsonResponse({'success': True, 'target_project_id': target_project.id})

@login_required
@require_POST
def subproject_convert_to_project(request, subproject_id):
    subproject = get_object_or_404(SubProject, id=subproject_id)
    source_project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, source_project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")

    new_project = Project.objects.create(
        owner=source_project.owner,
        name=subproject.name,
        description=subproject.description,
    )

    # Copy memberships from source project to the new project.
    memberships = ProjectMember.objects.filter(project=source_project).select_related('user')
    for membership in memberships:
        ProjectMember.objects.get_or_create(
            project=new_project,
            user=membership.user,
            defaults={'role': membership.role},
        )
    ProjectMember.objects.get_or_create(
        project=new_project,
        user=source_project.owner,
        defaults={'role': ProjectMember.ROLE_MEMBER},
    )

    TaskList.objects.filter(sub_project=subproject).update(
        project=new_project,
        sub_project=None,
    )
    Task.objects.filter(sub_project=subproject).update(
        project=new_project,
        sub_project=None,
    )

    ActivityLog.objects.create(
        user=request.user,
        project=new_project,
        action='project_created',
        description=f"Project '{new_project.name}' created from sub-project",
    )

    subproject.delete()

    return JsonResponse({'success': True, 'project_id': new_project.id})

@login_required
def project_subprojects(request, pk):
    project = get_user_project_or_404(request.user, pk)
    subprojects = list(project.subprojects.order_by('created_at').values('id', 'name'))
    return JsonResponse({'success': True, 'subprojects': subprojects})

@login_required
def project_detail(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)

    subprojects = project.subprojects.all().order_by('created_at')
    selected_subproject = None
    scope = request.GET.get('scope', '')

    if subprojects.exists():
        sub_id = request.GET.get('sub')
        if sub_id == 'all':
            selected_subproject = None
        elif sub_id:
            selected_subproject = get_project_subproject_or_404(project, sub_id)
        else:
            selected_subproject = subprojects.first()
    else:
        if not project.lists.filter(sub_project__isnull=True).exists() and project.owner == request.user:
            TaskList.objects.create(project=project, name='To Do', position=0)
            TaskList.objects.create(project=project, name='In Progress', position=1)
            TaskList.objects.create(project=project, name='Done', position=2)

    q = request.GET.get('q', '')
    assignee_id = request.GET.get('assignee', '')
    assignee_query = request.GET.get('assignee_q', '').strip()
    status_id = request.GET.get('status', '').strip()
    priority_code = request.GET.get('priority', '').strip()
    label_id = request.GET.get('label', '')
    due = request.GET.get('due', '')
    page_number = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', '25').strip()
    if per_page not in {'10', '25', '50', '100'}:
        per_page = '25'

    base_tasks = Task.objects.filter(project=project, is_archived=False).select_related(
        'task_list', 'project', 'sub_project', 'created_by', 'created_by__userprofile'
    ).prefetch_related(
        'labels',
        Prefetch('assignees', queryset=User.objects.select_related('userprofile')),
        'checklist_items',
    )

    scope_all = (scope == 'all' or request.GET.get('sub') == 'all') and subprojects.exists()
    if not scope_all:
        if selected_subproject:
            base_tasks = base_tasks.filter(sub_project=selected_subproject)
        else:
            base_tasks = base_tasks.filter(sub_project__isnull=True)

    if q:
        base_tasks = base_tasks.filter(title__icontains=q)
    if assignee_id:
        base_tasks = base_tasks.filter(assignees__id=assignee_id)
    if assignee_query:
        base_tasks = base_tasks.filter(
            Q(assignees__username__icontains=assignee_query) |
            Q(assignees__email__icontains=assignee_query)
        )
    if project.is_project:
        if status_id and status_id in STRUCTURED_TASK_STATUSES:
            base_tasks = base_tasks.filter(status=status_id)
        if priority_code and priority_code in STRUCTURED_TASK_PRIORITIES:
            base_tasks = base_tasks.filter(priority=priority_code)
    else:
        if status_id:
            base_tasks = base_tasks.filter(task_list_id=status_id)
        if label_id:
            base_tasks = base_tasks.filter(labels__id=label_id)
    if due:
        base_tasks = base_tasks.filter(due_date__lte=due)
    base_tasks = base_tasks.distinct()

    list_tasks_qs = base_tasks.order_by('-updated_at', '-id')
    list_paginator = Paginator(list_tasks_qs, int(per_page))
    list_page_obj = list_paginator.get_page(page_number)

    if scope_all:
        grouped_task_lists = []
        subproject_items = list(subprojects)
        if project.lists.filter(sub_project__isnull=True, is_archived=False).exists():
            subproject_items = [None] + subproject_items

        for sp in subproject_items:
            list_qs = project.lists.filter(is_archived=False, sub_project=sp)
            lists = list(list_qs.order_by('position').prefetch_related(
                Prefetch('tasks', queryset=base_tasks.order_by('order'), to_attr='filtered_tasks')
            ))
            grouped_task_lists.append({
                'subproject': sp,
                'task_lists': lists,
            })
        task_lists = []
    else:
        list_qs = project.lists.filter(is_archived=False)
        list_qs = list_qs.filter(sub_project=selected_subproject if selected_subproject else None)
        task_lists = list(list_qs.order_by('position').prefetch_related(
            Prefetch('tasks', queryset=base_tasks.order_by('order'), to_attr='filtered_tasks')
        ))
        grouped_task_lists = []

    status_lists_qs = project.lists.filter(is_archived=False)
    if not scope_all:
        status_lists_qs = status_lists_qs.filter(sub_project=selected_subproject if selected_subproject else None)
    available_status_lists = status_lists_qs.order_by('position')
    structured_status_options = [
        (Task.STATUS_NONE, '-'),
        (Task.STATUS_IN_PROGRESS, 'In Progress'),
        (Task.STATUS_DONE, 'Done'),
        (Task.STATUS_INFEASIBLE, 'Infeasible'),
    ]
    structured_priority_options = [
        (Task.PRIORITY_P0, 'P0 - Urgent'),
        (Task.PRIORITY_P1, 'P1 - High'),
        (Task.PRIORITY_P2, 'P2 - Medium'),
        (Task.PRIORITY_P3, 'P3 - Low'),
        (Task.PRIORITY_P4, 'P4 - Very Low'),
    ]

    task_form = TaskForm(project=project)
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    checklist_form = ChecklistItemForm()

    shared_members = project.memberships.select_related('user', 'user__userprofile').order_by('user__username')
    shared_user_ids = set(shared_members.values_list('user_id', flat=True))
    querystring = request.GET.copy()
    querystring.pop('page', None)

    context = {
        'project': project,
        'task_lists': task_lists,
        'task_form': task_form,
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'checklist_form': checklist_form,
        'users': User.objects.select_related('userprofile').order_by('username'),
        'projects': get_accessible_projects_queryset(request.user).order_by('name'),
        'user_role': role,
        'subprojects': subprojects,
        'selected_subproject': selected_subproject,
        'task_scope': 'all' if scope_all else 'sub',
        'grouped_task_lists': grouped_task_lists,
        'list_page_obj': list_page_obj,
        'per_page': per_page,
        'per_page_options': ['10', '25', '50', '100'],
        'available_status_lists': available_status_lists,
        'structured_status_options': structured_status_options,
        'structured_priority_options': structured_priority_options,
        'querystring': querystring.urlencode(),
        'filter_values': {
            'q': q,
            'assignee': assignee_id,
            'assignee_q': assignee_query,
            'status': status_id,
            'priority': priority_code,
            'label': label_id,
            'due': due,
            'page': str(list_page_obj.number),
            'per_page': per_page,
        },
        'shared_members': shared_members,
        'shared_user_ids': shared_user_ids,
        'shared_role_default': ProjectMember.ROLE_MEMBER,
        'all_users': User.objects.exclude(id=request.user.id).order_by('username'),
        'project_is_locked': is_project_locked(project),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('arva/_task_board.html', context, request=request)
        return JsonResponse({'html': html})

    return render(request, 'arva/project_detail.html', context)

@login_required
def project_archive(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return HttpResponseForbidden("Forbidden")

    archived_lists = project.lists.filter(is_archived=True).order_by('position')
    archived_tasks = project.tasks.filter(is_archived=True).select_related('task_list').prefetch_related(
        Prefetch('assignees', queryset=User.objects.select_related('userprofile').order_by('username'))
    ).order_by('task_list__position', 'order')
    return render(request, 'arva/project_archive.html', {
        'project': project,
        'archived_lists': archived_lists,
        'archived_tasks': archived_tasks,
        'user_role': role,
    })

@login_required
def project_activity(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return HttpResponseForbidden("Forbidden")

    activities = project.activities.select_related('user', 'task').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    action = request.GET.get('action', '').strip()
    user_id = request.GET.get('user', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if q:
        activities = activities.filter(
            Q(description__icontains=q) |
            Q(task__title__icontains=q) |
            Q(action__icontains=q) |
            Q(user__username__icontains=q)
        )

    if action:
        activities = activities.filter(action=action)

    if user_id:
        activities = activities.filter(user_id=user_id)

    if date_from:
        try:
            date_from_value = datetime.strptime(date_from, "%Y-%m-%d").date()
            activities = activities.filter(created_at__date__gte=date_from_value)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_value = datetime.strptime(date_to, "%Y-%m-%d").date()
            activities = activities.filter(created_at__date__lte=date_to_value)
        except ValueError:
            pass

    users = User.objects.filter(
        Q(owned_projects=project) | Q(project_memberships__project=project)
    ).distinct().order_by('username')

    paginator = Paginator(activities, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    querystring = request.GET.copy()
    querystring.pop('page', None)

    return render(request, 'arva/activity_log.html', {
        'project': project,
        'activities': page_obj,
        'user_role': role,
        'actions': ActivityLog.ACTION_CHOICES,
        'users': users,
        'filters': {
            'q': q,
            'action': action,
            'user': user_id,
            'date_from': date_from,
            'date_to': date_to,
        },
        'querystring': querystring.urlencode(),
    })

@login_required
def subproject_list(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER, ProjectMember.ROLE_VIEWER]:
        return HttpResponseForbidden("Forbidden")

    subprojects = project.subprojects.all().order_by('created_at')
    admin_projects = Project.objects.filter(owner=request.user).distinct().order_by('name')
    return render(request, 'arva/subproject_list.html', {
        'project': project,
        'subprojects': subprojects,
        'user_role': role,
        'admin_projects': admin_projects,
    })

@login_required
@require_POST
def project_update(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({
            "success": False,
            "error": "The project cannot be updated because you are not the owner of this project."
        }, status=400)
    form = ProjectForm(request.POST, instance=project, current_user=request.user)
    if form.is_valid():
        form.save()
        sync_project_shares(project, form.cleaned_data)
        ActivityLog.objects.create(
            user=request.user,
            project=project,
            action='project_updated',
            description=f"Project '{project.name}' updated",
        )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def project_close(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    if not project.is_project:
        return JsonResponse({'success': False, 'error': 'Only structured projects can be closed.'}, status=400)
    if project.is_closed:
        return JsonResponse({'success': True, 'is_closed': True})

    project.is_closed = True
    project.save(update_fields=['is_closed'])
    ActivityLog.objects.create(
        user=request.user,
        project=project,
        action='project_updated',
        description=f"Project '{project.name}' closed",
    )
    return JsonResponse({'success': True, 'is_closed': True})


@login_required
@require_POST
def project_reopen(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    if not project.is_project:
        return JsonResponse({'success': False, 'error': 'Only structured projects can be reopened.'}, status=400)
    if not project.is_closed:
        return JsonResponse({'success': True, 'is_closed': False})

    project.is_closed = False
    project.save(update_fields=['is_closed'])
    ActivityLog.objects.create(
        user=request.user,
        project=project,
        action='project_updated',
        description=f"Project '{project.name}' reopened",
    )
    return JsonResponse({'success': True, 'is_closed': False})

@login_required
@require_POST
def project_convert_to_subproject(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")

    if project.subprojects.exists():
        return JsonResponse({'success': False, 'error': 'Project has sub-projects and cannot be converted.'}, status=400)

    target_project_id = request.POST.get('target_project_id')
    if not target_project_id:
        return JsonResponse({'success': False, 'error': 'Missing target project.'}, status=400)

    target_project = get_user_project_or_404(request.user, target_project_id)
    if not require_role(request.user, target_project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")

    if str(project.id) == str(target_project.id):
        return JsonResponse({'success': False, 'error': 'Target project must be different.'}, status=400)

    subproject = SubProject.objects.create(
        project=target_project,
        name=project.name,
        description=project.description,
    )

    TaskList.objects.filter(project=project).update(
        project=target_project,
        sub_project=subproject,
    )
    Task.objects.filter(project=project).update(
        project=target_project,
        sub_project=subproject,
    )

    ActivityLog.objects.create(
        user=request.user,
        project=target_project,
        action='project_updated',
        description=f"Project '{project.name}' converted to sub-project",
    )

    project.delete()

    return JsonResponse({'success': True, 'subproject_id': subproject.id, 'target_project_id': target_project.id})
@login_required
@require_POST
def project_delete(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({
            "success": False,
            "error": "The project cannot be deleted because you are not the owner of this project."
        }, status=400)
    
    if project.tasks.exists():
        return JsonResponse({
            "success": False,
            "error": "Project cannot be deleted because it still has tasks."
        }, status=400)
    
    name = project.name
    project.delete()
    ActivityLog.objects.create(
        user=request.user,
        project=None,
        action='project_deleted',
        description=f"Project '{name}' deleted",
    )
    return JsonResponse({'success': True})

@login_required
def project_members(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return HttpResponseForbidden("Forbidden")

    members = project.memberships.select_related('user')
    form = ProjectMemberForm()
    form.fields['user'].queryset = User.objects.exclude(id=request.user.id)
    return render(request, 'arva/project_members.html', {
        'project': project,
        'members': members,
        'form': form,
        'user_role': role,
    })

@login_required
@require_POST
def project_member_add(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")

    form = ProjectMemberForm(request.POST)
    form.fields['user'].queryset = User.objects.exclude(id=request.user.id)

    if form.is_valid():
        member = form.save(commit=False)
        member.project = project
        member.role = ProjectMember.ROLE_MEMBER

        if member.user == request.user:
            return HttpResponseForbidden("Tidak boleh menambahkan diri sendiri sebagai member.")

        if ProjectMember.objects.filter(project=project, user=member.user).exists():
            return HttpResponseForbidden("User ini sudah menjadi member project.")

        member.save()
        return redirect('project_members', pk=project.pk)

    members = project.memberships.select_related('user')
    return render(request, 'arva/project_members.html', {
        'project': project,
        'members': members,
        'form': form,
        'user_role': ProjectMember.ROLE_ADMIN,
    })

@login_required
@require_POST
def project_member_update(request, member_id):
    member = get_object_or_404(ProjectMember, id=member_id)
    project = member.project

    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({"success": False, "error": "Forbidden"}, status=403)

    new_role = request.POST.get("role")

    if member.user == project.owner:
        return JsonResponse({"success": False, "error": "Owner role cannot be changed."}, status=400)

    # if member.role == "admin" and new_role != "admin":
    #     remaining_admin = project.memberships.filter(role="admin").exclude(id=member.id).count()
    #     if remaining_admin == 0:
    #         return JsonResponse({"success": False, "error": "Project must have at least 1 admin."}, status=400)

    if member.role != ProjectMember.ROLE_MEMBER:
        member.role = ProjectMember.ROLE_MEMBER
        member.save(update_fields=["role"])

    return JsonResponse({"success": True, "role": ProjectMember.ROLE_MEMBER})

@login_required
@require_POST
def project_member_delete(request, member_id):
    member = get_object_or_404(ProjectMember, id=member_id)
    project = member.project
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    member.delete()
    return redirect('project_members', pk=project.pk)

@login_required
@require_POST
def tasklist_create(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()

    subproject = None
    subproject_id = request.POST.get('sub_project_id')
    if project.subprojects.exists():
        if not subproject_id:
            return JsonResponse({'success': False, 'error': 'Sub-project required.'}, status=400)
        subproject = get_project_subproject_or_404(project, subproject_id)

    form = TaskListForm(request.POST)
    if form.is_valid():
        tl = form.save(commit=False)
        tl.project = project
        tl.sub_project = subproject
        last_pos = project.lists.filter(sub_project=subproject).aggregate(dj_models.Max('position'))['position__max'] or 0
        tl.position = last_pos + 1
        tl.save()
        ActivityLog.objects.create(
            user=request.user, project=project, action='list_created',
            description=f"List '{tl.name}' created"
        )
        tl.filtered_tasks = []
        html = render_to_string('arva/_task_list.html', {
            'task_list': tl,
            'project': project,
            'user_role': get_role(request.user, project),
            'selected_subproject': subproject,
        }, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def tasklist_reorder(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()
    subproject = None
    subproject_id = request.POST.get('sub_project_id')
    if project.subprojects.exists():
        if not subproject_id:
            return JsonResponse({'success': False, 'error': 'Sub-project required.'}, status=400)
        subproject = get_project_subproject_or_404(project, subproject_id)
    ordered_ids = request.POST.getlist('ordered_ids[]')
    for index, lid in enumerate(ordered_ids):
        TaskList.objects.filter(id=lid, project=project, sub_project=subproject).update(position=index)
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_moved',
        description='Lists reordered'
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def tasklist_delete(request, list_id):
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()
    name = tl.name
    tl.delete()
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_deleted',
        description=f"List '{name}' deleted"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def tasklist_archive(request, list_id):
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()
    tl.is_archived = True
    tl.save()
    tl.tasks.update(is_archived=True)
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_archived',
        description=f"List '{tl.name}' archived"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def tasklist_unarchive(request, list_id):
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    if is_project_locked(project):
        return closed_project_error()
    tl.is_archived = False
    tl.save()
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_unarchived',
        description=f"List '{tl.name}' unarchived"
    )
    return JsonResponse({'success': True})

@login_required
def task_view(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related('created_by', 'created_by__userprofile'),
        id=task_id
    )
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)
    users = User.objects.all()
    labels = Label.objects.all()
    projects = Project.objects.filter(
        Q(owner=request.user) | Q(memberships__user=request.user)
    ).distinct().order_by('name')
    project_lists = TaskList.objects.filter(
        project=project,
        sub_project=task.sub_project if task.sub_project else None,
        is_archived=False
    ).order_by('position')
    subprojects = project.subprojects.order_by('created_at')
    colors = ["primary", "success", "danger", "warning", "info", "dark", ""]
    comments = task.comments.filter(parent__isnull=True)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    total = task.checklist_total
    done = task.checklist_done
    percent = int((done / total) * 100) if total > 0 else 0

    view_only = bool(is_project_locked(project) or not (role == "admin" or request.user in task.assignees.all()))
    html = render_to_string('arva/_task_view.html', {
        'task': task,
        'project': project,
        'project_is_project': project.is_project,
        'user_role': role,
        'users': users,
        'labels': labels,
        'projects': projects,
        'project_lists': project_lists,
        'subprojects': subprojects,
        'selected_subproject': task.sub_project,
        'colors': colors,
        'checklist_total': total,
        'checklist_done': done,
        'checklist_percent': percent,
        'root_comments': comments,
        "view_only": view_only,
        'project_is_closed': is_project_locked(project),
    }, request=request)

    return JsonResponse({'success': True, 'html': html})

@login_required
def project_lists(request, pk):
    project = get_user_project_or_404(request.user, pk)
    subproject = None
    subproject_id = request.GET.get('sub_project_id')
    if project.subprojects.exists():
        if subproject_id:
            subproject = get_project_subproject_or_404(project, subproject_id)
        else:
            subproject = project.subprojects.order_by('created_at').first()
    lists = project.lists.filter(
        is_archived=False,
        sub_project=subproject if subproject else None
    ).order_by('position').values('id', 'name')
    return JsonResponse({'success': True, 'lists': list(lists)})

@login_required
@require_POST
def task_inline_update(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    field = request.POST.get('field')
    value = request.POST.get('value', '')

    changed = False
    desc = ''

    if field == 'title':
        old = task.title
        task.title = value
        changed = True
        desc = f"Title updated from '{old}' to '{value}'"
    elif field == 'description':
        task.description = value
        changed = True
        desc = "Description updated"
    elif field == 'status':
        if project.is_project and value not in STRUCTURED_TASK_STATUSES:
            return JsonResponse({'success': False, 'error': 'Invalid status.'}, status=400)
        task.status = value or Task.STATUS_NONE
        changed = True
        desc = "Status updated"
    elif field == 'start_date':
        parsed_start = datetime.strptime(value, "%Y-%m-%d").date() if value else None
        if project.is_project and not parsed_start and not task.start_date_tbd:
            return JsonResponse({'success': False, 'error': 'Start Date is required or mark it as TBD.'}, status=400)
        task.start_date = parsed_start
        if parsed_start:
            task.start_date_tbd = False
        if project.is_project and parsed_start and task.due_date and task.due_date < parsed_start:
            return JsonResponse({'success': False, 'error': 'End Date cannot be earlier than Start Date.'}, status=400)
        changed = True
        desc = "Start date updated"
    elif field == 'start_date_tbd':
        is_tbd = str(value).lower() in {'1', 'true', 'on', 'yes'}
        if project.is_project and not is_tbd and not task.start_date:
            return JsonResponse({'success': False, 'error': 'Start Date is required or mark it as TBD.'}, status=400)
        task.start_date_tbd = is_tbd
        if is_tbd:
            task.start_date = None
        changed = True
        desc = "Start date TBD updated"
    elif field == 'due_date':
        parsed_due = datetime.strptime(value, "%Y-%m-%d").date() if value else None
        if project.is_project and not parsed_due:
            return JsonResponse({'success': False, 'error': 'End Date is required.'}, status=400)
        if project.is_project and parsed_due and task.start_date and parsed_due < task.start_date:
            return JsonResponse({'success': False, 'error': 'End Date cannot be earlier than Start Date.'}, status=400)
        if project.is_project and parsed_due and project.etd and parsed_due > project.etd:
            return JsonResponse({'success': False, 'error': 'End Date must not exceed project ETD.'}, status=400)
        task.due_date = parsed_due
        changed = True
        desc = "Due date updated"
    elif field == 'priority':
        if project.is_project and value not in STRUCTURED_TASK_PRIORITIES:
            return JsonResponse({'success': False, 'error': 'Invalid priority for project task.'}, status=400)
        task.priority = value or Task.PRIORITY_P2
        changed = True
        desc = "Priority updated"
    elif field == 'assignees':
        old_ids = set(task.assignees.values_list('id', flat=True))

        ids = [i for i in value.split(',') if i]
        if project.is_project and len(ids) > 1:
            return JsonResponse({'success': False, 'error': 'Only one assignee is allowed for project tasks.'}, status=400)
        if project.is_project and len(ids) == 0:
            return JsonResponse({'success': False, 'error': 'Assignee is required for project tasks.'}, status=400)
        new_ids = set(ids)
        task.assignees.set(ids)
        changed = True
        desc = "Assignees updated"
        
        project = task.project
        added_ids = new_ids - old_ids
        users_by_id = User.objects.filter(id__in=ids).in_bulk()
        for uid in ids:
            user_obj = users_by_id.get(int(uid))
            if not user_obj:
                continue

            if user_obj == project.owner:
                continue

            ProjectMember.objects.get_or_create(
                project=project,
                user=user_obj,
                defaults={'role': ProjectMember.ROLE_MEMBER}
            )

            print("Start Send Email")
            if uid in added_ids and user_obj != request.user:
                try:
                    print("Sending Email")
                    board_url = f"https://{request.get_host()}/project/{task.project.id}"
                    context = {
                        "task": task,
                        "project": task.project,
                        "assignee": user_obj,
                        "assigned_by": request.user,
                        "board_url": board_url,
                    }

                    html_message = render_to_string("email/assign_task.html", context)
                    plain_message = strip_tags(html_message)

                    EmailThread(
                        subject=f"[Arva] You have been assigned to: {task.title}",
                        message=plain_message,
                        html_message=html_message,
                        from_email=None,
                        recipient_list=[user_obj.email],
                    ).start()
                    print("Already Sending Email")
                except Exception as e:
                    print("Email sending error:", e)

    elif field == 'labels':
        if project.is_project:
            return JsonResponse({'success': False, 'error': 'Labels are disabled for project tasks.'}, status=400)
        ids = [i for i in value.split(',') if i]
        task.labels.set(ids)
        changed = True
        desc = "Labels updated"
    if field == 'cover_color':
        task.cover_color = value or None
        changed = True
        desc = "updated cover color"

    if not changed:
        return JsonResponse({'success': False, 'error': 'Unknown field'}, status=400)

    task.save()
    ActivityLog.objects.create(project=project, task=task, user=request.user, action='task_updated', description=desc)

    html = render_to_string('arva/_task_card.html', {'task': task, 'project': project, 'user_role': role}, request=request)
    list_row_html = render_to_string('arva/_task_list_row.html', {'task': task, 'project': project, 'user_role': role}, request=request)
    return JsonResponse({'success': True, 'html': html, 'list_row_html': list_row_html})

@login_required
@require_POST
def task_create(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if is_project_locked(project):
        return closed_project_error()
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER]):
        return HttpResponseForbidden("Forbidden")
    task_list_id = request.POST.get('task_list_id')
    task_list = get_object_or_404(TaskList, id=task_list_id, project=project)
    subproject = None
    subproject_id = request.POST.get('sub_project_id')
    if project.subprojects.exists():
        if subproject_id:
            subproject = get_project_subproject_or_404(project, subproject_id)
        else:
            subproject = task_list.sub_project
        if task_list.sub_project != subproject:
            return JsonResponse({'success': False, 'error': 'Invalid list for sub-project.'}, status=400)

    data = request.POST.copy()
    if project.is_project:
        data.setlist('labels', [])
        data.pop('cover_color', None)
    if 'priority' not in data or not data['priority']:
        data['priority'] = Task.PRIORITY_P2

    form = TaskForm(data, project=project)
    if form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.sub_project = subproject
        task.task_list = task_list
        last_order = task_list.tasks.aggregate(dj_models.Max('order'))['order__max'] or 0
        task.order = last_order + 1
        task.created_by = request.user
        task.save()
        form.save_m2m()

        if not project.is_project:
            initial_comment = request.POST.get('initial_comment', '').strip()
            if initial_comment:
                Comment.objects.create(task=task, user=request.user, content=initial_comment)
            for uploaded in request.FILES.getlist('comment_files'):
                Attachment.objects.create(task=task, uploaded_by=request.user, file=uploaded)
        ActivityLog.objects.create(
            user=request.user, project=project, task=task,
            action='task_created', description=f"Task '{task.title}' created"
        )
        html = render_to_string('arva/_task_card.html', {
            'task': task,
            'project': project,
            'user_role': get_role(request.user, project),
        }, request=request)
        list_row_html = render_to_string('arva/_task_list_row.html', {
            'task': task,
            'project': project,
            'user_role': get_role(request.user, project),
        }, request=request)
        return JsonResponse({
            'success': True,
            'html': html,
            'list_row_html': list_row_html,
            'task_id': task.id,
            'task_list_id': task.task_list_id,
        })
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def task_update(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return HttpResponseForbidden("Forbidden")
    data = request.POST.copy()
    if project.is_project:
        data.setlist('labels', [])
        data.pop('cover_color', None)
    if 'priority' not in data or not data['priority']:
        data['priority'] = Task.PRIORITY_P2
    form = TaskForm(data, instance=task, project=project)
    if form.is_valid():
        form.save()
        ActivityLog.objects.create(
            user=request.user, project=task.project, task=task,
            action='task_updated', description=f"Task '{task.title}' updated"
        )
        html = render_to_string('arva/_task_card.html', {
            'task': task,
            'project': project,
            'user_role': get_role(request.user, project),
        }, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    title = task.title
    task.delete()
    ActivityLog.objects.create(
        user=request.user, project=project, action='task_deleted',
        description=f"Task '{title}' deleted"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
@transaction.atomic
def task_move(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER] or        (role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all()):
        return HttpResponseForbidden("Forbidden")

    new_list_id = request.POST.get('task_list_id')
    ordered_ids = request.POST.getlist('ordered_ids[]')

    new_list = get_object_or_404(TaskList, id=new_list_id, project=task.project)
    if new_list.sub_project != task.sub_project:
        task.sub_project = new_list.sub_project
    task.task_list = new_list
    task.save()

    if ordered_ids:
        order_cases = [
            When(id=int(tid), then=pos) for pos, tid in enumerate(ordered_ids)
        ]
        Task.objects.filter(id__in=ordered_ids, project=task.project).update(
            order=Case(*order_cases, output_field=IntegerField())
        )

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='task_moved', description=f"Task '{task.title}' moved to list '{new_list.name}'"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
@transaction.atomic
def task_transfer(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    source_project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(source_project):
        return closed_project_error()
    source_role = get_role(request.user, source_project)
    if source_role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER] or (
        source_role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all()
    ):
        return HttpResponseForbidden("Forbidden")

    target_project_id = request.POST.get('project_id')
    target_list_id = request.POST.get('task_list_id')
    if not target_project_id:
        return JsonResponse({'success': False, 'error': 'Missing project'}, status=400)

    target_project = get_user_project_or_404(request.user, target_project_id)
    if is_project_locked(target_project):
        return closed_project_error()
    target_role = get_role(request.user, target_project)
    if target_role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER]:
        return HttpResponseForbidden("Forbidden")

    target_subproject = None
    target_subproject_id = request.POST.get('sub_project_id')
    if target_project.subprojects.exists():
        if not target_subproject_id:
            return JsonResponse({'success': False, 'error': 'Sub-project required.'}, status=400)
        target_subproject = get_project_subproject_or_404(target_project, target_subproject_id)

    if target_list_id:
        target_list = get_object_or_404(TaskList, id=target_list_id, project=target_project)
    else:
        target_list = target_project.lists.filter(
            is_archived=False,
            sub_project=target_subproject if target_subproject else None
        ).order_by('position').first()
        if not target_list:
            return JsonResponse({'success': False, 'error': 'No list available in target project'}, status=400)

    if target_list.sub_project != target_subproject:
        return JsonResponse({'success': False, 'error': 'Invalid list for sub-project.'}, status=400)

    max_order = Task.objects.filter(task_list=target_list).aggregate(Max('order'))['order__max'] or 0
    task.project = target_project
    task.sub_project = target_subproject
    task.task_list = target_list
    task.order = max_order + 1
    task.save()

    ActivityLog.objects.create(
        user=request.user, project=source_project, task=task,
        action='task_moved', description=f"Task '{task.title}' moved to project '{target_project.name}'"
    )
    ActivityLog.objects.create(
        user=request.user, project=target_project, task=task,
        action='task_moved', description=f"Task '{task.title}' moved into project '{target_project.name}'"
    )

    return JsonResponse({'success': True})

@login_required
@require_POST
def task_archive(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    task.is_archived = True
    task.save()
    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='task_archived', description=f"Task '{task.title}' archived"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def task_unarchive(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    task.is_archived = False
    task.save()
    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='task_unarchived', description=f"Task '{task.title}' unarchived"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def comment_add(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return HttpResponseForbidden("Forbidden")

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.user = request.user
        comment.save()
        ActivityLog.objects.create(
            user=request.user, project=task.project, task=task,
            action='comment_added', description=f"Comment added on task '{task.title}'"
        )
        html = render_to_string('arva/_comment_item.html', {'comment': comment}, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def comment_reply(request, comment_id):
    parent = get_object_or_404(Comment, id=comment_id)
    task = parent.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False}, status=403)

    content = request.POST.get("content", "").strip()
    if not content:
        return JsonResponse({'success': False}, status=400)

    new_comment = Comment.objects.create(
        task=task,
        user=request.user,
        parent=parent,
        content=content
    )

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='comment_added', description=f"replied to a comment"
    )

    html = render_to_string("arva/_comment_list.html", {
        "comments": [new_comment],
        "user_role": role,
        "user": request.user,
        "project_is_closed": is_project_locked(project),
        "show_comment_avatar": False,
    }, request=request)

    return JsonResponse({"success": True, "html": html})

@login_required
@require_POST
def comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    task = comment.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    if not (comment.user_id == request.user.id or project.owner_id == request.user.id):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='comment_added', description=f"deleted a comment"
    )

    comment.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def attachment_add(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return HttpResponseForbidden("Forbidden")

    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.task = task
        attachment.uploaded_by = request.user
        attachment.save()
        ActivityLog.objects.create(
            user=request.user, project=task.project, task=task,
            action='attachment_added', description=f"Attachment added on task '{task.title}'"
        )
        html = render_to_string('arva/_attachment_item.html', {'attachment': attachment}, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def checklist_add(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if project.is_project:
        return JsonResponse({'success': False, 'error': 'Checklist is disabled for project tasks.'}, status=400)
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return HttpResponseForbidden("Forbidden")

    form = ChecklistItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.task = task
        item.save()
        ActivityLog.objects.create(
            user=request.user, project=item.task.project, task=item.task,
            action='checklist_added', description=f"Checklist item added on task '{item.task.title}'"
        )
        html = render_to_string('arva/_checklist_item.html', {'item': item}, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def checklist_edit(request, item_id):
    item = get_object_or_404(ChecklistItem, id=item_id)
    task = item.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if project.is_project:
        return JsonResponse({'success': False, 'error': 'Checklist is disabled for project tasks.'}, status=400)
    role = get_role(request.user, project)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': "Forbidden"}, status=403)

    new_text = request.POST.get("content", "").strip()
    if not new_text:
        return JsonResponse({'success': False, 'error': "Content empty"}, status=400)

    old_text = item.content
    item.content = new_text
    item.save()

    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_added', description=f"edited checklist item: '{old_text}' → '{new_text}'"
    )

    return JsonResponse({"success": True})

@login_required
@require_POST
def checklist_toggle(request, item_id):
    item = get_object_or_404(ChecklistItem, id=item_id)
    project = get_user_project_or_404(request.user, item.task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if project.is_project:
        return JsonResponse({'success': False, 'error': 'Checklist is disabled for project tasks.'}, status=400)
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in item.task.assignees.all():
        return HttpResponseForbidden("Forbidden")

    item.is_done = not item.is_done
    item.save()
    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_toggled', description=f"Checklist toggled on task '{item.task.title}'"
    )
    return JsonResponse({'success': True, 'is_done': item.is_done})

@login_required
@require_POST
def checklist_delete(request, item_id):
    item = get_object_or_404(ChecklistItem, id=item_id)
    task = item.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    if project.is_project:
        return JsonResponse({'success': False, 'error': 'Checklist is disabled for project tasks.'}, status=400)
    role = get_role(request.user, project)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': "Forbidden"}, status=403)

    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_toggled', description=f"deleted checklist item: '{item.content}'"
    )
    item.delete()

    return JsonResponse({"success": True})

# AI Priority Analysis Views
@login_required
def ai_analyze_task(request, task_id):
    """Analyze a single task using AI and return priority recommendations."""
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)
    
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    try:
        ai_service = get_ai_service()
        analysis = ai_service.analyze_task(task)
        
        if 'error' in analysis:
            return JsonResponse({'success': False, 'error': analysis['error']}, status=500)
        
        # Save analysis results to task
        task.ai_priority_score = analysis.get('priority_score')
        task.ai_priority_reason = analysis.get('reasoning', '')
        task.ai_complexity = analysis.get('complexity', '')
        task.ai_estimated_hours = analysis.get('estimated_hours')
        task.ai_analyzed_at = now()
        task.save(update_fields=[
            'ai_priority_score', 'ai_priority_reason', 'ai_complexity',
            'ai_estimated_hours', 'ai_analyzed_at'
        ])
        
        return JsonResponse({
            'success': True,
            'analysis': analysis
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def ai_analyze_project(request, pk):
    """Analyze all tasks in a project using AI."""
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    
    if role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER]:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    try:
        ai_service = get_ai_service()
        
        # Get all non-archived, non-done tasks
        tasks = Task.objects.filter(
            project=project,
            is_archived=False
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'task_list'
        ).prefetch_related(
            'assignees', 'labels', 'checklist_items'
        )
        
        results = []
        for task in tasks:
            analysis = ai_service.analyze_task(task)
            if 'error' not in analysis:
                # Save to task
                task.ai_priority_score = analysis.get('priority_score')
                task.ai_priority_reason = analysis.get('reasoning', '')
                task.ai_complexity = analysis.get('complexity', '')
                task.ai_estimated_hours = analysis.get('estimated_hours')
                task.ai_analyzed_at = now()
                task.save(update_fields=[
                    'ai_priority_score', 'ai_priority_reason', 'ai_complexity',
                    'ai_estimated_hours', 'ai_analyzed_at'
                ])
                results.append(analysis)
        
        # Sort by priority score
        results.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        return JsonResponse({
            'success': True,
            'analyzed_count': len(results),
            'priorities': results
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def ai_priority_queue(request):
    """Display AI-prioritized task queue for the user."""
    try:
        # Get tasks for user
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            Q(assignees=request.user) | Q(project__owner=request.user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        ).prefetch_related(
            'assignees', 'labels', 'checklist_items'
        )[:50]
        
        # Only show cached analysis - NO API calls on page load
        priorities = []
        for task in tasks:
            # Only include tasks that have been analyzed before
            if task.ai_priority_score is not None:
                priorities.append({
                    'task_id': task.id,
                    'task_title': task.title,
                    'project_id': task.project.id,
                    'project_name': task.project.name,
                    'sub_project_name': task.sub_project.name if task.sub_project else None,
                    'priority_score': task.ai_priority_score,
                    'priority_level': _get_priority_level(task.ai_priority_score),
                    'complexity': task.ai_complexity,
                    'estimated_hours': task.ai_estimated_hours,
                    'reasoning': task.ai_priority_reason,
                    'due_date': task.due_date.strftime('%d %b %Y') if task.due_date else None,
                    'task_list': task.task_list.name if task.task_list else None,
                    'has_analysis': task.ai_analyzed_at is not None,
                })
        
        # Sort by priority score
        priorities.sort(key=lambda x: x.get('priority_score', 0) or 0, reverse=True)
        
        return render(request, 'arva/ai_priority_queue.html', {
            'priorities': priorities,
            'total_tasks': len(priorities)
        })
        
    except Exception as e:
        messages.error(request, f'Error loading priority queue: {str(e)}')
        return render(request, 'arva/ai_priority_queue.html', {
            'priorities': [],
            'total_tasks': 0,
            'error': str(e)
        })


@login_required
@require_POST
def ai_priority_refresh(request):
    """Refresh AI analysis for all tasks (called via AJAX)."""
    try:
        ai_service = get_ai_service()
        
        # Get tasks for user
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            Q(assignees=request.user) | Q(project__owner=request.user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        )[:50]
        
        # Analyze all tasks
        analyzed_count = 0
        for task in tasks:
            analysis = ai_service.analyze_task(task)
            if 'error' not in analysis:
                task.ai_priority_score = analysis.get('priority_score')
                task.ai_priority_reason = analysis.get('reasoning', '')
                task.ai_complexity = analysis.get('complexity', '')
                task.ai_estimated_hours = analysis.get('estimated_hours')
                task.ai_analyzed_at = now()
                task.save(update_fields=[
                    'ai_priority_score', 'ai_priority_reason', 'ai_complexity',
                    'ai_estimated_hours', 'ai_analyzed_at'
                ])
                analyzed_count += 1
        
        return JsonResponse({
            'success': True,
            'analyzed_count': analyzed_count,
            'message': f'Successfully analyzed {analyzed_count} tasks'
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
def _get_priority_level(score):
    """Helper to convert score to priority level."""
    if score is None:
        return 'Unknown'
    if score >= 80:
        return 'Critical'
    elif score >= 60:
        return 'High'
    elif score >= 40:
        return 'Medium'
    else:
        return 'Low'
    
# AI Chat Assistant Views
@login_required
def ai_chat(request):
    """Display AI Chat interface with conversation history."""
    # Get chat history for this user (private)
    chat_messages = AIChatMessage.objects.filter(
        user=request.user
    ).order_by('created_at')[:50]
    
    return render(request, 'arva/ai_chat.html', {
        'chat_messages': chat_messages,
    })

@login_required
@require_POST
def ai_chat_send(request):
    """Send message to AI and get response."""
    message = request.POST.get('message', '').strip()
    
    if not message:
        return JsonResponse({'success': False, 'error': 'Message is empty'})
    
    try:
        # Save user message
        user_msg = AIChatMessage.objects.create(
            user=request.user,
            role='user',
            content=message
        )
        
        # Get chat history for context
        chat_history = list(AIChatMessage.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10].values('role', 'content'))
        chat_history.reverse()
        
        # Get AI response
        ai_service = get_ai_chat_service()
        ai_response = ai_service.chat(request.user, message, chat_history)
        
        # Save AI response
        ai_msg = AIChatMessage.objects.create(
            user=request.user,
            role='assistant',
            content=ai_response
        )
        
        return JsonResponse({
            'success': True,
            'user_message': {
                'id': user_msg.id,
                'content': user_msg.content,
                'created_at': user_msg.created_at.strftime('%H:%M')
            },
            'ai_message': {
                'id': ai_msg.id,
                'content': ai_msg.content,
                'created_at': ai_msg.created_at.strftime('%H:%M')
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
@require_POST
def ai_chat_clear(request):
    """Clear chat history for current user."""
    AIChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({'success': True})

@login_required
def ai_chat_today_work(request):
    """Get AI recommendation for today's work."""
    try:
        ai_service = get_ai_chat_service()
        recommendation = ai_service.get_work_recommendation(request.user)
        
        # Save as AI message
        ai_msg = AIChatMessage.objects.create(
            user=request.user,
            role='assistant',
            content=recommendation
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': ai_msg.id,
                'content': ai_msg.content,
                'created_at': ai_msg.created_at.strftime('%H:%M')
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
