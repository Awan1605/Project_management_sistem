"""
Fungsi Bantu Views
==================
Berisi fungsi-fungsi utilitas yang dipakai bersama oleh modul views lainnya.
Termasuk: query set project, pengecekan role, pengecekan project terkunci, dll.
"""

from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.db.models import Q

from ..models import Project, ProjectMember, SubProject, Task


# ============================================================
# KONSTANTA
# ============================================================

# Prioritas task yang valid (P0-P4)
STRUCTURED_TASK_PRIORITIES = {
    Task.PRIORITY_P0,
    Task.PRIORITY_P1,
    Task.PRIORITY_P2,
    Task.PRIORITY_P3,
    Task.PRIORITY_P4,
}

# Status task yang valid
STRUCTURED_TASK_STATUSES = {
    Task.STATUS_NONE,
    Task.STATUS_IN_PROGRESS,
    Task.STATUS_DONE,
    Task.STATUS_INFEASIBLE,
}


# ============================================================
# FUNGSI QUERY SET PROJECT
# ============================================================

def get_accessible_projects_queryset(user):
    """Ambil queryset project yang bisa diakses oleh user tertentu.
    
    User bisa mengakses project jika:
    - Project bersifat publik (is_private=False), ATAU
    - User adalah pemilik project, ATAU
    - User adalah member dari project tersebut
    """
    if getattr(user, "is_superuser", False):
        return Project.objects.all()
    return Project.objects.filter(
        Q(is_private=False) |
        Q(owner=user) |
        Q(memberships__user=user)
    ).distinct()


def normalize_user_mention_query(raw_value):
    """Normalisasi query pencarian user.

    Mendukung format mention seperti:
    - @andre
    - @andre@email.com
    """
    value = (raw_value or '').strip()
    if value.startswith('@'):
        value = value[1:].strip()
    return value


def get_user_project_or_404(user, pk):
    """Ambil project berdasarkan pk, hanya jika user memiliki akses.
    Jika tidak ditemukan, return 404."""
    qs = get_accessible_projects_queryset(user)
    return get_object_or_404(qs, pk=pk)


def get_project_subproject_or_404(project, sub_id):
    """Ambil subproject berdasarkan id, hanya jika milik project yang benar.
    Jika tidak ditemukan, return 404."""
    return get_object_or_404(SubProject, id=sub_id, project=project)


# ============================================================
# FUNGSI ROLE & AKSES
# ============================================================

def get_role(user, project):
    """Ambil role user dalam project.
    
    Catatan: Sistem role-based sudah disederhanakan.
    Semua user yang punya akses project diperlakukan seragam.
    """
    if not project.can_user_view(user):
        return None
    # Template lama masih memakai "admin" untuk branching
    # Dengan role-based access yang dihapus, semua user dianggap sama
    return ProjectMember.ROLE_ADMIN


def require_role(user, project, allowed_roles):
    """Cek apakah user memiliki role yang diizinkan.
    
    Catatan: Sistem role gating sudah deprecated.
    Hanya mempertahankan kontrol owner untuk endpoint yang membutuhkan admin.
    """
    normalized = set(allowed_roles or [])
    if normalized == {ProjectMember.ROLE_ADMIN}:
        return project.owner_id == user.id
    return project.can_user_view(user)


def can_manage_project(user, project):
    """Hak kelola close/re-open project.

    Diizinkan untuk:
    - superuser
    - creator project (field lama `created_by` atau field aktif `owner`)
    - PM project (field lama `pm` atau field aktif `pm_assignee`)
    """
    if not getattr(user, "is_authenticated", False) or project is None:
        return False

    creator_id = getattr(project, "created_by_id", None) or getattr(project, "owner_id", None)
    pm_id = getattr(project, "pm_id", None) or getattr(project, "pm_assignee_id", None)

    return bool(
        user.is_superuser or
        creator_id == user.id or
        pm_id == user.id
    )


# ============================================================
# FUNGSI PROJECT TERKUNCI
# ============================================================

def is_project_locked(project):
    """Cek apakah project sedang terkunci (ditutup).
    """
    return bool(project and project.is_project and project.is_closed)


def _wants_json(request):
    if request is None:
        return False
    xrw = (request.headers.get('x-requested-with') or '').lower()
    accept = (request.headers.get('accept') or '').lower()
    return xrw == 'xmlhttprequest' or 'application/json' in accept


def permission_denied_response(request, message, *, status=403, code='permission_denied', details=None):
    payload = {
        'success': False,
        'error': message,
        'code': code,
    }
    if details:
        payload['details'] = details
    if _wants_json(request):
        return JsonResponse(payload, status=status)
    return render(request, 'arva/403.html', payload, status=status)


def closed_project_error(request=None, *, action='modify this project'):
    """Return error untuk project yang sudah ditutup, JSON untuk AJAX dan page untuk normal request."""
    message = f'Access denied. Project is closed and cannot be modified. Re-open the project to {action}.'
    if request is None:
        return JsonResponse({'success': False, 'error': message, 'code': 'project_closed'}, status=403)
    return permission_denied_response(request, message, status=403, code='project_closed')


def custom_permission_denied_view(request, exception=None):
    message = 'Access denied. You do not have permission to access this page.'
    return permission_denied_response(request, message, status=403, code='forbidden')


# ============================================================
# FUNGSI SYNC PROJECT SHARES
# ============================================================

def sync_project_shares(project, cleaned_data):
    """Sinkronkan anggota project yang di-share.
    
    Untuk project private:
    - Hapus member yang tidak ada di daftar terpilih
    - Tambah/update member sesuai daftar terpilih
    
    Untuk project publik:
    - Tidak ada perubahan (semua user bisa akses)
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    selected_users = cleaned_data.get('shared_users') or User.objects.none()
    selected_ids = set(selected_users.values_list('id', flat=True))

    if project.is_private:
        # Project private: hanya owner + user yang di-share
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
    # Project publik tetap transparan; membership yang ada tetap dipertahankan


# ============================================================
# FUNGSI HELPER AI
# ============================================================

def _get_priority_level(score):
    """Konversi skor prioritas (1-100) menjadi level prioritas."""
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


def is_admin(user):
    """Cek apakah user adalah admin/superuser.
    
    Args:
        user: User object
    
    Returns:
        bool: True jika user adalah superuser atau staff
    """
    return user.is_authenticated and (user.is_superuser or user.is_staff)
