from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db import transaction, models as dj_models
from django.contrib.auth import get_user_model
from django.db.models import Q, Max
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.utils.html import strip_tags
from datetime import datetime
from .utils import is_user_online, EmailThread

from .models import (
    Project, ProjectMember, Task, Comment, Attachment,
    ActivityLog, TaskList, ChecklistItem, Label,
    UserProfile, UserActivity, WebsiteSettings
)
from .forms import (
    RegisterForm, ProjectForm, TaskForm,
    CommentForm, AttachmentForm, TaskListForm,
    ChecklistItemForm, ProjectMemberForm, 
    CreateUserInlineForm, UserEditForm, AdminPasswordResetForm,
    AvatarUploadForm, WebsiteSettingsForm
)

User = get_user_model()

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

def get_user_project_or_404(user, pk):
    qs = Project.objects.filter(
        Q(owner=user) |
        Q(memberships__user=user) |
        Q(tasks__assignees=user)
    ).distinct()
    return get_object_or_404(qs, pk=pk)

def get_role(user, project):
    return project.get_user_role(user)

def require_role(user, project, allowed_roles):
    role = get_role(user, project)
    if role not in allowed_roles:
        return False
    return True

@login_required
def website_settings(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to manage settings.")
        return redirect("dashboard")

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
def user_list(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission.")
        return redirect('project_list')

    q = request.GET.get('q', '').strip()
    users = User.objects.all().order_by('username')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

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

    new_role = request.POST.get('role')
    if new_role not in ['admin', 'member', 'viewer']:
        return JsonResponse({'success': False, 'error': 'Invalid role'}, status=400)

    pm.role = new_role
    pm.save()

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
    projects = Project.objects.filter(
        Q(owner=request.user) | Q(memberships__user=request.user)
    ).annotate(last_task_activity=Max('tasks__updated_at')).distinct().order_by('-created_at')
    activities = UserActivity.objects.select_related('user')
    online_users = [a.user for a in activities if is_user_online(a.last_activity)]

    form = ProjectForm()
    return render(request, 'arva/project_list.html', {
        'projects': projects, 
        'project_form': form,
        'online_users': online_users,
    })

@login_required
def my_cards(request):
    tasks = Task.objects.filter(
        assignees=request.user,
        is_archived=False
    ).select_related('project', 'task_list').order_by('due_date', 'project__name')
    return render(request, 'arva/my_cards.html', {'tasks': tasks})

@login_required
@require_POST
def project_create(request):
    form = ProjectForm(request.POST)
    if form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()

        TaskList.objects.create(project=project, name='To Do', position=0)
        TaskList.objects.create(project=project, name='In Progress', position=1)
        TaskList.objects.create(project=project, name='Done', position=2)

        ActivityLog.objects.create(
            user=request.user,
            project=project,
            action='project_created',
            description=f"Project '{project.name}' created",
        )
        html = render_to_string('arva/_project_item.html', {'project': project}, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def project_edit(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)

    if role != ProjectMember.ROLE_ADMIN:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'name': project.name,
            'description': project.description
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def project_detail(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)

    if not project.lists.exists() and project.owner == request.user:
        TaskList.objects.create(project=project, name='To Do', position=0)
        TaskList.objects.create(project=project, name='In Progress', position=1)
        TaskList.objects.create(project=project, name='Done', position=2)

    q = request.GET.get('q', '')
    assignee_id = request.GET.get('assignee', '')
    label_id = request.GET.get('label', '')
    due = request.GET.get('due', '')

    base_tasks = Task.objects.filter(project=project, is_archived=False).prefetch_related(
        'labels', 'assignees', 'comments__user', 'attachments', 'checklist_items'
    )

    if role != ProjectMember.ROLE_ADMIN:
        base_tasks = base_tasks.filter(assignees=request.user)

    if q:
        base_tasks = base_tasks.filter(title__icontains=q)
    if assignee_id:
        base_tasks = base_tasks.filter(assignees__id=assignee_id)
    if label_id:
        base_tasks = base_tasks.filter(labels__id=label_id)
    if due:
        base_tasks = base_tasks.filter(due_date__lte=due)

    task_lists = list(project.lists.filter(is_archived=False).order_by('position'))
    for tl in task_lists:
        tl.filtered_tasks = base_tasks.filter(task_list=tl).order_by('order')

    task_form = TaskForm()
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    checklist_form = ChecklistItemForm()

    context = {
        'project': project,
        'task_lists': task_lists,
        'task_form': task_form,
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'checklist_form': checklist_form,
        'users': User.objects.all(),
        'user_role': role,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('arva/_task_board.html', context, request=request)
        return JsonResponse({'html': html})

    return render(request, 'arva/project_detail.html', context)

@login_required
def project_archive(request, pk):
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN:
        return HttpResponseForbidden("Forbidden")

    archived_lists = project.lists.filter(is_archived=True).order_by('position')
    archived_tasks = project.tasks.filter(is_archived=True).select_related('task_list').order_by('task_list__position', 'order')
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
    if role != ProjectMember.ROLE_ADMIN:
        return HttpResponseForbidden("Forbidden")

    activities = project.activities.select_related('user', 'task')[:100]
    return render(request, 'arva/activity_log.html', {'project': project, 'activities': activities, 'user_role': role})

@login_required
@require_POST
def project_update(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return JsonResponse({
            "success": False,
            "error": "The project cannot be updated because you are not the owner of this project."
        }, status=400)
    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
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
    if role != ProjectMember.ROLE_ADMIN:
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

    if new_role not in ["admin", "member", "viewer"]:
        return JsonResponse({"success": False, "error": "Invalid role"}, status=400)

    if member.user == project.owner:
        return JsonResponse({"success": False, "error": "Owner role cannot be changed."}, status=400)

    # if member.role == "admin" and new_role != "admin":
    #     remaining_admin = project.memberships.filter(role="admin").exclude(id=member.id).count()
    #     if remaining_admin == 0:
    #         return JsonResponse({"success": False, "error": "Project must have at least 1 admin."}, status=400)

    member.role = new_role
    member.save()

    return JsonResponse({"success": True, "role": new_role})

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

    form = TaskListForm(request.POST)
    if form.is_valid():
        tl = form.save(commit=False)
        tl.project = project
        last_pos = project.lists.aggregate(dj_models.Max('position'))['position__max'] or 0
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
        }, request=request)
        return JsonResponse({'success': True, 'html': html})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def tasklist_reorder(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return HttpResponseForbidden("Forbidden")
    ordered_ids = request.POST.getlist('ordered_ids[]')
    for index, lid in enumerate(ordered_ids):
        TaskList.objects.filter(id=lid, project=project).update(position=index)
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
    tl.is_archived = False
    tl.save()
    ActivityLog.objects.create(
        user=request.user, project=project, action='list_unarchived',
        description=f"List '{tl.name}' unarchived"
    )
    return JsonResponse({'success': True})

@login_required
def task_view(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)
    users = User.objects.all()
    labels = Label.objects.all()
    colors = ["primary", "success", "danger", "warning", "info", "dark", ""]
    comments = task.comments.filter(parent__isnull=True)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    total = task.checklist_total
    done = task.checklist_done
    percent = int((done / total) * 100) if total > 0 else 0

    view_only = not (role == "admin" or request.user in task.assignees.all())
    html = render_to_string('arva/_task_view.html', {
        'task': task,
        'project': project,
        'user_role': role,
        'users': users,
        'labels': labels,
        'colors': colors,
        'checklist_total': total,
        'checklist_done': done,
        'checklist_percent': percent,
        'root_comments': comments,
        "view_only": view_only,
    }, request=request)

    return JsonResponse({'success': True, 'html': html})

@login_required
@require_POST
def task_inline_update(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
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
    elif field == 'due_date':
        task.due_date = datetime.strptime(value, "%Y-%m-%d").date() or None
        changed = True
        desc = "Due date updated"
    elif field == 'priority':
        task.priority = value or Task.PRIORITY_MEDIUM
        changed = True
        desc = "Priority updated"
    elif field == 'assignees':
        old_ids = set(task.assignees.values_list('id', flat=True))

        ids = [i for i in value.split(',') if i]
        new_ids = set(ids)
        task.assignees.set(ids)
        changed = True
        desc = "Assignees updated"
        
        project = task.project
        added_ids = new_ids - old_ids
        for uid in ids:
            user_obj = User.objects.filter(id=uid).first()
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
    return JsonResponse({'success': True, 'html': html})

@login_required
@require_POST
def task_create(request, pk):
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER]):
        return HttpResponseForbidden("Forbidden")
    task_list_id = request.POST.get('task_list_id')
    task_list = get_object_or_404(TaskList, id=task_list_id, project=project)

    data = request.POST.copy()
    if 'priority' not in data or not data['priority']:
        data['priority'] = Task.PRIORITY_MEDIUM

    form = TaskForm(data)
    if form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.task_list = task_list
        last_order = task_list.tasks.aggregate(dj_models.Max('order'))['order__max'] or 0
        task.order = last_order + 1
        task.created_by = request.user
        task.save()
        form.save_m2m()
        ActivityLog.objects.create(
            user=request.user, project=project, task=task,
            action='task_created', description=f"Task '{task.title}' created"
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
def task_update(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)
    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return HttpResponseForbidden("Forbidden")
    data = request.POST.copy()
    if 'priority' not in data or not data['priority']:
        data['priority'] = Task.PRIORITY_MEDIUM
    form = TaskForm(data, instance=task)
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
    role = get_role(request.user, project)
    if role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER] or        (role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all()):
        return HttpResponseForbidden("Forbidden")

    new_list_id = request.POST.get('task_list_id')
    ordered_ids = request.POST.getlist('ordered_ids[]')

    new_list = get_object_or_404(TaskList, id=new_list_id, project=task.project)
    task.task_list = new_list
    task.save()

    for index, tid in enumerate(ordered_ids):
        Task.objects.filter(id=tid, project=task.project).update(order=index)

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='task_moved', description=f"Task '{task.title}' moved to list '{new_list.name}'"
    )
    return JsonResponse({'success': True})

@login_required
@require_POST
def task_archive(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
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
        "user": request.user
    }, request=request)

    return JsonResponse({"success": True, "html": html})

@login_required
@require_POST
def comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    task = comment.task
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)

    if not (role == ProjectMember.ROLE_ADMIN or comment.user == request.user):
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
    role = get_role(request.user, project)

    if role != ProjectMember.ROLE_ADMIN and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': "Forbidden"}, status=403)

    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_toggled', description=f"deleted checklist item: '{item.content}'"
    )
    item.delete()

    return JsonResponse({"success": True})
