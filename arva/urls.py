from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='arva/auth_login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # path('register/', views.register, name='register'),

    # Projects & board
    path('', views.project_list, name='project_list'),
    path('my/cards/', views.my_cards, name='my_cards'),
    path('project/create/', views.project_create, name='project_create'),
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('project/<int:pk>/update/', views.project_update, name='project_update'),
    path('project/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('project/<int:pk>/activity/', views.project_activity, name='project_activity'),
    path('project/<int:pk>/archive/', views.project_archive, name='project_archive'),
    path('project/<int:pk>/subprojects/list/', views.subproject_list, name='subproject_list'),
    path('project/<int:pk>/lists/', views.project_lists, name='project_lists'),

    # Project members
    path('project/<int:pk>/members/', views.project_members, name='project_members'),
    path('project/<int:pk>/members/add/', views.project_member_add, name='project_member_add'),
    path('project/member/<int:member_id>/update/', views.project_member_update, name='project_member_update'),
    path('project/member/<int:member_id>/delete/', views.project_member_delete, name='project_member_delete'),

    # Lists
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
    path('project/<int:pk>/subprojects/', views.project_subprojects, name='project_subprojects'),

    # Tasks
    path('project/<int:pk>/task/create/', views.task_create, name='task_create'),
    path('task/<int:task_id>/view/', views.task_view, name='task_view'),
    path('task/<int:task_id>/update/', views.task_update, name='task_update'),
    path('task/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:task_id>/move/', views.task_move, name='task_move'),
    path('task/<int:task_id>/transfer/', views.task_transfer, name='task_transfer'),
    path('task/<int:task_id>/archive/', views.task_archive, name='task_archive'),
    path('task/<int:task_id>/unarchive/', views.task_unarchive, name='task_unarchive'),
    path('task/<int:task_id>/inline-update/', views.task_inline_update, name='task_inline_update'),

    # Comments & attachments
    path('task/<int:task_id>/comment/add/', views.comment_add, name='comment_add'),
    path('comment/<int:comment_id>/reply/', views.comment_reply, name="comment_reply"),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name="comment_delete"),
    path('task/<int:task_id>/attachment/add/', views.attachment_add, name='attachment_add'),

    # Checklist
    path('task/<int:task_id>/checklist/add/', views.checklist_add, name='checklist_add'),
    path('checklist/<int:item_id>/edit/', views.checklist_edit, name='checklist_edit'),
    path('checklist/<int:item_id>/delete/', views.checklist_delete, name='checklist_delete'),
    path('checklist/<int:item_id>/toggle/', views.checklist_toggle, name='checklist_toggle'),

    # User
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user_system, name='create_user_system'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/delete/', views.user_hard_delete, name='user_hard_delete'),
    path('project-member/<int:pm_id>/update-role/', views.project_member_update_role, name='project_member_update_role'),
    path('project-member/<int:pm_id>/remove/', views.project_member_remove, name='project_member_remove'),

    # Settings
    path('settings/website/', views.website_settings, name='website_settings'),
    path('profile/theme/update/', views.update_user_theme, name='update_user_theme'),
]
