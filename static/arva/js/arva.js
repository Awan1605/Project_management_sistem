function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
const csrftoken = getCookie('csrftoken');
$.ajaxSetup({
  headers: {
    'X-CSRFToken': csrftoken
  }
});

$(function() {

  $(document).on('click', '.theme-select', function() {
    const theme = $(this).data('theme');

    $.post({
      url: '/profile/theme/update/',
      data: {
        theme: theme
      },
      headers: {
        "X-CSRFToken": csrftoken
      },
      success: function(resp) {
        if (resp.success) {
          location.reload();
        }
      },
      error: function() {
        alert("Gagal mengubah tema.");
      }
    });
  });

  $('#project-create-form').on('submit', function(e) {
    e.preventDefault();
    const $form = $(this);

    $.post({
      url: '/project/create/',
      data: $form.serialize(),
      success: function(resp) {
        if (resp.success) {
          $('#project-list').prepend(resp.html);
          $('#projectModal').modal('hide');
          $form[0].reset();
        }
      },
      error: function() {
        alert('Gagal membuat project');
      }
    });
  });

  $(document).on("click", "#btn-edit-project", function() {
    $("#projectEditModal").modal("show");
  });

  $("#project-edit-form").on("submit", function(e) {
    e.preventDefault();
    const projectId = $("#task-board").data("project-id");

    $.post({
      url: `/project/${projectId}/edit/`,
      data: $(this).serialize(),
      success: function(resp) {
        if (resp.success) {
          $(".board-header .project-header").text(resp.name);
          $(".board-header .project-description").text(resp.description || "-");

          $("#projectEditModal").modal("hide");
        }
      },
      error: function() {
        alert("Gagal menyimpan perubahan.");
      }
    });
  });

  $(document).on('click', '.btn-delete-project', function () {
      const btn = $(this);
      const projectId = btn.data('id');

      if (!confirm("Are you sure you want to delete this project?")) {
          return;
      }

      $.post({
          url: `/project/${projectId}/delete/`,
          success: function (resp) {
              if (resp.success) {
                  $(`#project-${projectId}`).fadeOut(200, function () {
                      $(this).remove();
                  });
              } else {
                  alert(resp.error || "Failed to delete project.");
              }
          },
          error: function (xhr) {
              if (xhr.responseJSON && xhr.responseJSON.error) {
                  alert(xhr.responseJSON.error);
              } else {
                  alert("Failed to delete project.");
              }
          }
      });
  });

  $(document).on('submit', '#add-list-form', function(e) {
    e.preventDefault();
    const $form = $(this);
    const projectId = $form.data('project-id');
    const name = $form.find('input[name="name"]').val().trim();
    if (!name) return;

    $.post({
      url: `/project/${projectId}/list/create/`,
      data: $form.serialize(),
      success: function(resp) {
        if (resp.success) {
          $(resp.html).insertBefore($('.add-list-column'));
          $form[0].reset();
          initSortable();
        }
      },
      error: function() {
        alert('Gagal membuat list');
      }
    });
  });

  $(document).on('click', '.btn-list-delete', function() {
    if (!confirm('Hapus list beserta semua card di dalamnya?')) return;
    const listElem = $(this).closest('.board-list');
    const listId = listElem.data('list-id');

    $.post({
      url: `/list/${listId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          listElem.remove();
          reorderListsOnServer();
        }
      },
      error: function() {
        alert('Gagal menghapus list');
      }
    });
  });

  $(document).on('click', '.btn-list-archive', function() {
    if (!confirm('Archive list ini dan semua card di dalamnya?')) return;
    const listElem = $(this).closest('.board-list');
    const listId = listElem.data('list-id');

    $.post({
      url: `/list/${listId}/archive/`,
      success: function(resp) {
        if (resp.success) {
          listElem.remove();
          reorderListsOnServer();
        }
      },
      error: function() {
        alert('Gagal archive list');
      }
    });
  });

  $(document).on('click', '.btn-unarchive-list', function() {
    const listId = $(this).data('list-id');
    const row = $(this).closest('li');
    $.post({
      url: `/list/${listId}/unarchive/`,
      success: function(resp) {
        if (resp.success) {
          row.remove();
        }
      },
      error: function() {
        alert('Gagal unarchive list');
      }
    });
  });

  $(document).on('click', '.btn-unarchive-task', function() {
    const taskId = $(this).data('task-id');
    const row = $(this).closest('li');
    $.post({
      url: `/task/${taskId}/unarchive/`,
      success: function(resp) {
        if (resp.success) {
          row.remove();
        }
      },
      error: function() {
        alert('Gagal unarchive task');
      }
    });
  });

  $(document).on('submit', '.add-card-form', function(e) {
    e.preventDefault();
    const $form = $(this);
    const title = $form.find('textarea[name="title"]').val().trim();
    if (!title) return;

    const projectId = $form.data('project-id');
    const listId = $form.data('list-id');

    const data = $form.serialize() + `&task_list_id=${listId}`;

    $.post({
      url: `/project/${projectId}/task/create/`,
      data: data,
      success: function(resp) {
        if (resp.success) {
          const column = $form.closest('.board-list').find('.task-column');
          column.append(resp.html);
          checkEmptyState(column);
          checkEmptyState($(resp.target));
          $form[0].reset();
          initSortable();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses membuat card di board ini.');
        } else {
          alert('Gagal membuat card');
        }
      }
    });
  });

  function inlineUpdate(taskId, field, value, onSuccess) {
    $.post({
      url: `/task/${taskId}/inline-update/`,
      data: {
        field: field,
        value: value
      },
      success: function(resp) {
        if (resp.success) {
          if (resp.html) {
            const card = $(`.task-card[data-task-id='${taskId}']`);
            card.replaceWith(resp.html);
          }
          if (typeof onSuccess === 'function') onSuccess();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses melakukan perubahan ini.');
        } else {
          alert('Gagal menyimpan perubahan.');
        }
      }
    });
  }

  function refreshBoardCard(taskId) {
    $.get(`/task/${taskId}/detail/`, function(resp) {
      if (resp.success && resp.html) {
        const card = $(`.task-card[data-task-id='${taskId}']`);
        card.replaceWith(resp.html);
      }
    });
  }

  $(document).on('change', '#task-view-title', function() {
    const taskId = $('#taskViewModal').data('task-id');
    inlineUpdate(taskId, 'title', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-desc', function() {
    const taskId = $('#taskViewModal').data('task-id');
    inlineUpdate(taskId, 'description', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-due', function() {
    const taskId = $('#taskViewModal').data('task-id');
    inlineUpdate(taskId, 'due_date', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-priority', function() {
    const taskId = $('#taskViewModal').data('task-id');
    inlineUpdate(taskId, 'priority', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-assignees', function() {
    const taskId = $('#taskViewModal').data('task-id');
    const values = $(this).val() ? $(this).val().join(',') : '';
    inlineUpdate(taskId, 'assignees', values, function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-labels', function() {
    const taskId = $('#taskViewModal').data('task-id');
    const values = $(this).val() ? $(this).val().join(',') : '';
    inlineUpdate(taskId, 'labels', values, function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('click', '.cover-color-box', function() {
    const taskId = $('#taskViewModal').data('task-id');
    const color = $(this).data('color');
    inlineUpdate(taskId, 'cover_color', color, () => {
      loadTaskView(taskId);
    });
  });

  $(document).on('click', '.btn-view-task', function() {
    const card = $(this).closest('.task-card');
    const taskId = card.data('task-id');

    $('#taskViewModal').data('task-id', taskId);

    $('#task-view-body').html('<div class="text-center text-muted">Loading...</div>');
    $('#taskViewModal').modal('show');

    loadTaskView(taskId);
  });

  function loadTaskView(taskId) {
    $.get(`/task/${taskId}/view/`, function(resp) {
      if (resp.success) {
        $('#task-view-body').html(resp.html);
      } else {
        $('#task-view-body').html('<div class="text-danger">Tidak boleh melihat card ini.</div>');
      }
    }).fail(function(xhr) {
      if (xhr.status === 403) {
        $('#task-view-body').html('<div class="text-danger">Tidak boleh melihat card ini.</div>');
      } else {
        $('#task-view-body').html('<div class="text-danger">Gagal memuat card.</div>');
      }
    });
  }

  function loadProjectLists(projectId, $select, selectedId) {
    if (!projectId || !$select) return;
    $.get(`/project/${projectId}/lists/`, function(resp) {
      if (!resp.success) return;
      $select.empty();
      resp.lists.forEach((lst) => {
        const option = $('<option>').val(lst.id).text(lst.name);
        if (selectedId && String(lst.id) === String(selectedId)) {
          option.attr('selected', 'selected');
        }
        $select.append(option);
      });
    });
  }

  function handleTaskMoved(taskId) {
    const $card = $(`.task-card[data-task-id='${taskId}']`);
    const $column = $card.closest('.task-column');
    $card.remove();
    if ($column.length && typeof checkEmptyState === 'function') {
      checkEmptyState($column);
    }

    $(`#mycards-table tbody tr[data-task-id='${taskId}']`).remove();
    if ($('#mycards-search').length) {
      $('#mycards-search').trigger('input');
    }

    $('#taskViewModal').modal('hide');
    $('#taskMoveModal').modal('hide');
  }

  $(document).on('change', '#task-move-project', function() {
    const projectId = $(this).val();
    const $listSelect = $('#task-move-list');
    loadProjectLists(projectId, $listSelect);
  });

  $(document).on('click', '#btn-move-task', function() {
    const taskId = $(this).data('task-id');
    const projectId = $('#task-move-project').val();
    const listId = $('#task-move-list').val();
    if (!taskId || !projectId) return;

    $.post({
      url: `/task/${taskId}/transfer/`,
      data: {
        project_id: projectId,
        task_list_id: listId
      },
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (resp.success) {
          handleTaskMoved(taskId);
        } else {
          alert(resp.error || 'Failed to move task.');
        }
      },
      error: function() {
        alert('Failed to move task.');
      }
    });
  });

  $(document).on('click', '.btn-quick-move-task', function() {
    const taskId = $(this).data('task-id');
    const projectId = $(this).data('project-id');
    const $modal = $('#taskMoveModal');
    $modal.data('task-id', taskId);
    $('#quick-move-project').val(projectId);
    loadProjectLists(projectId, $('#quick-move-list'));
    $modal.modal('show');
  });

  $(document).on('change', '#quick-move-project', function() {
    const projectId = $(this).val();
    loadProjectLists(projectId, $('#quick-move-list'));
  });

  $(document).on('click', '#btn-quick-move-confirm', function() {
    const $modal = $('#taskMoveModal');
    const taskId = $modal.data('task-id');
    const projectId = $('#quick-move-project').val();
    const listId = $('#quick-move-list').val();
    if (!taskId || !projectId) return;

    $.post({
      url: `/task/${taskId}/transfer/`,
      data: {
        project_id: projectId,
        task_list_id: listId
      },
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (resp.success) {
          handleTaskMoved(taskId);
        } else {
          alert(resp.error || 'Failed to move task.');
        }
      },
      error: function() {
        alert('Failed to move task.');
      }
    });
  });

  $(document).on('click', '#btn-add-comment', function() {
    const taskId = $('#taskViewModal').data('task-id');
    if (!taskId) return;

    const content = $('#task-view-comment-input').val().trim();
    if (!content) return;

    $.post({
      url: `/task/${taskId}/comment/add/`,
      data: {
        content: content
      },
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses memberi komentar pada card ini.');
        } else {
          alert('Gagal mengirim komentar.');
        }
      }
    });
  });

  $(document).on('click', '.btn-reply-comment', function() {
    const commentId = $(this).data('id');
    const container = $(this).closest('.comment-item').find('.reply-form');

    container.html(`
        <textarea class="form-control reply-input" rows="2" placeholder="Write a reply..."></textarea>
        <button class="btn btn-sm btn-primary mt-1 btn-submit-reply" data-id="${commentId}">
            Reply
        </button>
        <button class="btn btn-sm btn-secondary mt-1 btn-cancel-reply">
            Cancel
        </button>
    `);

    container.show();
  });

  $(document).on('click', '.btn-cancel-reply', function() {
    const container = $(this).closest('.reply-form');
    container.html('').hide();
  });

  $(document).on('click', '.btn-submit-reply', function() {
    const commentId = $(this).data('id');
    const container = $(this).closest('.reply-form');
    const content = container.find('.reply-input').val().trim();
    const taskId = $('#taskViewModal').data('task-id');

    if (!content) return;

    $.post({
      url: `/comment/${commentId}/reply/`,
      data: {
        content: content
      },
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function() {
        alert("Gagal mengirim reply.");
      }
    });
  });

  $(document).on('click', '.btn-delete-comment', function() {
    if (!confirm("Delete this comment?")) return;

    const commentId = $(this).data("id");
    const taskId = $('#taskViewModal').data('task-id');

    $.post({
      url: `/comment/${commentId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert("Anda tidak punya akses untuk menghapus komentar ini.");
        } else {
          alert("Gagal menghapus komentar.");
        }
      }
    });
  });

  $(document).on('click', '#btn-add-checkitem', function() {
    const taskId = $('#taskViewModal').data('task-id');
    if (!taskId) return;

    const content = prompt('Nama checklist item:');
    if (!content || !content.trim()) return;

    $.post({
      url: `/task/${taskId}/checklist/add/`,
      data: {
        content: content.trim()
      },
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses mengubah checklist card ini.');
        } else {
          alert('Gagal menambah checklist.');
        }
      }
    });
  });

  $(document).on('change', '#task-view-checklist .checklist-toggle', function() {
    const li = $(this).closest('li');
    const itemId = li.data('id');
    const taskId = $('#taskViewModal').data('task-id');
    if (!taskId || !itemId) return;

    $.post({
      url: `/checklist/${itemId}/toggle/`,
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses mengubah checklist card ini.');
        } else {
          alert('Gagal mengubah status checklist.');
        }
      }
    });
  });

  $(document).on('change', '#task-view-upload', function() {
    const taskId = $('#taskViewModal').data('task-id');
    if (!taskId) return;

    const fileInput = this;
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    $.ajax({
      url: `/task/${taskId}/attachment/add/`,
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      success: function(resp) {
        if (resp.success) {
          fileInput.value = '';
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses upload lampiran di card ini.');
        } else {
          alert('Gagal upload lampiran.');
        }
      }
    });
  });

  $(document).on('click', '.btn-delete-task', function() {
    if (!confirm('Yakin hapus card ini?')) return;
    const card = $(this).closest('.task-card');
    const taskId = card.data('task-id');

    $.post({
      url: `/task/${taskId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          card.remove();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses menghapus card ini.');
        } else {
          alert('Gagal menghapus card');
        }
      }
    });
  });

  $(document).on('click', '.btn-archive-task', function() {
    const card = $(this).closest('.task-card');
    const taskId = card.data('task-id');
    if (!confirm('Archive card ini?')) return;

    $.post({
      url: `/task/${taskId}/archive/`,
      success: function(resp) {
        if (resp.success) {
          card.remove();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses archive card ini.');
        } else {
          alert('Gagal archive card');
        }
      }
    });
  });

  $(document).on('click', '.toggle-comments', function() {
    const container = $(this).closest('.comment-section').find('.comments');
    container.toggleClass('d-none');
  });

  $(document).on('submit', '.comment-form', function(e) {
    e.preventDefault();
    const $form = $(this);
    const container = $form.closest('.comments');
    const taskId = container.data('task-id');
    const content = $form.find('textarea[name="content"]').val().trim();
    if (!content) return;

    $.post({
      url: `/task/${taskId}/comment/add/`,
      data: {
        content: content
      },
      success: function(resp) {
        if (resp.success) {
          const list = container.find('.comment-list');
          list.append(resp.html);
          $form.find('textarea[name="content"]').val('');
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses memberi komentar.');
        } else {
          alert('Gagal mengirim komentar');
        }
      }
    });
  });

  $(document).on('submit', '.attachment-form', function(e) {
    e.preventDefault();
    const $form = $(this);
    const container = $form.closest('.comments');
    const taskId = container.data('task-id');
    const fileInput = $form.find('input[type="file"]')[0];
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    $.ajax({
      url: `/task/${taskId}/attachment/add/`,
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      success: function(resp) {
        if (resp.success) {
          const list = container.find('.attachment-list');
          list.append(resp.html);
          $form[0].reset();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses upload lampiran.');
        } else {
          alert('Gagal upload lampiran');
        }
      }
    });
  });

  $(document).on('submit', '.checklist-form', function(e) {
    e.preventDefault();
    const $form = $(this);
    const container = $form.closest('.comments');
    const taskId = container.data('task-id');
    const content = $form.find('input[name="content"]').val().trim();
    if (!content) return;

    $.post({
      url: `/task/${taskId}/checklist/add/`,
      data: {
        content: content
      },
      success: function(resp) {
        if (resp.success) {
          const list = container.find('.checklist-list');
          list.append(resp.html);
          $form[0].reset();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          alert('Anda tidak punya akses menambah checklist.');
        } else {
          alert('Gagal menambah checklist');
        }
      }
    });
  });

  $(document).on('click', '.checklist-content', function() {
    const span = $(this);
    const text = span.text().trim();
    const li = span.closest("li");

    if (span.attr('disabled')) return;

    const input = $(`<input type="text" class="form-control form-control-sm checklist-edit-input" value="${text}">`);

    span.replaceWith(input);
    input.focus();

    input.on('blur keydown', function(e) {
      if (e.type === "blur" || e.key === "Enter") {

        const taskId = $('#taskViewModal').data('task-id');
        const itemId = li.data('id');
        const newContent = input.val().trim();

        $.post({
          url: `/checklist/${itemId}/edit/`,
          data: {
            content: newContent
          },
          success: function(resp) {
            if (resp.success) {
              loadTaskView(taskId);
            }
          },
          error: function() {
            alert("Gagal mengubah checklist");
          }
        });
      }
    });
  });

  $(document).on('click', '.btn-delete-checkitem', function() {
    if (!confirm("Hapus checklist item ini?")) return;

    const li = $(this).closest("li");
    const itemId = li.data("id");
    const taskId = $('#taskViewModal').data('task-id');

    $.post({
      url: `/checklist/${itemId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          loadTaskView(taskId);
        }
      },
      error: function() {
        alert("Gagal menghapus checklist");
      }
    });
  });

  $(document).on('click', '#btn-open-create-user-modal', function() {
    const form = $('#create-user-form');
    form[0].reset();
    form.find('.form-control').removeClass('is-invalid');
    form.find('.invalid-feedback').text('');
    $('#createUserModal').modal('show');
  });

  $(document).on('submit', '#create-user-form', function(e) {
    e.preventDefault();
    const form = $(this);

    form.find('.form-control').removeClass('is-invalid');
    form.find('.invalid-feedback').text('');

    $.post({
      url: '/users/create/',
      data: form.serialize(),
      success: function(resp) {
        if (resp.success) {
          $('#createUserModal').modal('hide');
          if ($('#user-table').length) {
            $('#user-table tbody').append(`
                        <tr data-user-id="${resp.user.id}">
                          <td>${resp.user.username}</td>
                          <td>${resp.user.email}</td>
                          <td><span class="badge bg-success">Yes</span></td>
                          <td>No</td>
                          <td></td>
                          <td></td>
                          <td>
                            <a href="/users/${resp.user.id}/edit/" class="btn btn-sm btn-outline-secondary">Edit</a>
                            <button class="btn btn-sm btn-outline-info btn-reset-password">Reset Password</button>
                            <button class="btn btn-sm btn-outline-warning btn-toggle-active">Toggle Active</button>
                            <button class="btn btn-sm btn-outline-danger btn-delete-user">Delete</button>
                          </td>
                        </tr>
                    `);
          }
        }
      },
      error: function(xhr) {
        if (xhr.status === 400 && xhr.responseJSON.errors) {
          const errors = xhr.responseJSON.errors;
          Object.keys(errors).forEach(function(field) {
            const input = form.find(`[name="${field}"]`);
            input.addClass('is-invalid');
            form.find(`.invalid-feedback[data-field="${field}"]`).text(errors[field][0]);
          });
        } else if (xhr.status === 403) {
          alert("Tidak punya akses.");
        } else {
          alert("Gagal membuat user.");
        }
      }
    });
  });

  $(document).on('click', '.btn-toggle-active', function() {
    const tr = $(this).closest('tr');
    const userId = tr.data('user-id');

    $.post({
      url: `/users/${userId}/toggle-active/`,
      success: function(resp) {
        if (resp.success) {
          const badge = tr.find('td:nth-child(3) .badge');
          if (resp.is_active) {
            badge.removeClass('bg-danger').addClass('bg-success').text('Yes');
          } else {
            badge.removeClass('bg-success').addClass('bg-danger').text('No');
          }
        }
      },
      error: function() {
        alert('Gagal mengubah status.');
      }
    });
  });

  $(document).on('click', '.btn-delete-user', function() {
    if (!confirm("Yakin ingin menghapus user ini secara permanen? Ini tidak bisa dibatalkan.")) return;

    const tr = $(this).closest('tr');
    const userId = tr.data('user-id');

    $.post({
      url: `/users/${userId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          tr.fadeOut(200, function() {
            $(this).remove();
          });
        }
      },
      error: function(xhr) {
        alert(xhr.responseJSON?.error || 'Gagal menghapus user.');
      }
    });
  });

  $(document).on('click', '.btn-reset-password', function() {
    const tr = $(this).closest('tr');
    const userId = tr.data('user-id');

    const form = $('#reset-password-form');
    form[0].reset();
    form.find('.form-control').removeClass('is-invalid');
    form.find('.invalid-feedback').text('');
    $('#reset-password-user-id').val(userId);
    $('#resetPasswordModal').modal('show');
  });

  $(document).on('submit', '#reset-password-form', function(e) {
    e.preventDefault();
    const form = $(this);
    const userId = $('#reset-password-user-id').val();

    form.find('.form-control').removeClass('is-invalid');
    form.find('.invalid-feedback').text('');

    $.post({
      url: `/users/${userId}/reset-password/`,
      data: form.serialize(),
      success: function(resp) {
        if (resp.success) {
          $('#resetPasswordModal').modal('hide');
        }
      },
      error: function(xhr) {
        if (xhr.status === 400 && xhr.responseJSON.errors) {
          const errors = xhr.responseJSON.errors;
          Object.keys(errors).forEach(function(field) {
            const input = form.find(`[name="${field}"]`);
            input.addClass('is-invalid');
            form.find(`.invalid-feedback[data-field="${field}"]`).text(errors[field][0]);
          });
        } else {
          alert('Gagal reset password.');
        }
      }
    });
  });

  $(document).on('change', '.member-role-select', function() {
    const tr = $(this).closest('tr');
    const pmId = tr.data('pm-id');
    const newRole = $(this).val();

    $.post({
      url: `/project-member/${pmId}/update-role/`,
      data: {
        role: newRole
      },
      success: function(resp) {
        if (!resp.success) {
          alert("Gagal update role.");
        }
      },
      error: function() {
        alert("Gagal update role.");
      }
    });
  });

  // open modal
$(document).on("click", ".btn-edit-member", function () {
    const id = $(this).data("id");
    const username = $(this).data("username");
    const role = $(this).data("role");

    $("#edit-member-id").val(id);
    $("#edit-member-username").val(username);
    $("#edit-member-role").val(role);

    $("#editMemberModal").modal("show");
});

$(document).on("click", "#btn-save-member", function () {
    const memberId = $("#edit-member-id").val();
    const newRole = $("#edit-member-role").val();

    $.post({
        url: `/project/member/${memberId}/update/`,
        data: { role: newRole },
        headers: { "X-CSRFToken": csrftoken },
        success: function (resp) {
            if (resp.success) {
                const row = $(`button[data-id="${memberId}"]`).closest("tr");
                row.find("td:nth-child(2)").text(newRole.charAt(0).toUpperCase() + newRole.slice(1));

                $("#editMemberModal").modal("hide");
            } else {
                alert(resp.error);
            }
        },
        error: function (xhr) {
            alert(xhr.responseJSON?.error || "Failed to update role.");
        }
    });
});


  $(document).on('click', '.btn-remove-membership', function() {
    if (!confirm("Hapus user dari project ini?")) return;

    const tr = $(this).closest('tr');
    const pmId = tr.data('pm-id');

    $.post({
      url: `/project-member/${pmId}/remove/`,
      success: function(resp) {
        if (resp.success) {
          tr.fadeOut(200, function() {
            $(this).remove();
          });
        }
      }
    });
  });

  $('#task-filter-form input, #task-filter-form select').on('change keyup', function() {
    const projectId = $('#task-board').data('project-id');
    const query = $('#task-filter-form').serialize();

    $.get({
      url: `/project/${projectId}/`,
      data: query,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      },
      success: function(resp) {
        $('#task-board-wrapper').html(resp.html);
        initSortable();
      },
      error: function() {
        alert('Gagal melakukan filter');
      }
    });
  });

  function reorderListsOnServer() {
    const projectId = $('#task-board').data('project-id');
    const orderedIds = [];
    $('#board-lists .board-list').each(function() {
      const id = $(this).data('list-id');
      if (id) orderedIds.push(id);
    });

    if (!orderedIds.length) return;

    $.post({
      url: `/project/${projectId}/list/reorder/`,
      data: {
        'ordered_ids[]': orderedIds
      }
    });
  }

  function checkEmptyState($column) {
    const hasCard = $column.find('.task-card').length > 0;
    const $empty = $column.find('.empty-card-state');

    if (hasCard) {
        $empty.hide();
    } else {
        $empty.show();
    }
  }

  function initSortable() {
    $('#board-lists').sortable({
      items: '> .board-list:not(.add-list-column)',
      axis: 'x',
      stop: function() {
        reorderListsOnServer();
      }
    });

    $('.task-column').sortable({
      connectWith: '.task-column',
      placeholder: 'task-placeholder',
      handle: '.card-body',
      start: function (event, ui) {
        ui.item.addClass('dragging');
      },
      stop: function(event, ui) {
        ui.item.removeClass('dragging');
        const $item = $(ui.item);
        const taskId = $item.data('task-id');
        const $column = $item.closest('.task-column');
        const listId = $column.data('list-id');
        const orderedIds = [];
        $column.find('.task-card').each(function() {
          orderedIds.push($(this).data('task-id'));
        });

        checkEmptyState($column);
        checkEmptyState($(event.target));

        $.post({
          url: `/task/${taskId}/move/`,
          data: {
            task_list_id: listId,
            'ordered_ids[]': orderedIds
          },
          error: function(xhr) {
            if (xhr.status === 403) {
              alert('Anda tidak punya akses memindahkan card ini.');
            } else {
              alert('Gagal memindahkan card');
            }
          }
        });
      }
    }).disableSelection();
  }

  if ($('#task-board').length) {
    initSortable();
  }
});
