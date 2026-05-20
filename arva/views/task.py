"""
Views Task
==========
Menangani CRUD task, pindah task, transfer antar project, archive, inline update, dan pencarian.
"""

from datetime import datetime

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db import transaction, models as dj_models
from django.db.models import Q, Max, Prefetch, Case, When, IntegerField, Value, CharField, F
from django.db.models.functions import Concat, Lower
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

from ..models import (
    Project, ProjectMember, Task, TaskList, ActivityLog, Comment, Attachment, Label,
)
from ..forms import TaskForm, CommentForm
from ..utils import EmailThread

from .helpers import (
    get_accessible_projects_queryset,
    get_user_project_or_404,
    get_project_subproject_or_404,
    get_role,
    require_role,
    is_project_locked,
    closed_project_error,
    STRUCTURED_TASK_PRIORITIES,
    STRUCTURED_TASK_STATUSES,
    normalize_user_mention_query,
)

User = get_user_model()


def _task_search_status_priority_case():
    """Default global task search order: unfinished first, done last."""
    return Case(
        When(status=Task.STATUS_IN_PROGRESS, then=0),
        When(task_list__name__iexact='in progress', then=0),
        When(status=Task.STATUS_NONE, then=1),
        When(task_list__name__iexact='to do', then=1),
        When(status=Task.STATUS_INFEASIBLE, then=2),
        When(task_list__name__iexact='infeasible', then=2),
        When(status=Task.STATUS_DONE, then=3),
        When(task_list__name__iexact='done', then=3),
        default=1,
        output_field=IntegerField(),
    )


def _apply_task_search_sort(queryset, sort_mode):
    """Apply server-side ordering for task search results."""
    mode = (sort_mode or 'default').strip().lower()
    tasks = queryset.annotate(_status_priority=_task_search_status_priority_case())

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
    if mode in {'project_asc', 'project_desc'}:
        tasks = tasks.annotate(_project_sort=Lower('project__name'))
        if mode == 'project_asc':
            return tasks.order_by('_status_priority', '_project_sort', '-created_at', '-id')
        return tasks.order_by('_status_priority', '-_project_sort', '-created_at', '-id')
    return tasks.order_by('_status_priority', '-created_at', '-id')


# ============================================================
# TASK BOARD VIEWS
# ============================================================

@login_required
def task_search_by_user(request):
    """Cari task berdasarkan user, status, due date, label, dan project.
    Mengembalikan hasil dalam format JSON untuk AJAX."""
    user_query_raw = request.GET.get('user_q', '')
    user_query = normalize_user_mention_query(user_query_raw)
    status = request.GET.get('status', '').strip()
    due = request.GET.get('due', '').strip()
    label_id = request.GET.get('label', '').strip()
    project_id = request.GET.get('project', '').strip()
    sort_mode = request.GET.get('sort', 'default').strip().lower()

    accessible_projects = get_accessible_projects_queryset(request.user)
    tasks = Task.objects.filter(
        project__in=accessible_projects,
        is_archived=False,
    ).select_related(
        'project',
        'task_list',
        'created_by',
        'created_by__userprofile',
        'project__pm_assignee',
        'project__pm_assignee__userprofile',
    ).prefetch_related(
        Prefetch('assignees', queryset=User.objects.select_related('userprofile').order_by('username')),
        'labels',
    ).distinct()

    if user_query:
        tasks = tasks.annotate(
            assignee_full_name=Concat(
                F('assignees__first_name'),
                Value(' '),
                F('assignees__last_name'),
                output_field=CharField(),
            ),
        ).filter(
            Q(assignees__username__icontains=user_query) |
            Q(assignees__email__icontains=user_query) |
            Q(assignees__first_name__icontains=user_query) |
            Q(assignees__last_name__icontains=user_query) |
            Q(assignee_full_name__icontains=user_query)
        )
    if status:
        tasks = tasks.filter(task_list__name__iexact=status)
    if due:
        tasks = tasks.filter(due_date__lte=due)
    if label_id:
        tasks = tasks.filter(labels__id=label_id)
    if project_id:
        tasks = tasks.filter(project_id=project_id)

    tasks = _apply_task_search_sort(tasks, sort_mode)[:200]
    results = []
    for task in tasks:
        assignees = list(task.assignees.all())
        primary_assignee = assignees[0] if assignees else task.project.pm_assignee
        assignee_count = len(assignees)
        reporter = task.created_by
        reporter_profile = getattr(reporter, 'userprofile', None) if reporter else None
        assignee_profile = getattr(primary_assignee, 'userprofile', None) if primary_assignee else None
        labels = list(task.labels.all()[:3])
        status_code = task.status if task.project.is_project else (
            'done' if task.task_list.name.lower() == 'done' else (
                'in_progress' if task.task_list.name.lower() == 'in progress' else '-'
            )
        )
        status_display = task.get_status_display() if task.project.is_project else task.task_list.name
        results.append({
            'id': task.id,
            'title': task.title,
            'project_id': task.project_id,
            'project_name': task.project.name,
            'task_list_name': task.task_list.name,
            'status': status_display,
            'status_code': status_code,
            'priority': task.priority or Task.PRIORITY_P2,
            'priority_display': task.get_priority_display() if task.priority else 'P2 - Medium',
            'is_project': bool(task.project.is_project),
            'sub_project_name': task.sub_project.name if task.sub_project else '',
            'description': strip_tags(task.description or ''),
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'updated_at': task.updated_at.isoformat() if task.updated_at else '',
            'start_date': task.start_date.isoformat() if task.start_date else '',
            'start_date_display': task.start_date.strftime('%d %b %Y') if task.start_date else '',
            'start_date_tbd': bool(task.start_date_tbd),
            'due_date': task.due_date.isoformat() if task.due_date else '',
            'due_date_display': task.due_date.strftime('%d %b %Y') if task.due_date else 'No due',
            'due_status': 'overdue' if task.is_overdue else ('today' if task.is_due_today else ('soon' if task.is_due_soon else ('later' if task.due_date else 'none'))),
            'assignees': [u.username for u in assignees],
            'assignees_display': ', '.join(u.username for u in assignees[:3]) + (f" +{len(assignees)-3}" if len(assignees) > 3 else ''),
            'assignee': {
                'username': primary_assignee.username if primary_assignee else '',
                'email': primary_assignee.email if primary_assignee else '',
                'avatar_url': assignee_profile.avatar_url if assignee_profile else '/static/arva/img/default-avatar.png',
                'initial': (primary_assignee.username[0].upper() if primary_assignee and primary_assignee.username else 'U'),
                'extra_count': max(assignee_count - 1, 0),
            },
            'reporter': {
                'username': reporter.username if reporter else '',
                'email': reporter.email if reporter else '',
                'avatar_url': reporter_profile.avatar_url if reporter_profile else '/static/arva/img/default-avatar.png',
                'initial': (reporter.username[0].upper() if reporter and reporter.username else 'U'),
            },
            'labels': [{'name': label.name, 'color': label.color} for label in labels],
            'url': f"/task/{task.id}/",
        })

    return JsonResponse({
        'success': True,
        'count': len(results),
        'sort': sort_mode or 'default',
        'results': results
    })


@login_required
def task_user_suggestions(request):
    """Cari kandidat user untuk mention-style assignee filter."""
    raw_query = request.GET.get('q', '')
    query = normalize_user_mention_query(raw_query)

    accessible_projects = get_accessible_projects_queryset(request.user)
    users = User.objects.filter(
        assigned_tasks__project__in=accessible_projects,
        assigned_tasks__is_archived=False,
        is_active=True,
    ).annotate(
        full_name_value=Concat(
            F('first_name'),
            Value(' '),
            F('last_name'),
            output_field=CharField(),
        ),
    )
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(full_name_value__icontains=query)
        )
    users = users.select_related('userprofile').distinct().order_by('username')[:20]

    results = []
    seen_user_ids = set()
    for user in users:
        if user.id in seen_user_ids:
            continue
        seen_user_ids.add(user.id)
        profile = getattr(user, 'userprofile', None)
        full_name = user.get_full_name().strip()
        avatar_url = profile.avatar_url if profile else '/static/arva/img/default-avatar.png'
        results.append({
            'id': user.id,
            'username': user.username,
            'email': user.email or '',
            'full_name': full_name,
            'avatar_url': avatar_url,
        })

    return JsonResponse({'success': True, 'count': len(results), 'results': results})


@login_required
def my_cards(request):
    """Tampilkan semua task yang di-assign ke user atau di project milik user."""
    accessible_projects = get_accessible_projects_queryset(request.user)
    tasks = Task.objects.filter(
        project__in=accessible_projects,
        is_archived=False
    ).select_related('project', 'task_list').annotate(
        _status_priority=_task_search_status_priority_case()
    ).order_by('_status_priority', '-created_at', '-id')
    return render(request, 'arva/my_cards.html', {'tasks': tasks})


# ============================================================
# TASK CRUD
# ============================================================

@login_required
@require_POST
def task_create(request, pk):
    """Buat task baru dalam project.
    
    Untuk project structured: label dan cover color dinonaktifkan.
    Untuk project biasa: bisa menambahkan komentar dan lampiran saat buat task.
    """
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
def task_view(request, task_id):
    """Tampilkan detail task dalam modal (format HTML untuk AJAX)."""
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
def task_detail(request, task_id):
    """Tampilkan detail task sebagai halaman penuh (bukan modal)."""
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
        return HttpResponseForbidden("Forbidden")

    total = task.checklist_total
    done = task.checklist_done
    percent = int((done / total) * 100) if total > 0 else 0

    view_only = bool(is_project_locked(project) or not (role == "admin" or request.user in task.assignees.all()))

    return render(request, 'arva/task_detail.html', {
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
    })


@login_required
@require_POST
def task_update(request, task_id):
    """Update task yang sudah ada."""
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
    """Hapus task (admin project ATAU task creator bisa)."""
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    
    # Check permission: admin project ATAU creator task
    role = get_role(request.user, project)
    is_admin = role == ProjectMember.ROLE_ADMIN
    is_creator = task.created_by == request.user if hasattr(task, 'created_by') else False
    
    if not is_admin and not is_creator:
        return HttpResponseForbidden("Forbidden: Only project admins or task creators can delete tasks")
    
    title = task.title
    task.delete()
    ActivityLog.objects.create(
        user=request.user, project=project, action='task_deleted',
        description=f"Task '{title}' deleted"
    )
    return JsonResponse({'success': True})


# ============================================================
# TASK MOVE & TRANSFER
# ============================================================

@login_required
@require_POST
@transaction.atomic
def task_move(request, task_id):
    """Pindahkan task ke task list lain (drag-and-drop pada board).
    Juga mengupdate urutan task dalam list."""
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
    """Transfer task ke project lain.
    
    Task akan dipindahkan ke task list pertama di target project.
    Jika target project punya subproject, subproject harus ditentukan.
    """
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


# ============================================================
# TASK ARCHIVE
# ============================================================

@login_required
@require_POST
def task_archive(request, task_id):
    """Archive task."""
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
    """Batalkan archive task."""
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


# ============================================================
# TASK INLINE UPDATE
# ============================================================

@login_required
@require_POST
def task_inline_update(request, task_id):
    """Update field task secara inline (satu field per request).
    
    Mendukung update: title, description, status, start_date, due_date,
    priority, assignees, labels, cover_color.
    Untuk assignees baru, otomatis kirim email notifikasi.
    """
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
        if project.is_project and parsed_start and task.due_date:
            due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
            if due < parsed_start:
                return JsonResponse({'success': False, 'error': 'End Date cannot be earlier than Start Date.'}, status=400)
        changed = True
        desc = "Start date updated"
    elif field == 'start_date_tbd':
        is_tbd = str(value).lower() in {'1', 'true', 'on', 'yes'}
        # Allow free toggling in both directions for a smooth inline UX.
        # Model-level clean() still enforces 'date OR tbd' on full-form save,
        # so transient states here are safe.
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
        
        # Tambahkan assignee sebagai member project dan kirim email notifikasi
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

            # Kirim email notifikasi ke assignee baru
            if uid in added_ids and user_obj != request.user:
                try:
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
                except Exception as e:
                    # Gagal kirim email tidak boleh menghentikan proses
                    import logging
                    logging.getLogger(__name__).error(f"Gagal kirim email assign task: {e}")

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
