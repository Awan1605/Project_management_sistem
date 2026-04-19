"""
Views Komentar, Lampiran, dan Checklist
=======================================
Menangani operasi terkait komentar, balasan, lampiran, dan checklist pada task.
"""

from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string

from .helpers import get_user_project_or_404, get_role, is_project_locked, closed_project_error
from ..models import Task, Comment, Attachment, ChecklistItem, ActivityLog
from ..forms import CommentForm, AttachmentForm, ChecklistItemForm


# ============================================================
# KOMENTAR
# ============================================================

@login_required
@require_POST
def comment_add(request, task_id):
    """Tambah komentar baru pada task.
    
    Hanya admin project atau assignee task yang bisa menambah komentar.
    Jika project terkunci, tolak perubahan.
    """
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
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
    """Balas komentar yang sudah ada (membuat threaded comment).
    
    Komentar balasan memiliki parent yang mengarah ke komentar asli.
    Hanya admin project atau assignee task yang bisa membalas.
    """
    parent = get_object_or_404(Comment, id=comment_id)
    task = parent.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
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
        action='comment_added', description="replied to a comment"
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
    """Hapus komentar.
    
    Hanya pemilik komentar atau owner project yang bisa menghapus.
    Project terkunci tidak bisa menghapus komentar.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    task = comment.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    # Hanya pemilik komentar atau owner project yang boleh menghapus
    if not (comment.user_id == request.user.id or project.owner_id == request.user.id):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='comment_added', description="deleted a comment"
    )

    comment.delete()
    return JsonResponse({'success': True})


# ============================================================
# LAMPIRAN (ATTACHMENT)
# ============================================================

@login_required
@require_POST
def attachment_add(request, task_id):
    """Tambah lampiran/file pada task.
    
    Mendukung upload file dengan validasi form.
    Hanya admin project atau assignee task yang bisa menambah lampiran.
    """
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
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


# ============================================================
# CHECKLIST
# ============================================================

@login_required
@require_POST
def checklist_add(request, task_id):
    """Tambah item checklist baru pada task.
    
    Hanya admin project atau assignee task yang bisa menambah checklist.
    """
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
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
    """Edit konten item checklist yang sudah ada.
    
    Hanya admin project atau assignee task yang bisa mengedit.
    """
    item = get_object_or_404(ChecklistItem, id=item_id)
    task = item.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
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
    """Toggle status checklist (centang/buka centang).
    
    Hanya admin project atau assignee task yang bisa toggle.
    """
    item = get_object_or_404(ChecklistItem, id=item_id)
    project = get_user_project_or_404(request.user, item.task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in item.task.assignees.all():
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
    """Hapus item checklist dari task.
    
    Hanya admin project atau assignee task yang bisa menghapus.
    """
    item = get_object_or_404(ChecklistItem, id=item_id)
    task = item.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error()
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': "Forbidden"}, status=403)

    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_toggled', description=f"deleted checklist item: '{item.content}'"
    )
    item.delete()

    return JsonResponse({"success": True})
