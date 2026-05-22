"""
Views Komentar, Lampiran, dan Checklist
=======================================
Menangani operasi terkait komentar, balasan, lampiran, dan checklist pada task.
"""

import re

from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils.text import get_valid_filename
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.urls import reverse

from .helpers import (
    get_user_project_or_404,
    get_role,
    is_project_locked,
    closed_project_error,
    permission_denied_response,
)
from ..models import Task, Comment, Attachment, ChecklistItem, ActivityLog, UserNotification
from ..forms import AttachmentForm, ChecklistItemForm

ALLOWED_COMMENT_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
ALLOWED_COMMENT_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_COMMENT_IMAGE_SIZE = 5 * 1024 * 1024
MAX_COMMENT_IMAGE_COUNT = 5
MENTION_PATTERN = re.compile(r'(^|\s)@([A-Za-z0-9_.+-]{2,150})')
User = get_user_model()


def _validate_comment_images(images):
    if len(images) > MAX_COMMENT_IMAGE_COUNT:
        return f'Maximum {MAX_COMMENT_IMAGE_COUNT} pasted images per comment.'

    for image in images:
        name = get_valid_filename(image.name or 'pasted-image')
        lowered = name.lower()
        extension = f".{lowered.split('.')[-1]}" if '.' in lowered else ''
        content_type = (getattr(image, 'content_type', '') or '').lower()
        if content_type not in ALLOWED_COMMENT_IMAGE_TYPES and extension not in ALLOWED_COMMENT_IMAGE_EXTENSIONS:
            return 'Only PNG, JPG, and WEBP images are allowed.'
        if image.size > MAX_COMMENT_IMAGE_SIZE:
            return 'Each pasted image must be 5 MB or smaller.'
    return None


def _create_mention_notifications(project, task, actor, comment):
    """Buat notifikasi mention berdasarkan @username di konten komentar."""
    content = comment.content or ''
    usernames = {m.group(2) for m in MENTION_PATTERN.finditer(content)}
    if not usernames:
        return

    mentioned_users = User.objects.filter(username__in=usernames, is_active=True).distinct()
    seen_recipient_ids = set()
    notifications = []

    for mentioned in mentioned_users:
        if mentioned.id == actor.id:
            continue
        if mentioned.id in seen_recipient_ids:
            continue
        if not project.can_user_view(mentioned):
            continue
        seen_recipient_ids.add(mentioned.id)
        notifications.append(UserNotification(
            recipient=mentioned,
            actor=actor,
            task=task,
            comment=comment,
            message=f"{actor.username} mentioned you in a comment on Task: {task.title}",
        ))

    if notifications:
        UserNotification.objects.bulk_create(notifications)


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    """Tandai notifikasi user login sebagai terbaca."""
    notification = get_object_or_404(
        UserNotification.objects.filter(recipient=request.user),
        id=notification_id,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
def notification_open(request, notification_id):
    """Buka notifikasi, tandai terbaca, lalu arahkan ke task/comment terkait."""
    notification = get_object_or_404(
        UserNotification.objects.select_related('task', 'comment'),
        id=notification_id,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    if notification.task_id:
        target = reverse('task_detail', args=[notification.task_id])
        if notification.comment_id:
            target = f"{target}#comment-{notification.comment_id}"
        return redirect(target)

    messages.info(request, 'Linked task is no longer available.')
    return redirect('notification_history')


@login_required
def notification_history(request):
    """Riwayat notifikasi mention (read + unread) dengan filter dan pagination."""
    active_filter = (request.GET.get('filter') or 'all').strip().lower()
    if active_filter not in {'all', 'unread', 'mentions'}:
        active_filter = 'all'

    notifications = UserNotification.objects.filter(recipient=request.user).select_related('actor', 'task', 'comment')
    if active_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif active_filter == 'mentions':
        notifications = notifications.filter(comment__isnull=False)

    paginator = Paginator(notifications.order_by('-created_at'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'arva/notification_history.html', {
        'page_obj': page_obj,
        'active_filter': active_filter,
    })


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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this task.', code='task_permission_forbidden')

    content = (request.POST.get('content') or '').strip()
    images = request.FILES.getlist('images')

    image_error = _validate_comment_images(images)
    if image_error:
        return JsonResponse({'success': False, 'error': image_error}, status=400)

    if not content and not images:
        return JsonResponse({'success': False, 'error': 'Comment or image is required.'}, status=400)

    if not content and images:
        content = 'Image attachment'

    comment = Comment.objects.create(task=task, user=request.user, content=content)
    for image in images:
        Attachment.objects.create(task=task, comment=comment, uploaded_by=request.user, file=image)
    _create_mention_notifications(project, task, request.user, comment)

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='comment_added', description=f"Comment added on task '{task.title}'"
    )
    html = render_to_string('arva/_comment_item.html', {'comment': comment}, request=request)
    return JsonResponse({'success': True, 'html': html})


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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(request, 'Access denied. Only project admins or task assignees can reply to comments.', code='comment_reply_forbidden')

    content = request.POST.get("content", "").strip()
    images = request.FILES.getlist('images')
    image_error = _validate_comment_images(images)
    if image_error:
        return JsonResponse({'success': False, 'error': image_error}, status=400)
    if not content and not images:
        return JsonResponse({'success': False, 'error': 'Reply or image is required.'}, status=400)
    if not content and images:
        content = 'Image attachment'

    new_comment = Comment.objects.create(
        task=task,
        user=request.user,
        parent=parent,
        content=content
    )
    for image in images:
        Attachment.objects.create(task=task, comment=new_comment, uploaded_by=request.user, file=image)
    _create_mention_notifications(project, task, request.user, new_comment)

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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)

    # Hanya pemilik komentar atau owner project yang boleh menghapus
    if not (comment.user_id == request.user.id or project.owner_id == request.user.id):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this project task.', code='task_permission_forbidden')

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='comment_added', description="deleted a comment"
    )

    comment.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def comment_edit(request, comment_id):
    """Edit komentar existing dengan validasi akses dan lock project."""
    comment = get_object_or_404(Comment, id=comment_id)
    task = comment.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error(request, action='add comments')

    role = get_role(request.user, project)
    if not (comment.user_id == request.user.id or project.owner_id == request.user.id or role == 'admin'):
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this project task.', code='task_permission_forbidden')

    content = (request.POST.get('content') or '').strip()
    if not content:
        return JsonResponse({'success': False, 'error': 'Comment content cannot be empty.'}, status=400)

    comment.content = content
    comment.save(update_fields=['content'])
    _create_mention_notifications(project, task, request.user, comment)

    ActivityLog.objects.create(
        user=request.user,
        project=task.project,
        task=task,
        action='comment_added',
        description="edited a comment"
    )

    rendered_content = render_to_string('arva/_comment_content.html', {'comment': comment}, request=request)
    return JsonResponse({
        'success': True,
        'comment_id': comment.id,
        'content': comment.content,
        'rendered_content': rendered_content,
    })


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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(
            request,
            'Access denied. Only project admins or task assignees can add comments.',
            code='comment_add_forbidden',
        )

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
def attachment_delete(request, attachment_id):
    """Hapus attachment pada task/comment dengan validasi akses."""
    attachment = get_object_or_404(Attachment, id=attachment_id)
    task = attachment.task
    project = get_user_project_or_404(request.user, task.project.id)
    if is_project_locked(project):
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)

    can_delete = bool(
        request.user.is_superuser or
        project.owner_id == request.user.id or
        (attachment.uploaded_by_id == request.user.id if attachment.uploaded_by_id else False) or
        (attachment.comment.user_id == request.user.id if attachment.comment_id else False) or
        role == 'admin'
    )
    if not can_delete:
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this project task.', code='task_permission_forbidden')

    try:
        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()
    except Exception:
        return JsonResponse({'success': False, 'error': 'Failed to delete attachment.'}, status=500)

    ActivityLog.objects.create(
        user=request.user, project=task.project, task=task,
        action='attachment_added', description=f"Attachment deleted on task '{task.title}'"
    )
    return JsonResponse({'success': True})


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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this task.', code='task_permission_forbidden')

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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this project task.', code='task_permission_forbidden')

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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)
    if role != 'admin' and request.user not in item.task.assignees.all():
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this task.', code='task_permission_forbidden')

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
        return closed_project_error(request, action='modify task comments/checklist/attachments')
    role = get_role(request.user, project)

    if role != 'admin' and request.user not in task.assignees.all():
        return permission_denied_response(request, 'Access denied. You do not have permission to perform this action on this project task.', code='task_permission_forbidden')

    ActivityLog.objects.create(
        user=request.user, project=item.task.project, task=item.task,
        action='checklist_toggled', description=f"deleted checklist item: '{item.content}'"
    )
    item.delete()

    return JsonResponse({"success": True})
