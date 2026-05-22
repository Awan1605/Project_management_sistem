"""
Paket Views Arviga Project Manager
===================================
Semua view dipecah menjadi modul-modul berdasarkan domain:
- helpers: Fungsi bantu yang dipakai bersama
- auth: Login, logout, registrasi
- project: CRUD project, archive, members
- subproject: CRUD subproject, pindah, konversi
- task: CRUD task, pindah, transfer, archive
- comment: Komentar, balasan, lampiran, checklist
- user: Manajemen user, pengaturan, performa
- ai: AI Priority, Chat, Developer
"""

# Re-export semua view agar urls.py tidak perlu diubah
from .helpers import (
    STRUCTURED_TASK_PRIORITIES,
    STRUCTURED_TASK_STATUSES,
    get_accessible_projects_queryset,
    get_user_project_or_404,
    get_project_subproject_or_404,
    get_role,
    require_role,
    can_manage_project,
    is_project_locked,
    closed_project_error,
    sync_project_shares,
    _get_priority_level,
)

from .auth import register, custom_logout

from .project import (
    project_list,
    project_detail,
    project_create,
    project_edit,
    project_update,
    project_delete,
    project_archive,
    project_close,
    project_reopen,
    project_convert_to_subproject,
    project_activity,
    project_members,
    project_member_add,
    project_member_update,
    project_member_delete,
    project_lists,
    tasklist_create,
    tasklist_reorder,
    tasklist_delete,
    tasklist_archive,
    tasklist_unarchive,
)

from .subproject import (
    subproject_list,
    subproject_create,
    subproject_delete,
    subproject_edit,
    subproject_move,
    subproject_convert_to_project,
    project_subprojects,
)

from .task import (
    task_create,
    task_view,
    task_detail,
    task_update,
    task_delete,
    task_move,
    task_transfer,
    task_archive,
    task_unarchive,
    task_inline_update,
    task_search_by_user,
    task_user_suggestions,
    my_cards,
)

from .comment import (
    comment_add,
    comment_reply,
    comment_edit,
    comment_delete,
    notification_mark_read,
    notification_open,
    notification_history,
    attachment_add,
    attachment_delete,
    checklist_add,
    checklist_edit,
    checklist_toggle,
    checklist_delete,
)

from .user import (
    my_profile,
    my_profile_update,
    my_profile_change_password,
    user_settings,
    website_settings,
    user_performance,
    ai_settings,
    update_user_theme,
    update_user_layout,
    user_list,
    create_user_system,
    user_edit,
    user_toggle_active,
    user_reset_password,
    user_hard_delete,
    project_member_update_role,
    project_member_remove,
)

from .approval import (
    pending_users,
    approve_user,
    reject_user,
)

from .ai import (
    ai_priority_queue,
    ai_priority_refresh,
    ai_analyze_task,
    ai_analyze_project,
    ai_chat,
    ai_chat_send,
    ai_chat_clear,
    ai_chat_today_work,
    ai_developer_dashboard,
    ai_developer_create_request,
    ai_developer_request_detail,
    ai_developer_start_processing,
    ai_developer_apply_changes,
    ai_developer_reject_changes,
    ai_developer_cancel_request,
    ai_developer_view_diff,
    ai_developer_codebase_analysis,
    ai_developer_api_status,
    ai_developer_create_v2,
    ai_developer_progress,
    ai_developer_start_v2,
    ai_developer_retry_v2,
    ai_developer_api_progress,
    ai_developer_api_cancel,
)
