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

function showError(message, title = 'Error') {
  Swal.fire({
    icon: 'error',
    title: title,
    text: message
  });
}

function showConfirm(message, title = 'Are you sure?') {
  return Swal.fire({
    icon: 'warning',
    title: title,
    text: message,
    showCancelButton: true,
    confirmButtonText: 'Yes',
    cancelButtonText: 'Cancel'
  }).then((result) => result.isConfirmed);
}

function showPrompt(message, title = 'Input') {
  return Swal.fire({
    title: title,
    text: message,
    input: 'text',
    inputPlaceholder: message,
    showCancelButton: true,
    confirmButtonText: 'Submit',
    cancelButtonText: 'Cancel'
  }).then((result) => (result.isConfirmed ? result.value : null));
}

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
        showError("Failed to change theme.");
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
        showError('Failed to create project');
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
        showError("Failed to save changes.");
      }
    });
  });

  $(document).on('click', '.btn-delete-project', async function () {
      const btn = $(this);
      const projectId = btn.data('id');

      if (!await showConfirm("Are you sure you want to delete this project?", "Delete project")) {
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
                  showError(resp.error || "Failed to delete project.");
              }
          },
          error: function (xhr) {
              if (xhr.responseJSON && xhr.responseJSON.error) {
                  showError(xhr.responseJSON.error);
              } else {
                  showError("Failed to delete project.");
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
        showError('Failed to create list');
      }
    });
  });

  $(document).on('click', '.btn-list-delete', async function() {
    if (!await showConfirm('Delete this list and all tasks inside it?', 'Delete list')) return;
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
        showError('Failed to delete list');
      }
    });
  });

  $(document).on('click', '.btn-list-archive', async function() {
    if (!await showConfirm('Archive this list and all tasks inside it?', 'Archive list')) return;
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
        showError('Failed to archive list');
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
        showError('Failed to unarchive list');
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
        showError('Failed to unarchive task');
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
          showError('You do not have access to create tasks on this board.');
        } else {
          showError('Failed to create task');
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
          showError('You do not have access to make this change.');
        } else {
          showError('Failed to save changes.');
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
        $('#task-view-body').html('<div class="text-danger">You are not allowed to view this task.</div>');
      }
    }).fail(function(xhr) {
      if (xhr.status === 403) {
        $('#task-view-body').html('<div class="text-danger">You are not allowed to view this task.</div>');
      } else {
        $('#task-view-body').html('<div class="text-danger">Failed to load task.</div>');
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
          showError(resp.error || 'Failed to move task.');
        }
      },
      error: function() {
        showError('Failed to move task.');
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
          showError(resp.error || 'Failed to move task.');
        }
      },
      error: function() {
        showError('Failed to move task.');
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
          showError('You do not have access to comment on this task.');
        } else {
          showError('Failed to send comment.');
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
        showError("Failed to send reply.");
      }
    });
  });

  $(document).on('click', '.btn-delete-comment', async function() {
    if (!await showConfirm("Delete this comment?", "Delete comment")) return;

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
          showError("You do not have access to delete this comment.");
        } else {
          showError("Failed to delete comment.");
        }
      }
    });
  });

  $(document).on('click', '#btn-add-checkitem', async function() {
    const taskId = $('#taskViewModal').data('task-id');
    if (!taskId) return;

    const content = await showPrompt('Checklist item name:', 'Add checklist');
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
          showError("You do not have access to change this task's checklist.");
        } else {
          showError('Failed to add checklist.');
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
          showError("You do not have access to change this task's checklist.");
        } else {
          showError('Failed to update checklist status.');
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
          showError('You do not have access to upload attachments on this task.');
        } else {
          showError('Failed to upload attachment.');
        }
      }
    });
  });

  $(document).on('click', '.btn-delete-task', async function() {
    if (!await showConfirm('Are you sure you want to delete this task?', 'Delete task')) return;
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
          showError('You do not have access to delete this task.');
        } else {
          showError('Failed to delete task');
        }
      }
    });
  });

  $(document).on('click', '.btn-archive-task', async function() {
    const card = $(this).closest('.task-card');
    const taskId = card.data('task-id');
    if (!await showConfirm('Archive this task?', 'Archive task')) return;

    $.post({
      url: `/task/${taskId}/archive/`,
      success: function(resp) {
        if (resp.success) {
          card.remove();
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          showError('You do not have access to archive this task.');
        } else {
          showError('Failed to archive task');
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
          showError('You do not have access to comment.');
        } else {
          showError('Failed to send comment');
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
          showError('You do not have access to upload attachments.');
        } else {
          showError('Failed to upload attachment');
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
          showError('You do not have access to add checklist items.');
        } else {
          showError('Failed to add checklist');
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
            showError("Failed to update checklist");
          }
        });
      }
    });
  });

  $(document).on('click', '.btn-delete-checkitem', async function() {
    if (!await showConfirm("Delete this checklist item?", "Delete checklist")) return;

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
        showError("Failed to delete checklist");
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
          showError("No access.");
        } else {
          showError("Failed to create user.");
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
        showError('Failed to change status.');
      }
    });
  });

  $(document).on('click', '.btn-delete-user', async function() {
    if (!await showConfirm("Are you sure you want to permanently delete this user? This cannot be undone.", "Delete user")) return;

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
        showError(xhr.responseJSON?.error || 'Failed to delete user.');
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
          showError('Failed to reset password.');
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
          showError("Failed to update role.");
        }
      },
      error: function() {
        showError("Failed to update role.");
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
                showError(resp.error);
            }
        },
        error: function (xhr) {
            showError(xhr.responseJSON?.error || "Failed to update role.");
        }
    });
});


  $(document).on('click', '.btn-remove-membership', async function() {
    if (!await showConfirm("Delete user dari project ini?", "Remove member")) return;

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
        showError('Failed to apply filter');
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
              showError('You do not have access to move this task.');
            } else {
              showError('Failed to move task');
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
