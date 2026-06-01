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
    path('project/<int:pk>/subproject/create/', views.subproject_create, name='subproject_create'),
    path('subproject/<int:subproject_id>/delete/', views.subproject_delete, name='subproject_delete'),
    path('subproject/<int:subproject_id>/edit/', views.subproject_edit, name='subproject_edit'),
    path('subproject/<int:subproject_id>/move/', views.subproject_move, name='subproject_move'),
    path('subproject/<int:subproject_id>/convert-project/', views.subproject_convert_to_project, name='subproject_convert_to_project'),
    path('project/<int:pk>/subprojects/', views.project_subprojects, name='project_subprojects'),


    # ============================================================
    # KOMENTAR & LAMPIRAN
    # ===========================================================,
    path('comment/<int:comment_id>/reply/', views.comment_reply, name="comment_reply"),
    path('comment/<int:comment_id>/edit/', views.comment_edit, name="comment_edit"),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name="comment_delete"),
    path('notifications/<int:notification_id>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/<int:notification_id>/open/', views.notification_open, name='notification_open'),
    path('notifications/', views.notification_history, name='notification_history'),
    path('notifications/poll/', views.notification_poll, name='notification_poll'),
    path('notifications/push/public-key/', views.webpush_public_key, name='webpush_public_key'),
    path('notifications/push/status/', views.webpush_status, name='webpush_status'),
    path('notifications/push/subscribe/', views.webpush_subscribe, name='webpush_subscribe'),
    path('notifications/push/unsubscribe/', views.webpush_unsubscribe, name='webpush_unsubscribe'),
    path('attachment/<int:attachment_id>/delete/', views.attachment_delete, name='attachment_delete'),

    # ============================================================
    # CHECKLIST
    # ============================================================
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

]