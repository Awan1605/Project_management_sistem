"""
Paket Views Arviga Project Manager
===================================
Semua view dipecah menjadi modul-modul berdasarkan domain:
- helpers: Fungsi bantu yang dipakai bersama
- auth: Login, logout, registrasi
- project: CRUD project, archive, members
- subproject: CRUD subproject, pindah, konversi
- comment: Komentar, balasan, lampiran, checklist
- user: Manajemen user, pengaturan, performa
"""

# ============================================================
# HELPERS
# ============================================================

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

# ============================================================
# AUTH
# ============================================================

from .auth import (
    register,
    custom_logout,
)

# ============================================================
# PROJECT
# ============================================================

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
)

# ============================================================
# SUBPROJECT
# ============================================================

from .subproject import (
    subproject_list,
    subproject_create,
    subproject_delete,
    subproject_edit,
    subproject_move,
    subproject_convert_to_project,
    project_subprojects,
)

# ============================================================
# COMMENT & NOTIFICATION
# ============================================================

from .comment import (
    comment_add,
    comment_reply,
    comment_edit,
    comment_delete,
    notification_mark_read,
    notification_open,
    notification_history,
    notification_poll,
    webpush_public_key,
    webpush_status,
    webpush_subscribe,
    webpush_unsubscribe,
    service_worker_js,
    attachment_add,
    attachment_delete,
    checklist_add,
    checklist_edit,
    checklist_toggle,
    checklist_delete,
)

# ============================================================
# USER
# ============================================================

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

# ============================================================
# APPROVAL
# ============================================================

from .approval import (
    pending_users,
    approve_user,
    reject_user,
)
