"""
Views Project
=============
Menangani CRUD project, archive, activity log, members, dan task lists.
"""

from datetime import datetime

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db.models import Prefetch, Q, Max, Case, When, IntegerField
from django.db import models as dj_models
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils.timezone import now
from datetime import timedelta
from django.db.models.functions import Lower

from ..models import (
    Project, ProjectMember, SubProject, Task, ActivityLog, TaskList,
)
from ..forms import ProjectForm, TaskForm, CommentForm, AttachmentForm, ChecklistItemForm, ProjectMemberForm, TaskListForm

from .helpers import (
    get_accessible_projects_queryset,
    get_user_project_or_404,
    get_project_subproject_or_404,
    get_role,
    require_role,
    can_manage_project,
    permission_denied_response,
    is_project_locked,
    closed_project_error,
    sync_project_shares,
    STRUCTURED_TASK_PRIORITIES,
    STRUCTURED_TASK_STATUSES,
    normalize_user_mention_query,
)

User = get_user_model()


def _can_edit_project(user, project):
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    if project.owner_id == user.id:
        return True
    if project.pm_assignee_id and project.pm_assignee_id == user.id:
        return True
    return False


def _project_edit_denied_message(user, project, action='edit this project'):
    if not getattr(user, 'is_authenticated', False):
        return f'Access denied. You must sign in to {action}.'
    if project.is_private and not project.can_user_view(user):
        return 'Access denied. Project is private and your account is not included in shared users.'
    return (
        f'Access denied. You do not have permission to {action} because only the Superuser, '
        'project creator, or project PM can perform this action.'
    )


def _build_task_status_priority_case(is_structured_project):
    """Urutan prioritas status default: in progress -> default -> infeasible -> done."""
    if is_structured_project:
        return Case(
            When(status=Task.STATUS_IN_PROGRESS, then=0),
            When(status=Task.STATUS_NONE, then=1),
            When(status=Task.STATUS_INFEASIBLE, then=2),
            When(status=Task.STATUS_DONE, then=3),
            default=4,
            output_field=IntegerField(),
        )
    return Case(
        When(task_list__name__iexact='in progress', then=0),
        When(task_list__name__iexact='to do', then=1),
        When(task_list__name__iexact='infeasible', then=2),
        When(task_list__name__iexact='done', then=3),
        default=1,
        output_field=IntegerField(),
    )


def _apply_project_task_sort(queryset, is_structured_project, sort_mode):
    """Apply server-side sort for project detail task collections."""
    mode = (sort_mode or 'default').strip().lower()
    tasks = queryset.annotate(_status_priority=_build_task_status_priority_case(is_structured_project))

    if mode == 'updated_asc':
        return tasks.order_by('_status_priority', 'updated_at', 'created_at', 'id')
    if mode == 'updated_desc':
        return tasks.order_by('_status_priority', '-updated_at', '-created_at', '-id')
    if mode in {'due_asc', 'due_desc'}:
        tasks = tasks.annotate(
            _due_is_null=Case(
                When(due_date__isnull=True, then=1),
                default=0,
                output_field=IntegerField(),
            )
        )
        if mode == 'due_asc':
            return tasks.order_by('_status_priority', '_due_is_null', 'due_date', '-created_at', '-id')
        return tasks.order_by('_status_priority', '_due_is_null', '-due_date', '-created_at', '-id')
    if mode in {'title_asc', 'title_desc'}:
        tasks = tasks.annotate(_title_sort=Lower('title'))
        if mode == 'title_asc':
            return tasks.order_by('_status_priority', '_title_sort', '-created_at', '-id')
        return tasks.order_by('_status_priority', '-_title_sort', '-created_at', '-id')
    return tasks.order_by('_status_priority', '-created_at', '-id')


# ============================================================
# PROJECT LIST & BOARD
# ============================================================

@login_required
def project_list(request):
    """Halaman utama yang menampilkan daftar project yang bisa diakses user.
    
    Menampilkan:
    - Daftar project yang bisa diakses (publik atau yang di-share)
    - Project yang dimiliki user
    - User yang sedang online
    - Project yang sudah ditutup
    """
    accessible_projects = get_accessible_projects_queryset(request.user)
    projects = accessible_projects.annotate(
        last_task_activity=Max('tasks__updated_at'),
        _sort_done=Case(
            When(is_project=True, is_closed=True, then=1),
            default=0,
            output_field=IntegerField(),
        ),
    ).prefetch_related(
        'subprojects',
        'memberships__user',
    ).distinct().order_by('_sort_done', '-created_at', '-id')
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
def project_detail(request, pk):
    """Halaman detail project yang menampilkan board/task per project.
    
    Fitur:
    - Filter berdasarkan subproject, assignee, status, priority, label, due date
    - Paginasi untuk tampilan list
    - Mendukung tampilan board (per list) dan list (tabel)
    - AJAX rendering untuk filter tanpa reload
    """
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
    assignee_query = normalize_user_mention_query(request.GET.get('assignee_q', ''))
    status_id = request.GET.get('status', '').strip()
    priority_code = request.GET.get('priority', '').strip()
    label_id = request.GET.get('label', '')
    due = request.GET.get('due', '')
    sort_mode = request.GET.get('sort', 'default').strip().lower()
    page_number = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', '25').strip()
    if per_page not in {'25', '50', '100'}:
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
            Q(assignees__email__icontains=assignee_query) |
            Q(assignees__first_name__icontains=assignee_query) |
            Q(assignees__last_name__icontains=assignee_query)
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

    ordered_tasks_qs = _apply_project_task_sort(base_tasks, project.is_project, sort_mode)

    list_tasks_qs = ordered_tasks_qs
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
                Prefetch('tasks', queryset=ordered_tasks_qs, to_attr='filtered_tasks')
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
            Prefetch('tasks', queryset=ordered_tasks_qs, to_attr='filtered_tasks')
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
        'per_page_options': ['25', '50', '100'],
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
            'sort': sort_mode,
            'page': str(list_page_obj.number),
            'per_page': per_page,
        },
        'shared_members': shared_members,
        'shared_user_ids': shared_user_ids,
        'shared_role_default': ProjectMember.ROLE_MEMBER,
        'all_users': User.objects.exclude(id=request.user.id).order_by('username'),
        'project_is_locked': is_project_locked(project),
        'project_can_manage_status': can_manage_project(request.user, project),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('arva/_task_board.html', context, request=request)
        return JsonResponse({'html': html})

    return render(request, 'arva/project_detail.html', context)


# ============================================================
# PROJECT CRUD
# ============================================================

@login_required
@require_POST
def project_create(request):
    """Buat project baru.
    
    Otomatis membuat 3 task list default: To Do, In Progress, Done.
    Sinkronkan shared users jika project bersifat private.
    """
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
    """Edit project yang sudah ada (hanya pemilik yang bisa)."""
    project = get_user_project_or_404(request.user, pk)
    if not _can_edit_project(request.user, project):
        return permission_denied_response(
            request,
            _project_edit_denied_message(request.user, project),
            code='project_edit_forbidden',
        )

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
def project_update(request, pk):
    """Update project (hanya pemilik yang bisa)."""
    project = get_user_project_or_404(request.user, pk)
    if not _can_edit_project(request.user, project):
        return permission_denied_response(
            request,
            _project_edit_denied_message(request.user, project, action='update this project'),
            code='project_update_forbidden',
        )
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
def project_delete(request, pk):
    """Hapus project (hanya pemilik yang bisa).
    Project yang masih punya task tidak bisa dihapus."""
    project = get_user_project_or_404(request.user, pk)
    if not (request.user.is_superuser or project.owner_id == request.user.id):
        return permission_denied_response(
            request,
            "Access denied. Only the project creator or a superuser can delete this project.",
            code="project_delete_forbidden",
        )
    
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


# ============================================================
# PROJECT STATUS (CLOSE / REOPEN)
# ============================================================

@login_required
@require_POST
def project_close(request, pk):
    """Tutup project (hanya untuk structured project)."""
    project = get_user_project_or_404(request.user, pk)
    if not can_manage_project(request.user, project):
        return permission_denied_response(
            request,
            'Access denied. You do not have permission to perform this action because only the Superuser, project creator, or project PM can close this project.',
            code='project_close_forbidden',
        )
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
    """Buka kembali project yang sudah ditutup."""
    project = get_user_project_or_404(request.user, pk)
    if not can_manage_project(request.user, project):
        return permission_denied_response(
            request,
            'Access denied. You do not have permission to perform this action because only the Superuser, project creator, or project PM can re-open this project.',
            code='project_reopen_forbidden',
        )
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


# ============================================================
# PROJECT CONVERT
# ============================================================

@login_required
@require_POST
def project_convert_to_subproject(request, pk):
    """Konversi project menjadi subproject dari project lain.
    Tidak bisa dikonversi jika project masih punya subproject."""
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

    if project.subprojects.exists():
        return JsonResponse({'success': False, 'error': 'Project has sub-projects and cannot be converted.'}, status=400)

    target_project_id = request.POST.get('target_project_id')
    if not target_project_id:
        return JsonResponse({'success': False, 'error': 'Missing target project.'}, status=400)

    target_project = get_user_project_or_404(request.user, target_project_id)
    if not require_role(request.user, target_project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

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


# ============================================================
# PROJECT ARCHIVE & ACTIVITY
# ============================================================

@login_required
def project_archive(request, pk):
    """Tampilkan task dan list yang sudah di-archive dalam project."""
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

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
    """Tampilkan log aktivitas project dengan filter dan paginasi."""
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

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


# ============================================================
# PROJECT MEMBERS
# ============================================================

@login_required
def project_members(request, pk):
    """Tampilkan halaman manajemen member project."""
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if project.owner_id != request.user.id:
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

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
    """Tambah member baru ke project."""
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

    form = ProjectMemberForm(request.POST)
    form.fields['user'].queryset = User.objects.exclude(id=request.user.id)

    if form.is_valid():
        member = form.save(commit=False)
        member.project = project
        member.role = ProjectMember.ROLE_MEMBER

        if member.user == request.user:
            return permission_denied_response(
                request,
                'Access denied. You cannot add yourself as a member to this project.',
                code='project_member_add_self_forbidden',
            )

        if ProjectMember.objects.filter(project=project, user=member.user).exists():
            return permission_denied_response(
                request,
                'Access denied. This user is already a project member.',
                status=400,
                code='project_member_already_exists',
            )

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
    """Update role member project (sistem role sudah disederhanakan)."""
    member = get_object_or_404(ProjectMember, id=member_id)
    project = member.project

    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

    new_role = request.POST.get("role")

    if member.user == project.owner:
        return JsonResponse({"success": False, "error": "Owner role cannot be changed."}, status=400)

    if member.role != ProjectMember.ROLE_MEMBER:
        member.role = ProjectMember.ROLE_MEMBER
        member.save(update_fields=["role"])

    return JsonResponse({"success": True, "role": ProjectMember.ROLE_MEMBER})


@login_required
@require_POST
def project_member_delete(request, member_id):
    """Hapus member dari project."""
    member = get_object_or_404(ProjectMember, id=member_id)
    project = member.project
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    member.delete()
    return redirect('project_members', pk=project.pk)


# ============================================================
# TASK LISTS (BOARD COLUMNS)
# ============================================================

@login_required
def project_lists(request, pk):
    """Ambil daftar task list dalam project (untuk dropdown/select)."""
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
def tasklist_create(request, pk):
    """Buat task list baru dalam project."""
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')

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
    """Ubah urutan task list dalam project."""
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')
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
    """Hapus task list dari project."""
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')
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
    """Archive task list beserta semua task di dalamnya."""
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')
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
    """Batalkan archive task list."""
    tl = get_object_or_404(TaskList, id=list_id)
    project = get_user_project_or_404(request.user, tl.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')
    tl.is_archived = False
    tl.save()
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_unarchived',
        description=f"List '{tl.name}' unarchived"
    )
    return JsonResponse({'success': True})
