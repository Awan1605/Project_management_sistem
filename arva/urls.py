"""
URL Configuration Arviga Project Manager
==========================================
Mendefinisikan seluruh URL routing aplikasi.

Kelompok URL:
- Auth: Login, logout
- Projects & board: CRUD project, kanban board
- Project members: Keanggotaan project
- Lists: CRUD task list dalam project
- Subprojects: CRUD sub-project
- Tasks: CRUD task, move, transfer, archive
- Comments & attachments: Komentar, lampiran, checklist
- User management: Pengaturan user, performa
- AI features: Priority queue, chat, developer
"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ============================================================
    # AUTENTIKASI
    # ============================================================
    path('login/', auth_views.LoginView.as_view(template_name='arva/auth_login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    # path('register/', views.register, name='register'),

    # ============================================================
    # PROJECT & BOARD
    # ============================================================
    path('', views.project_list, name='project_list'),
    path('my/cards/', views.my_cards, name='my_cards'),
    path('tasks/search/', views.task_search_by_user, name='task_search_by_user'),
    path('tasks/user-suggestions/', views.task_user_suggestions, name='task_user_suggestions'),
    path('project/create/', views.project_create, name='project_create'),
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('project/<int:pk>/update/', views.project_update, name='project_update'),
    path('project/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('project/<int:pk>/convert-subproject/', views.project_convert_to_subproject, name='project_convert_to_subproject'),
    path('project/<int:pk>/activity/', views.project_activity, name='project_activity'),
    path('project/<int:pk>/close/', views.project_close, name='project_close'),
    path('project/<int:pk>/reopen/', views.project_reopen, name='project_reopen'),
    path('project/<int:pk>/archive/', views.project_archive, name='project_archive'),
    path('project/<int:pk>/subprojects/list/', views.subproject_list, name='subproject_list'),
    path('project/<int:pk>/lists/', views.project_lists, name='project_lists'),

    # ============================================================
    # KEANGGOTAAN PROJECT
    # ============================================================
    path('project/<int:pk>/members/', views.project_members, name='project_members'),
    path('project/<int:pk>/members/add/', views.project_member_add, name='project_member_add'),
    path('project/member/<int:member_id>/update/', views.project_member_update, name='project_member_update'),
    path('project/member/<int:member_id>/delete/', views.project_member_delete, name='project_member_delete'),

    # ============================================================
    # TASK LIST & SUBPROJECT
    # ============================================================
    path('project/<int:pk>/list/create/', views.tasklist_create, name='tasklist_create'),
    path('project/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('project/<int:pk>/list/reorder/', views.tasklist_reorder, name='tasklist_reorder'),
    path('list/<int:list_id>/delete/', views.tasklist_delete, name='tasklist_delete'),
    path('list/<int:list_id>/archive/', views.tasklist_archive, name='tasklist_archive'),
    path('list/<int:list_id>/unarchive/', views.tasklist_unarchive, name='tasklist_unarchive'),
    path('project/<int:pk>/subproject/create/', views.subproject_create, name='subproject_create'),
    path('subproject/<int:subproject_id>/delete/', views.subproject_delete, name='subproject_delete'),
    path('subproject/<int:subproject_id>/edit/', views.subproject_edit, name='subproject_edit'),
    path('subproject/<int:subproject_id>/move/', views.subproject_move, name='subproject_move'),
    path('subproject/<int:subproject_id>/convert-project/', views.subproject_convert_to_project, name='subproject_convert_to_project'),
    path('project/<int:pk>/subprojects/', views.project_subprojects, name='project_subprojects'),

    # ============================================================
    # TASK
    # ============================================================
    path('project/<int:pk>/task/create/', views.task_create, name='task_create'),
    path('task/<int:task_id>/view/', views.task_view, name='task_view'),
    path('task/<int:task_id>/', views.task_detail, name='task_detail'),
    path('task/<int:task_id>/update/', views.task_update, name='task_update'),
    path('task/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:task_id>/move/', views.task_move, name='task_move'),
    path('task/<int:task_id>/transfer/', views.task_transfer, name='task_transfer'),
    path('task/<int:task_id>/archive/', views.task_archive, name='task_archive'),
    path('task/<int:task_id>/unarchive/', views.task_unarchive, name='task_unarchive'),
    path('task/<int:task_id>/inline-update/', views.task_inline_update, name='task_inline_update'),

    # ============================================================
    # KOMENTAR & LAMPIRAN
    # ============================================================
    path('task/<int:task_id>/comment/add/', views.comment_add, name='comment_add'),
    path('comment/<int:comment_id>/reply/', views.comment_reply, name="comment_reply"),
    path('comment/<int:comment_id>/edit/', views.comment_edit, name="comment_edit"),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name="comment_delete"),
    path('notifications/<int:notification_id>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/<int:notification_id>/open/', views.notification_open, name='notification_open'),
    path('notifications/', views.notification_history, name='notification_history'),
    path('task/<int:task_id>/attachment/add/', views.attachment_add, name='attachment_add'),
    path('attachment/<int:attachment_id>/delete/', views.attachment_delete, name='attachment_delete'),

    # ============================================================
    # CHECKLIST
    # ============================================================
    path('task/<int:task_id>/checklist/add/', views.checklist_add, name='checklist_add'),
    path('checklist/<int:item_id>/edit/', views.checklist_edit, name='checklist_edit'),
    path('checklist/<int:item_id>/delete/', views.checklist_delete, name='checklist_delete'),
    path('checklist/<int:item_id>/toggle/', views.checklist_toggle, name='checklist_toggle'),

    # ============================================================
    # MANAJEMEN USER
    # ============================================================
    path('users/', views.user_list, name='user_list'),
    path('users/pending/', views.pending_users, name='pending_users'),
    path('users/<int:user_id>/approve/', views.approve_user, name='approve_user'),
    path('users/<int:user_id>/reject/', views.reject_user, name='reject_user'),
    path('users/create/', views.create_user_system, name='create_user_system'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/delete/', views.user_hard_delete, name='user_hard_delete'),
    path('project-member/<int:pm_id>/update-role/', views.project_member_update_role, name='project_member_update_role'),
    path('project-member/<int:pm_id>/remove/', views.project_member_remove, name='project_member_remove'),

    # ============================================================
    # PENGATURAN
    # ============================================================
    path('settings/', views.user_settings, name='user_settings'),
    path('profile/', views.my_profile, name='my_profile'),
    path('profile/update/', views.my_profile_update, name='my_profile_update'),
    path('profile/change-password/', views.my_profile_change_password, name='my_profile_change_password'),
    path('settings/website/', views.website_settings, name='website_settings'),
    path('settings/ai/', views.ai_settings, name='ai_settings'),
    path('profile/theme/update/', views.update_user_theme, name='update_user_theme'),
    path('profile/layout/update/', views.update_user_layout, name='update_user_layout'),

    # ============================================================
    # PERFORMA USER
    # ============================================================
    path('user/performance/', views.user_performance, name='user_performance'),

    # ============================================================
    # AI PRIORITY ANALYSIS
    # ============================================================
    path('ai/priority-queue/', views.ai_priority_queue, name='ai_priority_queue'),
    path('ai/priority-refresh/', views.ai_priority_refresh, name='ai_priority_refresh'),
    path('ai/analyze-task/<int:task_id>/', views.ai_analyze_task, name='ai_analyze_task'),
    path('ai/analyze-project/<int:pk>/', views.ai_analyze_project, name='ai_analyze_project'),
    
    # ============================================================
    # AI CHAT ASSISTANT
    # ============================================================
    path('ai/chat/', views.ai_chat, name='ai_chat'),
    path('ai/chat/send/', views.ai_chat_send, name='ai_chat_send'),
    path('ai/chat/clear/', views.ai_chat_clear, name='ai_chat_clear'),
    path('ai/chat/today-work/', views.ai_chat_today_work, name='ai_chat_today_work'),
    
    # ============================================================
    # AI DEVELOPER V1 (LEGACY)
    # ============================================================
    path('ai/developer/', views.ai_developer_dashboard, name='ai_developer_dashboard'),
    path('ai/developer/create/', views.ai_developer_create_request, name='ai_developer_create'),
    path('ai/developer/request/<int:request_id>/', views.ai_developer_request_detail, name='ai_developer_request_detail'),
    path('ai/developer/request/<int:request_id>/start/', views.ai_developer_start_processing, name='ai_developer_start'),
    path('ai/developer/request/<int:request_id>/apply/', views.ai_developer_apply_changes, name='ai_developer_apply'),
    path('ai/developer/request/<int:request_id>/reject/', views.ai_developer_reject_changes, name='ai_developer_reject'),
    path('ai/developer/request/<int:request_id>/cancel/', views.ai_developer_cancel_request, name='ai_developer_cancel'),
    path('ai/developer/diff/<int:change_id>/', views.ai_developer_view_diff, name='ai_developer_diff'),
    path('ai/developer/analysis/', views.ai_developer_codebase_analysis, name='ai_developer_analysis'),
    path('ai/developer/api-status/', views.ai_developer_api_status, name='ai_developer_api_status'),
    
    # ============================================================
    # AI DEVELOPER V2 (PROGRESS TRACKING)
    # ============================================================
    path('ai/developer/v2/create/', views.ai_developer_create_v2, name='ai_developer_create_v2'),
    path('ai/developer/v2/request/<int:request_id>/progress/', views.ai_developer_progress, name='ai_developer_progress'),
    path('ai/developer/v2/request/<int:request_id>/start/', views.ai_developer_start_v2, name='ai_developer_start_v2'),
    path('ai/developer/v2/request/<int:request_id>/retry/', views.ai_developer_retry_v2, name='ai_developer_retry'),
    
    # ============================================================
    # API ENDPOINTS V2
    # ============================================================
    path('ai-developer/api/progress/<int:request_id>/', views.ai_developer_api_progress, name='ai_developer_api_progress'),
    path('ai-developer/api/cancel/<int:request_id>/', views.ai_developer_api_cancel, name='ai_developer_api_cancel'),
]
