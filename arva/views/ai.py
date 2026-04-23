"""
Views AI (Artificial Intelligence)
====================================
Menangani semua fitur AI:
- AI Priority Queue: Analisis & prioritas task
- AI Chat Assistant: Asisten chat AI
- AI Developer V1: Pembuat kode otomatis (legacy)
- AI Developer V2: Pembuat kode dengan progress tracking
"""

import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.utils.timezone import now

from .helpers import (
    get_user_project_or_404, get_role, is_project_locked,
    closed_project_error, _get_priority_level,
)
from ..models import Task, AISettings, AIChatMessage, AIPriorityUsage
from ..ai_services import get_ai_service, get_ai_chat_service

logger = logging.getLogger(__name__)


def _check_ai_developer_enabled(request):
    """Cek apakah fitur AI Developer diaktifkan. Return None jika OK, response jika disabled."""
    ai_settings = AISettings.get_current()
    if not ai_settings.ai_developer_enabled:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'AI Developer is currently disabled by administrator.'
            }, status=403)
        messages.error(request, "AI Developer is currently disabled by administrator.")
        return redirect('project_list')
    return None


# ============================================================
# AI PRIORITY QUEUE
# ============================================================

@login_required
def ai_priority_queue(request):
    """Tampilkan antrean task yang diprioritaskan oleh AI.
    
    Menampilkan task yang sudah dianalisis sebelumnya (cached).
    TIDAK melakukan panggilan API saat halaman dimuat.
    Hanya bisa diakses jika fitur AI Priority diaktifkan oleh admin.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_priority_enabled:
        messages.error(request, "AI Priority Queue is currently disabled by administrator.")
        return redirect('project_list')
    
    try:
        # Ambil task user
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
        
        # Hanya tampilkan analisis yang sudah di-cache - TIDAK ada panggilan API saat load
        priorities = []
        today = now().date()
        for task in tasks:
            # Hanya sertakan task yang sudah pernah dianalisis
            if task.ai_priority_score is not None:
                # Hitung status due date
                days_until = None
                due_status = 'none'
                if task.due_date:
                    due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                    days_until = (due - today).days
                    if days_until < 0:
                        due_status = 'overdue'
                    elif days_until <= 2:
                        due_status = 'urgent'  # Merah
                    elif days_until <= 6:
                        due_status = 'warning'  # Oranye/Kuning
                    else:
                        due_status = 'safe'  # Hijau
                
                priorities.append({
                    'task_id': task.id,
                    'task_title': task.title,
                    'project_id': task.project.id,
                    'project_name': task.project.name,
                    'sub_project_name': task.sub_project.name if task.sub_project else None,
                    'priority_score': task.ai_priority_score,
                    'priority_level': _get_priority_level(task.ai_priority_score),
                    'complexity': task.ai_complexity,
                    'reasoning': task.ai_priority_reason,
                    'due_date': task.due_date.strftime('%d %b %Y') if task.due_date else None,
                    'due_status': due_status,
                    'days_until': days_until,
                    'task_list': task.task_list.name if task.task_list else None,
                    'has_analysis': task.ai_analyzed_at is not None,
                })
        
        # Urutkan berdasarkan skor prioritas
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
    """Refresh analisis AI untuk semua task (dipanggil via AJAX).
    
    Melakukan analisis ulang task yang ditugaskan ke user.
    Memanggil API AI untuk setiap task yang belum selesai.
    
    Dibatasi maksimal 2 kali per hari per user untuk menghemat token.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_priority_enabled:
        return JsonResponse({
            'success': False, 
            'error': 'AI Priority Queue is currently disabled by administrator.'
        })
    
    # Cek rate limiting (maksimal 2 kali per hari)
    can_use, remaining, message = AIPriorityUsage.can_use_priority_queue(request.user, max_usage=2)
    if not can_use:
        return JsonResponse({
            'success': False,
            'error': message,
            'limit_reached': True
        }, status=429)
    
    try:
        ai_service = get_ai_service()
        
        # Ambil task user
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            Q(assignees=request.user) | Q(project__owner=request.user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        )[:50]
        
        # Analisis semua task
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
        
        # Increment usage counter setelah berhasil
        usage = AIPriorityUsage.increment_usage(request.user)
        remaining = 2 - usage.usage_count
        
        return JsonResponse({
            'success': True,
            'analyzed_count': analyzed_count,
            'message': f'Successfully analyzed {analyzed_count} tasks',
            'remaining_usage': remaining,
            'usage_count': usage.usage_count
        })
        
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def ai_analyze_task(request, task_id):
    """Analisis satu task menggunakan AI dan kembalikan rekomendasi prioritas.
    
    Menyimpan hasil analisis ke field AI pada model Task.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_priority_enabled:
        return JsonResponse({
            'success': False, 
            'error': 'AI Priority Queue is currently disabled by administrator.'
        })
    
    task = get_object_or_404(Task, id=task_id)
    project = get_user_project_or_404(request.user, task.project.id)
    role = get_role(request.user, project)
    
    if role != 'admin' and request.user not in task.assignees.all():
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    try:
        ai_service = get_ai_service()
        analysis = ai_service.analyze_task(task)
        
        if 'error' in analysis:
            return JsonResponse({'success': False, 'error': analysis['error']}, status=500)
        
        # Simpan hasil analisis ke task
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
        
    except ValueError:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def ai_analyze_project(request, pk):
    """Analisis semua task dalam project menggunakan AI.
    
    Menyimpan hasil analisis ke setiap task dan mengembalikan
    daftar prioritas yang diurutkan berdasarkan skor.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_priority_enabled:
        return JsonResponse({
            'success': False, 
            'error': 'AI Priority Queue is currently disabled by administrator.'
        })
    
    project = get_user_project_or_404(request.user, pk)
    role = get_role(request.user, project)
    
    if role not in ['admin', 'member']:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    try:
        ai_service = get_ai_service()
        
        # Ambil semua task yang belum diarsip dan belum selesai
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
                # Simpan ke task
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
        
        # Urutkan berdasarkan skor prioritas
        results.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        return JsonResponse({
            'success': True,
            'analyzed_count': len(results),
            'priorities': results
        })
        
    except ValueError:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        }, status=503)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================
# AI CHAT ASSISTANT
# ============================================================

@login_required
def ai_chat(request):
    """Tampilkan antarmuka AI Chat dengan riwayat percakapan.
    
    Menampilkan 50 pesan terakhir dalam percakapan user.
    Hanya bisa diakses jika fitur AI Chat diaktifkan oleh admin.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_chat_enabled:
        messages.error(request, "AI Chat Assistant is currently disabled by administrator.")
        return redirect('project_list')
    
    # Ambil riwayat chat user (privat) - urutkan berdasarkan waktu
    chat_messages = AIChatMessage.objects.filter(
        user=request.user
    ).order_by('created_at')[:100]  # Increase limit to show more history
    
    return render(request, 'arva/ai_chat.html', {
        'chat_messages': chat_messages,
        'ai_settings': ai_settings,
    })


@login_required
@require_POST
def ai_chat_send(request):
    """Kirim pesan ke AI dan dapatkan respons.
    
    HANYA menyimpan respons AI ke database.
    Pesan user TIDAK disimpan untuk mencegah duplikasi setelah refresh.
    Pesan user ditampilkan real-time oleh JavaScript.
    """
    from ..models import AISettings
    ai_settings = AISettings.get_current()
    
    if not ai_settings.ai_chat_enabled:
        return JsonResponse({
            'success': False, 
            'error': 'AI Chat Assistant is currently disabled by administrator.'
        })
    
    message = request.POST.get('message', '').strip()
    
    if not message:
        return JsonResponse({'success': False, 'error': 'Message is empty'})
    
    try:
        # Ambil riwayat chat untuk konteks SEBELUM menyimpan pesan baru
        # agar pesan saat ini tidak terduplikasi di history
        chat_history = list(AIChatMessage.objects.filter(
            user=request.user
        ).order_by('-created_at')[:4].values('role', 'content'))
        chat_history.reverse()
        
        # Simpan pesan user ke database (untuk riwayat setelah refresh)
        user_msg = AIChatMessage.objects.create(
            user=request.user,
            role='user',
            content=message
        )
        
        # Dapatkan respons AI
        ai_service = get_ai_chat_service()
        ai_response = ai_service.chat(request.user, message, chat_history)
        
        # Simpan respons AI
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
                'created_at': user_msg.created_at.strftime('%d %b %Y %H:%M')
            },
            'ai_message': {
                'id': ai_msg.id,
                'content': ai_msg.content,
                'created_at': ai_msg.created_at.strftime('%d %b %Y %H:%M')
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False, 
            'error': f'AI service error: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def ai_chat_clear(request):
    """Hapus seluruh riwayat chat user saat ini."""
    AIChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({'success': True})


@login_required
def ai_chat_today_work(request):
    """Dapatkan rekomendasi AI untuk pekerjaan hari ini.
    
    Menyimpan pesan user dan rekomendasi sebagai pesan AI dalam riwayat chat.
    """
    try:
        # Simpan pesan user
        user_msg = AIChatMessage.objects.create(
            user=request.user,
            role='user',
            content='Apa yang harus saya kerjakan hari ini?'
        )
        
        ai_service = get_ai_chat_service()
        recommendation = ai_service.get_work_recommendation(request.user)
        
        # Simpan sebagai pesan AI
        ai_msg = AIChatMessage.objects.create(
            user=request.user,
            role='assistant',
            content=recommendation
        )
        
        return JsonResponse({
            'success': True,
            'user_message': {
                'id': user_msg.id,
                'content': user_msg.content,
                'created_at': user_msg.created_at.strftime('%d %b %Y %H:%M')
            },
            'message': {
                'id': ai_msg.id,
                'content': ai_msg.content,
                'created_at': ai_msg.created_at.strftime('%d %b %Y %H:%M')
            }
        })
        
    except ValueError:
        return JsonResponse({
            'success': False, 
            'error': 'AI service not configured. Please set GEMINI_API_KEY in settings.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================
# AI DEVELOPER V1 (LEGACY)
# ============================================================

@login_required
def ai_developer_dashboard(request):
    """Dashboard AI Developer - daftar semua feature request.
    
    Hanya staff/superuser yang bisa mengakses.
    Menampilkan statistik dan filter berdasarkan status/tipe.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("You don't have permission to access AI Developer.")
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    # Ambil parameter filter
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    
    requests_qs = AIFeatureRequest.objects.all().order_by('-created_at')
    
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)
    if type_filter:
        requests_qs = requests_qs.filter(request_type=type_filter)
    
    # Statistik
    stats = {
        'total': AIFeatureRequest.objects.count(),
        'pending': AIFeatureRequest.objects.filter(status='pending').count(),
        'in_progress': AIFeatureRequest.objects.filter(status__in=['analyzing', 'planning', 'generating', 'reviewing', 'applying', 'testing']).count(),
        'completed': AIFeatureRequest.objects.filter(status='completed').count(),
        'failed': AIFeatureRequest.objects.filter(status='failed').count(),
    }
    
    context = {
        'requests': requests_qs[:50],  # Batasi 50 terbaru
        'stats': stats,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'status_choices': AIFeatureRequest.STATUS_CHOICES,
        'type_choices': AIFeatureRequest.REQUEST_TYPE_CHOICES,
    }
    return render(request, 'arva/ai_developer_dashboard.html', context)


@login_required
def ai_developer_create_request(request):
    """Buat feature/bugfix request baru (V1).
    
    Menangani input form dan menjalankan AI processing jika diminta.
    Hanya staff/superuser yang bisa membuat request.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    from ..ai_developer import AIDeveloperService
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        request_type = request.POST.get('request_type', 'feature')
        priority = request.POST.get('priority', 'medium')
        target_files = request.POST.get('target_files', '').strip()
        
        if not title or not description:
            messages.error(request, 'Title and description are required.')
            return redirect('ai_developer_dashboard')
        
        # Buat request - gunakan nama field yang benar dari model
        related_files = [f.strip() for f in target_files.split(',') if f.strip()] if target_files else []
        
        feature_request = AIFeatureRequest.objects.create(
            title=title,
            description=description,
            request_type=request_type,
            priority=priority,
            related_files=related_files,
            created_by=request.user,
            status='pending'
        )
        
        messages.success(request, f'Request "{title}" created successfully!')
        
        # Opsional: mulai proses langsung
        if request.POST.get('start_immediately'):
            try:
                service = AIDeveloperService()
                service.process_request(feature_request)
                messages.success(request, 'AI processing started!')
            except Exception as e:
                messages.error(request, f'Failed to start AI processing: {str(e)}')
        
        return redirect('ai_developer_request_detail', request_id=feature_request.id)
    
    context = {
        'type_choices': AIFeatureRequest.REQUEST_TYPE_CHOICES,
        'priority_choices': AIFeatureRequest.PRIORITY_CHOICES,
    }
    return render(request, 'arva/ai_developer_create.html', context)


@login_required
def ai_developer_request_detail(request, request_id):
    """Lihat detail feature request beserta code changes.
    
    Hanya staff/superuser yang bisa mengakses.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest, AICodeChange
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    code_changes = feature_request.code_changes.all().order_by('file_path')
    
    # Calculate additions/deletions for each change
    changes_with_stats = []
    for change in code_changes:
        diff_text = change.get_diff() if change.get_diff() else ''
        adds = 0
        dels = 0
        for line in diff_text.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                adds += 1
            elif line.startswith('-') and not line.startswith('---'):
                dels += 1
        changes_with_stats.append({
            'change': change,
            'additions': adds,
            'deletions': dels,
        })
    
    context = {
        'req': feature_request,
        'code_changes': code_changes,
        'changes_with_stats': changes_with_stats,
    }
    return render(request, 'arva/ai_developer_request_detail.html', context)


@login_required
@require_POST
def ai_developer_start_processing(request, request_id):
    """Mulai AI processing untuk sebuah request (V1).
    
    Hanya bisa memproses request dengan status 'pending' atau 'failed'.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    from ..ai_developer import AIDeveloperService
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    # Cek apakah request bisa diproses
    if feature_request.status not in ['pending', 'failed']:
        messages.warning(request, 'Request sudah diproses atau sedang diproses.')
        return redirect('ai_developer_request_detail', request_id=request_id)
    
    try:
        service = AIDeveloperService()
        result = service.process_request(feature_request)
        
        if result.get('success'):
            messages.success(request, 'AI processing completed successfully!')
        else:
            messages.error(request, f"Processing failed: {result.get('error', 'Unknown error')}")
    
    except ValueError as e:
        messages.error(request, f'Configuration error: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('ai_developer_request_detail', request_id=request_id)


@login_required
@require_POST
def ai_developer_apply_changes(request, request_id):
    """Terapkan perubahan kode yang dihasilkan AI ke file.
    
    Hanya menerapkan perubahan dengan status 'pending'.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest, AICodeChange
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    # Ambil perubahan yang akan diterapkan
    change_ids = request.POST.getlist('change_ids')
    changes = feature_request.code_changes.filter(id__in=change_ids, status='pending')
    
    applied_count = 0
    failed_count = 0
    
    for change in changes:
        try:
            if change.apply_change():
                applied_count += 1
            else:
                failed_count += 1
        except Exception as e:
            change.status = 'failed'
            change.error_message = str(e)
            change.save()
            failed_count += 1
    
    if applied_count > 0:
        messages.success(request, f'{applied_count} changes applied successfully!')
    if failed_count > 0:
        messages.error(request, f'{failed_count} changes failed to apply.')
    
    return redirect('ai_developer_request_detail', request_id=request_id)


@login_required
@require_POST
def ai_developer_reject_changes(request, request_id):
    """Tolak perubahan kode yang dihasilkan AI."""
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest, AICodeChange
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    change_ids = request.POST.getlist('change_ids')
    changes = feature_request.code_changes.filter(id__in=change_ids)
    
    for change in changes:
        change.status = 'rejected'
        change.save()
    
    messages.success(request, f'{len(change_ids)} changes rejected.')
    return redirect('ai_developer_request_detail', request_id=request_id)


@login_required
@require_POST
def ai_developer_cancel_request(request, request_id):
    """Batalkan feature request.
    
    Hanya bisa membatalkan request yang belum selesai/gagal/dibatalkan.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    if feature_request.status in ['completed', 'failed', 'cancelled']:
        messages.error(request, 'Cannot cancel a completed/failed/cancelled request.')
    else:
        feature_request.status = 'cancelled'
        feature_request.save()
        messages.success(request, 'Request cancelled.')
    
    return redirect('ai_developer_dashboard')


@login_required
def ai_developer_view_diff(request, change_id):
    """Lihat diff untuk sebuah code change.
    
    Menampilkan perbandingan kode lama dan baru.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AICodeChange
    
    change = get_object_or_404(AICodeChange, id=change_id)
    
    # Calculate additions and deletions from diff
    diff_text = change.get_diff() if change.get_diff() else ''
    diff_lines = diff_text.split('\n') if diff_text else []
    
    additions = 0
    deletions = 0
    for line in diff_lines:
        if line.startswith('+') and not line.startswith('+++'):
            additions += 1
        elif line.startswith('-') and not line.startswith('---'):
            deletions += 1
    
    context = {
        'change': change,
        'diff_lines': diff_lines,
        'additions': additions,
        'deletions': deletions,
    }
    return render(request, 'arva/ai_developer_diff.html', context)


@login_required
def ai_developer_codebase_analysis(request):
    """Analisis struktur codebase menggunakan AI.
    
    Menampilkan pohon folder, model, views, URLs, template, dan backup files.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..ai_code_analyzer import CodebaseAnalyzer
    from pathlib import Path
    from django.conf import settings
    
    analyzer = CodebaseAnalyzer()
    analysis_result = analyzer.analyze_full_codebase()
    
    # Fungsi bantu untuk konversi FolderInfo ke dict
    def folder_to_dict(folder):
        if not folder:
            return None
        return {
            'name': folder.name,
            'path': folder.path,
            'is_folder': folder.is_folder,
            'file_count': folder.file_count,
            'file_types': dict(folder.file_types),
            'children': [folder_to_dict(c) for c in folder.children] if folder.children else []
        }
    
    # Konversi struktur folder ke JSON string untuk template
    folder_structure_json = json.dumps(folder_to_dict(analysis_result.folder_structure))
    
    # Konversi dataclass ke dict untuk template
    analysis = {
        'models': [{'name': m.name, 'fields': m.fields, 'methods': m.methods, 'file_path': m.file_path, 'line_number': m.line_number} for m in analysis_result.models],
        'views': [{'name': v.name, 'view_type': v.view_type, 'methods': v.methods, 'file_path': v.file_path, 'line_number': v.line_number} for v in analysis_result.views],
        'urls': [{'pattern': u.pattern, 'view_name': u.view_name, 'name': u.name} for u in analysis_result.urls],
        'templates': [{'name': t.name, 'extends': t.extends, 'file_path': t.file_path} for t in analysis_result.templates],
        'static_files': analysis_result.static_files,
        'apps': analysis_result.apps,
        'folder_structure': folder_structure_json,
    }
    
    # Get backup files from .ai_backups folder
    backup_files = []
    backup_dir = Path(settings.BASE_DIR) / '.ai_backups'
    if backup_dir.exists():
        for backup_file in sorted(backup_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if backup_file.is_file() and backup_file.suffix == '.bak':
                stat = backup_file.stat()
                # Parse filename to get original file path and timestamp
                # Format: {filepath}.{timestamp}.bak
                filename = backup_file.name
                parts = filename.rsplit('.', 2)  # Split from right to get .timestamp.bak
                if len(parts) >= 3:
                    original_file = parts[0].replace('_', '/')
                    timestamp_str = parts[1]
                    try:
                        from datetime import datetime
                        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    except:
                        timestamp = None
                else:
                    original_file = filename
                    timestamp = None
                
                backup_files.append({
                    'filename': filename,
                    'original_file': original_file,
                    'size': stat.st_size,
                    'created_at': timestamp,
                    'path': str(backup_file.relative_to(settings.BASE_DIR)),
                })
    
    context = {
        'analysis': analysis,
        'models_count': len(analysis.get('models', [])),
        'views_count': len(analysis.get('views', [])),
        'urls_count': len(analysis.get('urls', [])),
        'templates_count': len(analysis.get('templates', [])),
        'backup_files': backup_files[:20],  # Show last 20 backups
        'backup_count': len(backup_files),
    }
    return render(request, 'arva/ai_developer_analysis.html', context)


@login_required
def ai_developer_api_status(request):
    """API endpoint untuk cek status AI Developer.
    
    Mengembalikan ketersediaan layanan dan nama model yang digunakan.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..ai_developer import AIDeveloperService
    
    service = AIDeveloperService()
    
    return JsonResponse({
        'available': service.client is not None,
        'model': service.model_name if service.client else None,
    })


# ============================================================
# AI DEVELOPER V2 - SISTEM BARU DENGAN PROGRESS TRACKING
# ============================================================

@login_required
def ai_developer_create_v2(request):
    """Buat request AI Developer dengan template V2.
    
    Menggunakan sistem baru dengan progress tracking.
    Validasi input: judul minimal 5 karakter, deskripsi minimal 20 karakter.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        request_type = request.POST.get('request_type', 'feature')
        priority = request.POST.get('priority', 'medium')
        target_files = request.POST.get('target_files', '').strip()
        start_immediately = request.POST.get('start_immediately') == '1'
        
        # Validasi input
        if len(title) < 5:
            messages.error(request, 'Judul terlalu pendek (minimal 5 karakter).')
            return redirect('ai_developer_create_v2')
        
        if len(description) < 20:
            messages.error(request, 'Deskripsi terlalu pendek (minimal 20 karakter).')
            return redirect('ai_developer_create_v2')
        
        # Parse target files
        related_files = []
        if target_files:
            related_files = [f.strip() for f in target_files.split(',') if f.strip()]
        
        # Buat request baru
        feature_request = AIFeatureRequest.objects.create(
            title=title,
            description=description,
            request_type=request_type,
            priority=priority,
            related_files=related_files,
            created_by=request.user,
            status='pending',
            current_step=0,
            total_steps=7,
            progress_percent=0,
        )
        
        messages.success(request, 'Request berhasil dibuat!')
        
        # Mulai proses jika diminta
        if start_immediately:
            return redirect('ai_developer_progress', request_id=feature_request.id)
        else:
            return redirect('ai_developer_dashboard')
    
    # GET request - tampilkan form
    return render(request, 'arva/ai_developer_create_v2.html')


@login_required
def ai_developer_progress(request, request_id):
    """Lihat progress real-time dari AI Developer.
    
    Menampilkan status, progress bar, dan detail setiap langkah.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    context = {
        'request': feature_request,
    }
    return render(request, 'arva/ai_developer_progress.html', context)


@login_required
def ai_developer_api_progress(request, request_id):
    """API endpoint untuk mendapatkan progress request dalam format JSON.
    
    Digunakan untuk polling progress dari frontend (AJAX).
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    return JsonResponse({
        'id': feature_request.id,
        'status': feature_request.status,
        'status_display': feature_request.get_status_display(),
        'status_color': feature_request.status_color,
        'current_step': feature_request.current_step,
        'total_steps': feature_request.total_steps,
        'step_description': feature_request.step_description,
        'progress': feature_request.progress,
        'progress_percent': feature_request.progress_percent,
        'duration_formatted': feature_request.duration_formatted,
        'related_files_count': len(feature_request.related_files) if feature_request.related_files else 0,
        'is_cancelled': feature_request.is_cancelled,
    })


@login_required
@require_POST
def ai_developer_start_v2(request, request_id):
    """Mulai proses AI Developer dengan sistem V2.
    
    Menjalankan proses di background thread agar tidak blocking.
    Setelah memulai, redirect ke halaman progress.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    from ..ai_developer_v2 import AIDeveloperServiceV2
    import threading
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    # Cek apakah request bisa diproses
    if feature_request.status not in ['pending', 'failed']:
        messages.warning(request, 'Request sudah diproses atau sedang diproses.')
        return redirect('ai_developer_progress', request_id=request_id)
    
    # Fungsi untuk menjalankan proses di background
    def run_processing():
        try:
            service = AIDeveloperServiceV2()
            service.process_request(feature_request)
        except Exception as e:
            logger.error(f"[AI Developer V2] Error dalam background processing: {str(e)}")
            feature_request.status = 'failed'
            feature_request.last_error = str(e)
            feature_request.error_count += 1
            feature_request.save()
    
    # Jalankan di thread terpisah agar tidak blocking
    processing_thread = threading.Thread(target=run_processing)
    processing_thread.daemon = True
    processing_thread.start()
    
    messages.info(request, 'Proses AI Developer dimulai. Anda dapat melihat progress di halaman ini.')
    return redirect('ai_developer_progress', request_id=request_id)


@login_required
@require_POST
def ai_developer_api_cancel(request, request_id):
    """API endpoint untuk membatalkan request yang sedang diproses.
    
    Hanya bisa membatalkan request yang belum selesai/gagal/dibatalkan.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    
    disabled = _check_ai_developer_enabled(request)
    if disabled:
        return disabled
    
    from ..models import AIFeatureRequest
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    # Cek apakah bisa dibatalkan
    if feature_request.status in ['completed', 'failed', 'cancelled']:
        return JsonResponse({
            'success': False,
            'error': 'Request sudah selesai, gagal, atau sudah dibatalkan.'
        })
    
    # Batalkan request
    feature_request.cancel(reason='Dibatalkan oleh user')
    
    return JsonResponse({
        'success': True,
        'message': 'Request berhasil dibatalkan.'
    })


@login_required
def ai_developer_retry_v2(request, request_id):
    """Coba ulang request yang gagal dengan sistem V2.
    
    Mereset status dan menghapus code changes lama,
    lalu redirect ke halaman start V2.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    from ..models import AIFeatureRequest
    
    feature_request = get_object_or_404(AIFeatureRequest, id=request_id)
    
    # Reset status
    feature_request.status = 'pending'
    feature_request.current_step = 0
    feature_request.progress_percent = 0
    feature_request.step_description = ''
    feature_request.error_count = 0
    feature_request.last_error = ''
    feature_request.save()
    
    # Hapus code changes yang lama
    feature_request.code_changes.all().delete()
    
    messages.info(request, 'Request direset. Memulai ulang proses...')
    return redirect('ai_developer_start_v2', request_id=request_id)
