"""
Views Manajemen User & Pengaturan
==================================
Menangani pengaturan user, manajemen user (CRUD), pengaturan website,
dan laporan performa user.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Q, Max

from .helpers import get_user_project_or_404
from ..models import (
    Project, ProjectMember, Task, Comment, ActivityLog,
    UserProfile, WebsiteSettings, AISettings
)
from ..forms import (
    CreateUserInlineForm, UserEditForm, AdminPasswordResetForm,
    AvatarUploadForm, WebsiteSettingsForm
)

User = get_user_model()


# ============================================================
# PENGATURAN USER
# ============================================================

@login_required
def user_settings(request):
    """Halaman pengaturan user dengan menu navigasi.
    
    Menangani:
    - Edit profile (username, email, avatar)
    - Pengaturan website (hanya superuser di layout classic)
    """
    from ..forms import UserEditForm, UserProfileEditForm, AvatarUploadForm
    
    user_obj = request.user
    profile = user_obj.userprofile
    layout_preference = profile.layout_preference
    is_classic = layout_preference == UserProfile.LAYOUT_CLASSIC
    settings_obj = WebsiteSettings.objects.first()
    website_form = None
    user_form = None
    avatar_form = None
    
    # Pilih form yang sesuai: superuser bisa edit is_active/is_staff, user biasa tidak
    UserFormClass = UserEditForm if request.user.is_superuser else UserProfileEditForm
    
    # Tangani edit profile
    if request.method == "POST" and request.POST.get("settings_scope") == "profile":
        user_form = UserFormClass(request.POST, instance=user_obj)
        avatar_form = AvatarUploadForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and avatar_form.is_valid():
            user_form.save()
            
            obj = avatar_form.save(commit=False)
            icon = avatar_form.cleaned_data.get("avatar_icon")
            uploaded_avatar = avatar_form.cleaned_data.get("avatar")
            
            if uploaded_avatar:
                # User upload file - hapus pilihan ikon
                obj.avatar_icon = ""
            elif icon:
                # User pilih ikon - hapus avatar yang diupload
                if obj.avatar:
                    obj.avatar.delete(save=False)
                obj.avatar = None
                obj.avatar_icon = icon
            else:
                # Tidak ada yang dipilih - hapus keduanya
                if obj.avatar:
                    obj.avatar.delete(save=False)
                obj.avatar = None
                obj.avatar_icon = ""
            
            obj.save()
            messages.success(request, "Profile berhasil diperbarui.")
            return redirect("user_settings")
        else:
            messages.error(request, "Error menyimpan profile.")
    else:
        user_form = UserFormClass(instance=user_obj)
        avatar_form = AvatarUploadForm(instance=profile)

    # Pengaturan website (hanya superuser di layout classic)
    if is_classic and request.user.is_superuser:
        if request.method == "POST" and request.POST.get("settings_scope") == "website":
            website_form = WebsiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
            if website_form.is_valid():
                website_form.save()
                messages.success(request, "Pengaturan website berhasil disimpan.")
                return redirect("user_settings")
            messages.error(request, "Error menyimpan pengaturan website.")
        else:
            website_form = WebsiteSettingsForm(instance=settings_obj)

    return render(request, "arva/user_settings.html", {
        "layout_preference": layout_preference,
        "theme_preference": profile.theme_preference,
        "layout_is_classic": is_classic,
        "website_form": website_form,
        "settings": settings_obj,
        "profile": profile,
        "user_form": user_form,
        "avatar_form": avatar_form,
    })


@login_required
def website_settings(request):
    """Halaman pengaturan website (hanya superuser, layout sidebar).
    
    Di layout classic, pengaturan website tergabung di halaman user_settings.
    """
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
def update_user_theme(request):
    """Update preferensi tema user (inherit, light, dark, auto).
    
    Dipanggil via AJAX POST.
    """
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
    """Update preferensi layout user (sidebar atau classic).
    
    Dipanggil via AJAX POST.
    """
    layout = request.POST.get("layout")

    if layout not in ["sidebar", "classic"]:
        return JsonResponse({"success": False, "error": "Invalid layout"}, status=400)

    profile = request.user.userprofile
    profile.layout_preference = layout
    profile.save(update_fields=["layout_preference"])

    return JsonResponse({"success": True, "layout": layout})


# ============================================================
# LAPORAN PERFORMA USER
# ============================================================

@login_required
def user_performance(request):
    """Laporan performa task dengan filter dan grafik.
    
    Menampilkan statistik: completion rate, on-time rate, overdue rate,
    distribusi status/prioritas, tren mingguan, dan performa per user.
    Hanya bisa diakses oleh staff.
    """
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to view this page.")
        return redirect("project_list")
    
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    from datetime import timedelta, datetime
    import json
    
    # Ambil parameter filter
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    selected_user_id = request.GET.get('user')
    selected_project_id = request.GET.get('project')
    selected_priority = request.GET.get('priority')
    
    # Konversi ke int untuk perbandingan
    selected_user = int(selected_user_id) if selected_user_id and selected_user_id.isdigit() else None
    selected_project = int(selected_project_id) if selected_project_id and selected_project_id.isdigit() else None
    
    # Rentang tanggal default (30 hari terakhir)
    # Gunakan localdate untuk mengikuti timezone lokal
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=30)
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Queryset dasar - semua task yang tidak diarsip
    tasks = Task.objects.filter(is_archived=False)
    
    # Terapkan filter project, user, priority (tetap diterapkan)
    if selected_user:
        tasks = tasks.filter(assignees__id=selected_user)
    if selected_project:
        tasks = tasks.filter(project__id=selected_project)
    if selected_priority:
        tasks = tasks.filter(priority=selected_priority)
    
    # Simpan nilai string asli untuk template
    selected_user_str = selected_user_id if selected_user_id else ""
    selected_project_str = selected_project_id if selected_project_id else ""
    
    # Query semua task dengan filter yang diterapkan (tanpa filter tanggal untuk total)
    all_filtered_tasks = tasks
    
    # Task selesai = task yang berada di list dengan nama "Done" (case insensitive)
    # Ini konsisten dengan perhitungan progress di model Project dan SubProject
    completed_tasks_queryset = all_filtered_tasks.filter(task_list__name__iexact='Done')
    
    # Statistik ringkasan - total task (selalu semua task yang difilter, tanpa filter tanggal)
    total_tasks = all_filtered_tasks.count()
    completed_tasks = completed_tasks_queryset.count()
    completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
    
    # On-time delivery rate - task selesai sebelum atau tepat pada due_date
    # Task selesai = berada di list "Done"
    completed_with_due = completed_tasks_queryset.filter(due_date__isnull=False)
    on_time_count = 0
    for task in completed_with_due:
        # Cari log saat task dipindahkan ke list "Done"
        # Deskripsi log: "Task 'X' moved to list 'Done'"
        completion_log = ActivityLog.objects.filter(
            task=task,
            action='task_moved',
            description__icontains='Done'
        ).order_by('-created_at').first()
        
        if completion_log:
            completed_date = completion_log.created_at.date()
        else:
            # Fallback ke updated_at jika tidak ada log spesifik ke Done
            completed_date = task.updated_at.date()
        
        if completed_date <= task.due_date:
            on_time_count += 1
    
    # Jika tidak ada task dengan due date yang selesai, tampilkan 100% (default)
    if completed_with_due.count() == 0:
        ontime_rate = 100
    else:
        ontime_rate = round((on_time_count / completed_with_due.count() * 100), 1)
    
    # Overdue rate - task melewati due date tapi belum selesai
    # Task belum selesai = tidak berada di list "Done"
    overdue_count = all_filtered_tasks.filter(
        due_date__lt=timezone.localdate(),
        due_date__isnull=False,
    ).exclude(task_list__name__iexact='Done').count()
    overdue_rate = round((overdue_count / total_tasks * 100), 1) if total_tasks > 0 else 0
    
    # Waktu respons rata-rata (placeholder - membutuhkan data activity log)
    avg_response_time = 24
    
    # Data performa user untuk grafik
    # Ambil semua user yang memiliki task dalam filter yang diterapkan
    users_with_tasks = User.objects.filter(
        is_active=True,
        assigned_tasks__in=all_filtered_tasks
    ).distinct().order_by('username')
    
    # Hitung task yang tidak diassign (unassigned)
    unassigned_tasks_count = all_filtered_tasks.filter(assignees__isnull=True).count()
    
    user_labels = []
    user_completion_rates = []
    user_ontime_rates = []
    user_task_counts = []
    user_overdue_counts = []  # Tambahan: jumlah task overdue per user
    
    for user in users_with_tasks:
        # Ambil task user dalam set task yang sudah difilter
        user_tasks = all_filtered_tasks.filter(assignees=user)
        user_total = user_tasks.count()
        
        # Hanya sertakan user yang punya task (seharusnya selalu true karena sudah difilter)
        if user_total > 0:
            # Task selesai = berada di list "Done"
            user_completed = user_tasks.filter(task_list__name__iexact='Done').count()
            user_completion = round((user_completed / user_total * 100), 1)
            
            # Task overdue per user (belum selesai tapi melewati due date)
            user_overdue = user_tasks.filter(
                due_date__lt=timezone.localdate(),
                due_date__isnull=False,
            ).exclude(task_list__name__iexact='Done').count()
            
            # On-time rate untuk user
            # Hanya hitung jika user memiliki task selesai dengan due date
            user_completed_with_due = user_tasks.filter(task_list__name__iexact='Done', due_date__isnull=False)
            user_completed_with_due_count = user_completed_with_due.count()
            
            if user_completed_with_due_count > 0:
                user_on_time = 0
                for task in user_completed_with_due:
                    # Cari log saat task dipindahkan ke list "Done"
                    completion_log = ActivityLog.objects.filter(
                        task=task,
                        action='task_moved',
                        description__icontains="Done'"
                    ).order_by('-created_at').first()
                    
                    if completion_log:
                        completed_date = completion_log.created_at.date()
                    else:
                        completed_date = task.updated_at.date()
                    
                    if completed_date <= task.due_date:
                        user_on_time += 1
                user_ontime = round((user_on_time / user_completed_with_due_count * 100), 1)
            else:
                # Jika tidak ada task selesai dengan due date, tampilkan 0
                user_ontime = 0
            
            user_labels.append(user.username)
            user_completion_rates.append(user_completion)
            user_ontime_rates.append(user_ontime)
            user_task_counts.append(user_total)
            user_overdue_counts.append(user_overdue)
    
    # Jika ada task unassigned, tambahkan ke data grafik
    if unassigned_tasks_count > 0:
        user_labels.append('Unassigned')
        user_completion_rates.append(0)  # Unassigned tidak punya completion rate
        user_ontime_rates.append(0)      # Unassigned tidak punya on-time rate
        user_task_counts.append(unassigned_tasks_count)
        user_overdue_counts.append(0)    # Unassigned tidak dihitung overdue
    
    # Distribusi status - dari semua task yang difilter (tanpa filter tanggal)
    # Untuk kanban board, status ditentukan oleh task_list (list name), bukan field status
    # Task selesai = berada di list "Done"
    # Task in_progress = berada di list "In Progress"
    # Task pending = berada di list "To Do" atau list lain selain Done/In Progress
    # Task infeasible = field status 'infeasible' (khusus project terstruktur)
    status_counts = [
        all_filtered_tasks.filter(task_list__name__iexact='Done').count(),  # Done
        all_filtered_tasks.filter(task_list__name__iexact='In Progress').count(),  # In Progress
        all_filtered_tasks.filter(status='-').exclude(
            Q(task_list__name__iexact='Done') | Q(task_list__name__iexact='In Progress')
        ).count(),  # Pending
        all_filtered_tasks.filter(status='infeasible').count()  # Infeasible
    ]
    
    # Distribusi prioritas - dari semua task yang difilter (tanpa filter tanggal)
    priority_counts = [
        all_filtered_tasks.filter(priority='p0').count(),
        all_filtered_tasks.filter(priority='p1').count(),
        all_filtered_tasks.filter(priority='p2').count(),
        all_filtered_tasks.filter(priority='p3').count()
    ]
    
    # Tren mingguan - task yang selesai per hari
    # Gunakan kombinasi: task dengan status='done' yang updated_at-nya dalam hari tersebut
    # atau yang terakhir dipindahkan ke Done dalam hari tersebut (dari ActivityLog)
    week_labels = []
    weekly_completed = []
    
    for i in range(7):
        day = end_date - timedelta(days=6-i)
        week_labels.append(day.strftime('%a'))
        
        # Hitung task selesai pada hari tersebut
        # Task dianggap selesai pada hari X jika:
        # 1. Ada log task_moved ke list Done pada hari X, ATAU
        # 2. Task updated_at pada hari X dan berada di list Done
        
        # Cari task yang selesai berdasarkan ActivityLog
        day_completed_ids = set()
        
        # Ambil log task_moved ke Done pada hari tersebut
        # Deskripsi log: "Task 'X' moved to list 'Done'"
        # Gunakan range waktu dari awal hari sampai akhir hari untuk menghindari masalah timezone
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        day_logs_all = ActivityLog.objects.filter(
            action='task_moved',
            created_at__gte=day_start,
            created_at__lte=day_end
        )
        day_logs_with_done = day_logs_all.filter(description__icontains='Done')
        
        day_logs = day_logs_with_done.select_related('task').order_by('task__id', '-created_at')
        
        # Filter tambahan pada log
        if selected_user:
            day_logs = day_logs.filter(task__assignees__id=selected_user)
        if selected_project:
            day_logs = day_logs.filter(task__project__id=selected_project)
        if selected_priority:
            day_logs = day_logs.filter(task__priority=selected_priority)
        
        # Untuk setiap task, ambil log terakhir pada hari tersebut
        # Jika task saat ini berada di list "Done", anggap selesai pada hari tersebut
        seen_tasks = set()
        for log in day_logs:
            if log.task_id not in seen_tasks:
                seen_tasks.add(log.task_id)
                # Cek apakah task saat ini berada di list Done
                if log.task and log.task.task_list and log.task.task_list.name.lower() == 'done' and not log.task.is_archived:
                    day_completed_ids.add(log.task_id)
        
        # Juga cek task yang updated_at-nya pada hari tersebut dan berada di list Done
        # (untuk task yang mungkin tidak memiliki log yang jelas)
        # Gunakan range waktu untuk menghindari masalah timezone
        tasks_by_update = all_filtered_tasks.filter(
            task_list__name__iexact='Done',
            updated_at__gte=day_start,
            updated_at__lte=day_end
        ).values_list('id', flat=True)
        
        day_completed_ids.update(tasks_by_update)
        
        weekly_completed.append(len(day_completed_ids))
    
    # Opsi filter
    all_users = User.objects.filter(is_active=True)
    all_projects = Project.objects.filter(is_closed=False)
    

    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'selected_user': selected_user_str,
        'selected_project': selected_project_str,
        'selected_priority': selected_priority if selected_priority else "",
        'all_users': all_users,
        'all_projects': all_projects,
        'total_tasks': total_tasks,
        'completion_rate': completion_rate,
        'ontime_rate': ontime_rate,
        'overdue_rate': overdue_rate,
        'avg_response_time': avg_response_time,
        'user_labels': json.dumps(user_labels),
        'user_completion_rates': json.dumps(user_completion_rates),
        'user_ontime_rates': json.dumps(user_ontime_rates),
        'user_task_counts': json.dumps(user_task_counts),
        'user_overdue_counts': json.dumps(user_overdue_counts),
        'status_counts': json.dumps(status_counts),
        'priority_counts': json.dumps(priority_counts),
        'week_labels': json.dumps(week_labels),
        'weekly_completed': json.dumps(weekly_completed),
    }
    
    return render(request, "arva/user_performance_report.html", context)


# ============================================================
# PENGATURAN AI
# ============================================================

@login_required
def ai_settings(request):
    """Halaman pengaturan AI - hanya untuk superuser.
    
    Menangani konfigurasi:
    - Provider AI (OpenClaw, Ollama, dll)
    - Model AI Assistant dan AI Developer
    - Parameter AI (temperature, max_tokens)
    - Toggle fitur AI Priority dan AI Chat
    - Prompt kustom untuk analisis dan chat
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to manage AI settings.")
        return redirect("user_settings")
    
    ai_settings_obj = AISettings.get_current()
    
    if request.method == "POST":
        # Ambil data form
        provider = request.POST.get("provider", AISettings.PROVIDER_OPENCLAW)
        base_url_preset = request.POST.get("base_url_preset", "ollama")
        base_url = request.POST.get("base_url", "")
        api_key = request.POST.get("api_key", "").strip()
        
        # Model AI Assistant
        assistant_model = request.POST.get("assistant_model", "qwen2.5:7b")
        custom_assistant_model = request.POST.get("custom_assistant_model", "").strip()
        
        # Model AI Developer
        developer_model = request.POST.get("developer_model", "codellama:13b")
        custom_developer_model = request.POST.get("custom_developer_model", "").strip()
        
        # Parameter AI
        temperature = request.POST.get("temperature", "0.7")
        max_tokens = request.POST.get("max_tokens", "2048")
        ai_priority_enabled = request.POST.get("ai_priority_enabled") == "on"
        ai_chat_enabled = request.POST.get("ai_chat_enabled") == "on"
        ai_developer_enabled = request.POST.get("ai_developer_enabled") == "on"
        priority_analysis_prompt = request.POST.get("priority_analysis_prompt", "").strip()
        chat_system_prompt = request.POST.get("chat_system_prompt", "").strip()
        
        # Tangani base URL preset
        if base_url_preset == "ollama":
            base_url = "http://localhost:11434/v1"
        elif base_url_preset == "openclaw":
            base_url = "http://localhost:8080/v1"
        elif not base_url:
            base_url = "http://localhost:11434/v1"
        
        # Tangani model kustom
        if assistant_model == "custom" and custom_assistant_model:
            pass  # Biarkan kustom, akan ditangani oleh get_assistant_model()
        if developer_model == "custom" and custom_developer_model:
            pass  # Biarkan kustom, akan ditangani oleh get_developer_model()
        
        # Update pengaturan
        ai_settings_obj.provider = provider
        ai_settings_obj.base_url = base_url
        if api_key:
            ai_settings_obj.api_key = api_key
        
        # Simpan pilihan model
        ai_settings_obj.assistant_model = assistant_model
        ai_settings_obj.custom_assistant_model = custom_assistant_model
        ai_settings_obj.developer_model = developer_model
        ai_settings_obj.custom_developer_model = custom_developer_model
        
        # Simpan parameter
        ai_settings_obj.temperature = float(temperature) if temperature else 0.7
        ai_settings_obj.max_tokens = int(max_tokens) if max_tokens else 2048
        ai_settings_obj.ai_priority_enabled = ai_priority_enabled
        ai_settings_obj.ai_chat_enabled = ai_chat_enabled
        ai_settings_obj.ai_developer_enabled = ai_developer_enabled
        ai_settings_obj.priority_analysis_prompt = priority_analysis_prompt
        ai_settings_obj.chat_system_prompt = chat_system_prompt
        ai_settings_obj.updated_by = request.user
        
        ai_settings_obj.save()
        
        messages.success(request, f"AI settings saved! Assistant: {assistant_model}, Developer: {developer_model}")
        return redirect("ai_settings")
    
    return render(request, "arva/ai_settings.html", {
        "ai_settings": ai_settings_obj,
        "gemini_models": AISettings.GEMINI_MODELS,
        "openai_models": AISettings.OPENAI_MODELS,
        "openclaw_models": AISettings.OPENCLAW_MODELS,
        "assistant_models": AISettings.ASSISTANT_MODELS,
        "developer_models": AISettings.DEVELOPER_MODELS,
        "recommended_models": AISettings.RECOMMENDED_MODELS,
    })


# ============================================================
# MANAJEMEN USER (ADMIN)
# ============================================================

@login_required
def user_list(request):
    """Daftar semua user dengan fitur pencarian.
    
    Hanya bisa diakses oleh superuser.
    Menampilkan informasi aktivitas terakhir setiap user.
    """
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
    # Hitung aktivitas terakhir dari beberapa sumber
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
    """Buat user baru melalui sistem (bukan registrasi mandiri).
    
    Hanya superuser yang bisa membuat user. Validasi via CreateUserInlineForm.
    """
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
    """Edit profil user (informasi dan avatar).
    
    Superuser bisa mengedit semua user.
    User biasa hanya bisa mengedit profile sendiri.
    """
    user_obj = get_object_or_404(User, id=user_id)
    
    # Cek permission: superuser bisa edit semua, user biasa hanya bisa edit sendiri
    if not request.user.is_superuser and request.user.id != user_obj.id:
        messages.error(request, "You do not have permission.")
        return redirect('project_list')
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
            # Redirect superuser ke user_list, user biasa ke project_list
            if request.user.is_superuser:
                return redirect('user_list')
            else:
                return redirect('project_list')
    else:
        user_form = UserEditForm(instance=user_obj)
        avatar_form = AvatarUploadForm(instance=profile)

    # Informasi tambahan untuk template
    memberships = ProjectMember.objects.filter(user=user_obj).select_related('project')
    last_comment = Comment.objects.filter(user=user_obj).aggregate(Max('created_at'))['created_at__max']
    last_task_activity = ActivityLog.objects.filter(user=user_obj).aggregate(Max('created_at'))['created_at__max']
    valid_times = list(filter(None, [last_comment, last_task_activity, user_obj.last_login]))
    last_seen = max(valid_times) if valid_times else None

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
    """Toggle status aktif user (aktifkan/nonaktifkan).
    
    Hanya superuser yang bisa mengubah status aktif user.
    """
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
    """Reset password user oleh admin.
    
    Hanya superuser yang bisa mereset password user lain.
    """
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
    """Hapus user secara permanen (hard delete).
    
    Hanya superuser yang bisa menghapus user.
    Tidak bisa menghapus diri sendiri atau superuser lain.
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    user_obj = get_object_or_404(User, id=user_id)

    # Validasi: tidak boleh hapus diri sendiri
    if user_obj == request.user:
        return JsonResponse({'success': False, 'error': 'Tidak boleh menghapus diri sendiri.'}, status=400)

    # Validasi: tidak boleh hapus superuser lain
    if user_obj.is_superuser:
        return JsonResponse({'success': False, 'error': 'Tidak boleh menghapus superuser lain.'}, status=400)

    user_obj.delete()

    return JsonResponse({'success': True})


# ============================================================
# MANAJEMEN MEMBER PROJECT
# ============================================================

@login_required
@require_POST
def project_member_update_role(request, pm_id):
    """Update role member project.
    
    Catatan: Sistem role sudah disederhanakan, semua member dijadikan ROLE_MEMBER.
    Hanya superuser yang bisa mengakses endpoint ini.
    """
    pm = get_object_or_404(ProjectMember, id=pm_id)
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    # Update role sudah deprecated; pertahankan membership sebagai sharing biasa
    if pm.role != ProjectMember.ROLE_MEMBER:
        pm.role = ProjectMember.ROLE_MEMBER
        pm.save(update_fields=['role'])

    return JsonResponse({'success': True})


@login_required
@require_POST
def project_member_remove(request, pm_id):
    """Hapus member dari project.
    
    Hanya superuser yang bisa menghapus member project.
    """
    pm = get_object_or_404(ProjectMember, id=pm_id)

    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    pm.delete()

    return JsonResponse({'success': True})
