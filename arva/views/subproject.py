"""
Views Subproject
=================
Menangani CRUD subproject, pindah subproject, dan konversi antara project/subproject.
"""

from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string

from ..models import Project, ProjectMember, SubProject, Task, TaskList, ActivityLog
from ..forms import SubProjectForm

from .helpers import (
    get_user_project_or_404,
    get_project_subproject_or_404,
    get_role,
    require_role,
    permission_denied_response,
    is_project_locked,
    closed_project_error,
)


# ============================================================
# SUBPROJECT CRUD
# ============================================================

@login_required
def subproject_list(request, pk):
    """Tampilkan daftar subproject dalam project."""
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    if role not in [ProjectMember.ROLE_ADMIN, ProjectMember.ROLE_MEMBER, ProjectMember.ROLE_VIEWER]:
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

    subprojects = project.subprojects.all().order_by('-created_at')
    admin_projects = Project.objects.filter(owner=request.user).distinct().order_by('name')
    return render(request, 'arva/subproject_list.html', {
        'project': project,
        'subprojects': subprojects,
        'user_role': role,
        'admin_projects': admin_projects,
    })


@login_required
@require_POST
def subproject_create(request, pk):
    """Buat subproject baru dalam project.
    
    Jika ini subproject pertama, semua task dan list yang sudah ada
    akan dipindahkan ke subproject baru secara otomatis.
    """
    project = get_user_project_or_404(request.user, pk)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')

    had_subprojects = project.subprojects.exists()
    form = SubProjectForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    subproject = form.save(commit=False)
    subproject.project = project
    subproject.save()

    # Jika ini subproject pertama, pindahkan semua task & list ke subproject
    if not had_subprojects:
        TaskList.objects.filter(project=project, sub_project__isnull=True).update(sub_project=subproject)
        Task.objects.filter(project=project, sub_project__isnull=True).update(sub_project=subproject)

    # Buat task list default untuk subproject baru
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
    """Hapus subproject.
    Subproject yang masih punya task tidak bisa dihapus."""
    subproject = get_object_or_404(SubProject, id=subproject_id)
    project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')

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
    """Edit nama dan deskripsi subproject."""
    subproject = get_object_or_404(SubProject, id=subproject_id)
    project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(project):
        return closed_project_error(request, action='modify this project/task')

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


# ============================================================
# SUBPROJECT MOVE & CONVERT
# ============================================================

@login_required
@require_POST
def subproject_move(request, subproject_id):
    """Pindahkan subproject dari satu project ke project lain.
    
    Semua task list dan task yang ada di subproject akan ikut berpindah.
    """
    subproject = get_object_or_404(SubProject, id=subproject_id)
    source_project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, source_project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(source_project):
        return closed_project_error(request, action='modify this project/task')

    target_project_id = request.POST.get('project_id')
    if not target_project_id:
        return JsonResponse({'success': False, 'error': 'Missing target project.'}, status=400)

    target_project = get_user_project_or_404(request.user, target_project_id)
    if not require_role(request.user, target_project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')
    if is_project_locked(target_project):
        return closed_project_error(request, action='modify this project/task')

    if str(source_project.id) == str(target_project.id):
        return JsonResponse({'success': True})

    subproject.project = target_project
    subproject.save()

    # Pindahkan semua list dan task ke target project
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
    """Konversi subproject menjadi project mandiri.
    
    Semua task list dan task akan dipindahkan ke project baru.
    Member dari project asal akan disalin ke project baru.
    """
    subproject = get_object_or_404(SubProject, id=subproject_id)
    source_project = get_user_project_or_404(request.user, subproject.project.id)
    if not require_role(request.user, source_project, [ProjectMember.ROLE_ADMIN]):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action.', code='permission_forbidden')

    new_project = Project.objects.create(
        owner=source_project.owner,
        name=subproject.name,
        description=subproject.description,
    )

    # Salin membership dari project asal ke project baru
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

    # Pindahkan list dan task ke project baru
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


# ============================================================
# HELPER UNTUK SUBPROJECT
# ============================================================

@login_required
def project_subprojects(request, pk):
    """Ambil daftar subproject dalam project (format JSON untuk AJAX)."""
    project = get_user_project_or_404(request.user, pk)
    subprojects = list(project.subprojects.order_by('created_at').values('id', 'name'))
    return JsonResponse({'success': True, 'subprojects': subprojects})
