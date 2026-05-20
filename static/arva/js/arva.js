/**
 * Arva.js - JavaScript Utama Arviga Project Manager
 * ==================================================
 * Menangani seluruh interaksi frontend aplikasi:
 *
 * Kelompok fungsi:
 * - Utilitas: getCookie, CSRF setup
 * - Project: Buat, edit, hapus, update project
 * - Task: Buat, edit, hapus, pindah, transfer, archive task
 * - Inline update: Update field task langsung (judul, deskripsi, deadline, dll)
 * - Komentar: Tambah, balas, hapus komentar
 * - Lampiran: Upload file, hapus lampiran
 * - Checklist: Tambah, edit, toggle, hapus checklist
 * - Task List: Buat, reorder, hapus, archive kolom
 * - Subproject: Buat, edit, hapus, pindah, konversi
 * - User: Update tema, layout, buat user, reset password
 * - AI: Priority queue, chat, developer
 * - UI: Modal, sidebar, tema, layout switching
 */

function getCookie(name) {
  /** Ambil nilai cookie berdasarkan nama. Digunakan untuk CSRF token. */
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

// Set progress bar widths from data-percent attribute (avoids CSS linter false positives)
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.checklist-progress-bar[data-percent]').forEach(function (el) {
    el.style.width = el.getAttribute('data-percent') + '%';
  });
  
  // Check if we need to open a task modal automatically (from AI Priority Queue or other links)
  const urlParams = new URLSearchParams(window.location.search);
  const openTaskId = urlParams.get('open_task');
  if (openTaskId && typeof loadTaskView === 'function') {
    // Show loading message
    Swal.fire({
      title: 'Loading Task...',
      allowOutsideClick: false,
      allowEscapeKey: false,
      didOpen: () => {
        Swal.showLoading();
      }
    });
    
    // Load the task view
    loadTaskView(openTaskId);
    
    // Open the modal
    $('#taskViewModal').modal('show');
    
    // Close loading message when modal is shown
    $('#taskViewModal').on('shown.bs.modal', function() {
      Swal.close();
      // Remove the URL parameter without reloading
      const newUrl = new URL(window.location);
      newUrl.searchParams.delete('open_task');
      window.history.replaceState({}, '', newUrl);
    });
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
  return new Promise((resolve) => {
    // Create a custom modal that will definitely be above Bootstrap modal
    const modalHtml = `
      <div class="modal fade" id="customPromptModal" tabindex="-1" style="z-index: 99999 !important;">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">${title}</h5>
            </div>
            <div class="modal-body">
              <p class="mb-2">${message}</p>
              <input type="text" class="form-control" id="customPromptInput" placeholder="${message}">
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="customPromptSubmit">Submit</button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Remove any existing custom prompt modal
    const existingModal = document.getElementById('customPromptModal');
    if (existingModal) {
      existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modalEl = document.getElementById('customPromptModal');
    const inputEl = document.getElementById('customPromptInput');
    const submitBtn = document.getElementById('customPromptSubmit');
    
    const modal = new bootstrap.Modal(modalEl, {
      backdrop: 'static',
      keyboard: false
    });
    
    // Handle submit
    const handleSubmit = () => {
      const value = inputEl.value.trim();
      modal.hide();
      resolve(value || null);
    };
    
    submitBtn.addEventListener('click', handleSubmit);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        handleSubmit();
      }
    });
    
    // Handle cancel
    modalEl.addEventListener('hidden.bs.modal', () => {
      modalEl.remove();
      resolve(null);
    }, { once: true });
    
    // Show modal and focus input
    modal.show();
    setTimeout(() => inputEl.focus(), 300);
  });
}

function stripBomText(node) {
  if (!node) return;
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  const toClean = [];
  while (walker.nextNode()) {
    const textNode = walker.currentNode;
    if (textNode.nodeValue && textNode.nodeValue.includes('\uFEFF')) {
      toClean.push(textNode);
    }
  }
  toClean.forEach((textNode) => {
    textNode.nodeValue = textNode.nodeValue.replace(/\uFEFF/g, '');
  });
}

$(function() {
  stripBomText(document.body);

  function initPersistentViewToggles() {
    document.querySelectorAll('.arva-view-toggle[data-view-storage-key]').forEach((container) => {
      const key = container.getAttribute('data-view-storage-key');
      if (!key) return;

      const buttons = Array.from(container.querySelectorAll('[data-bs-toggle="pill"][data-bs-target]'));
      if (!buttons.length) return;

      const defaultTarget = container.getAttribute('data-view-default-target') || buttons[0].getAttribute('data-bs-target');
      const storedTarget = localStorage.getItem(key);
      const targetToShow = storedTarget || defaultTarget;
      const initialBtn = buttons.find((btn) => btn.getAttribute('data-bs-target') === targetToShow);

      if (initialBtn && window.bootstrap?.Tab) {
        bootstrap.Tab.getOrCreateInstance(initialBtn).show();
      }

      buttons.forEach((btn) => {
        btn.addEventListener('shown.bs.tab', (event) => {
          const target = event.target.getAttribute('data-bs-target');
          if (!target) return;

          localStorage.setItem(key, target);
          buttons.forEach((x) => x.classList.toggle('active', x === event.target));
        });
      });
    });
  }

  initPersistentViewToggles();

  function normalizeMentionQuery(rawValue) {
    const value = (rawValue || '').trim();
    return value.startsWith('@') ? value.slice(1).trim() : value;
  }

  function getUserInitials(user) {
    const source = (user.full_name || user.username || user.email || '').trim();
    if (!source) return '?';
    const chunks = source.split(/\s+/).filter(Boolean);
    if (chunks.length >= 2) {
      return `${chunks[0][0]}${chunks[1][0]}`.toUpperCase();
    }
    return source.slice(0, 2).toUpperCase();
  }

  function fetchUserMentionSuggestions(query, handlers) {
    fetch(`/tasks/user-suggestions/?${new URLSearchParams({ q: query }).toString()}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).then((resp) => resp.json()).then((resp) => {
      if (!resp.success) {
        handlers.onError?.();
        return;
      }
      handlers.onSuccess?.(resp.results || []);
    }).catch(() => {
      handlers.onError?.();
    });
  }

  function applyMentionToBoardFilter(mentionValue) {
    const filterForm = document.getElementById('task-filter-form');
    if (!filterForm) return false;

    const assigneeInput = filterForm.querySelector('input[name="assignee_q"]');
    if (!assigneeInput) return false;

    const assigneeSelect = filterForm.querySelector('select[name="assignee"]');
    if (assigneeSelect) {
      assigneeSelect.value = '';
    }
    assigneeInput.value = mentionValue;
    assigneeInput.dispatchEvent(new Event('input', { bubbles: true }));
    assigneeInput.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
    return true;
  }

  function detectActiveTaskResultView() {
    const boardModeBtn = document.querySelector('[data-view-mode].active');
    if (boardModeBtn?.dataset?.viewMode) {
      return boardModeBtn.dataset.viewMode === 'list' ? 'list' : 'card';
    }
    const tabBtn = document.querySelector('.arva-view-toggle .btn.active[data-bs-target]');
    if (tabBtn) {
      const target = (tabBtn.getAttribute('data-bs-target') || '').toLowerCase();
      if (target.includes('table') || target.includes('list')) return 'list';
      if (target.includes('card') || target.includes('grid')) return 'card';
    }
    return 'card';
  }

  function getTaskSearchPanelHost() {
    return document.querySelector('.app-content') ||
      document.querySelector('main.container-fluid') ||
      document.querySelector('main') ||
      document.body;
  }

  function getTaskSearchPanelState() {
    if (window.__taskSearchPanelState) return window.__taskSearchPanelState;

    const host = getTaskSearchPanelHost();
    const panel = document.createElement('section');
    panel.id = 'task-user-results-panel';
    panel.className = 'task-user-results-panel d-none';
    panel.innerHTML = `
      <div class="task-user-results-header">
        <div>
          <div class="task-user-results-title">Showing tasks for:</div>
          <div class="task-user-results-user" data-task-user-results-user></div>
        </div>
        <div class="task-user-results-actions">
          <div class="btn-group btn-group-sm" role="group" aria-label="Task result view mode">
            <button type="button" class="btn btn-outline-secondary active" data-task-results-view="card"><i class="bi bi-grid-3x3-gap me-1"></i>Card</button>
            <button type="button" class="btn btn-outline-secondary" data-task-results-view="list"><i class="bi bi-list-ul me-1"></i>List</button>
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm" data-task-results-reset>
            <i class="bi bi-x-circle me-1"></i>Clear
          </button>
        </div>
      </div>
      <div class="task-user-results-toolbar">
        <div class="task-user-results-search">
          <i class="bi bi-search"></i>
          <input type="text" class="form-control form-control-sm" placeholder="Filter this user's tasks..." data-task-results-filter>
        </div>
        <select class="form-select form-select-sm" data-task-results-sort>
          <option value="updated_desc">Recently updated</option>
          <option value="updated_asc">Oldest updated</option>
          <option value="due_asc">Due date (soonest)</option>
          <option value="due_desc">Due date (latest)</option>
          <option value="title_asc">Title (A-Z)</option>
          <option value="title_desc">Title (Z-A)</option>
          <option value="project_asc">Project (A-Z)</option>
        </select>
        <select class="form-select form-select-sm" data-task-results-per-page>
          <option value="10">10</option>
          <option value="25" selected>25</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
        <div class="task-user-results-summary" data-task-results-summary></div>
      </div>
      <div class="task-user-results-empty d-none" data-task-results-empty>
        <i class="bi bi-inbox"></i>
        <span>No tasks found for this user.</span>
      </div>
      <div class="task-user-results-card-list" data-task-results-cards></div>
      <div class="table-responsive d-none" data-task-results-table-wrap>
        <table class="table table-sm table-hover align-middle mb-0 table-modern">
          <thead>
            <tr>
              <th>Task</th>
              <th>Project</th>
              <th>Status</th>
              <th>Due</th>
              <th class="text-end">Action</th>
            </tr>
          </thead>
          <tbody data-task-results-table-body></tbody>
        </table>
      </div>
      <div class="task-user-results-pagination d-none" data-task-results-pagination>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-task-results-prev><i class="bi bi-chevron-left"></i></button>
        <span data-task-results-page-info></span>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-task-results-next><i class="bi bi-chevron-right"></i></button>
      </div>
    `;
    host.prepend(panel);

    const state = {
      panel,
      user: null,
      tasks: [],
      filtered: [],
      page: 1,
      perPage: 25,
      viewMode: detectActiveTaskResultView(),
    };

    state.userLabel = panel.querySelector('[data-task-user-results-user]');
    state.filterInput = panel.querySelector('[data-task-results-filter]');
    state.sortSelect = panel.querySelector('[data-task-results-sort]');
    state.perPageSelect = panel.querySelector('[data-task-results-per-page]');
    state.summary = panel.querySelector('[data-task-results-summary]');
    state.empty = panel.querySelector('[data-task-results-empty]');
    state.cardList = panel.querySelector('[data-task-results-cards]');
    state.tableWrap = panel.querySelector('[data-task-results-table-wrap]');
    state.tableBody = panel.querySelector('[data-task-results-table-body]');
    state.pagination = panel.querySelector('[data-task-results-pagination]');
    state.pageInfo = panel.querySelector('[data-task-results-page-info]');
    state.prevBtn = panel.querySelector('[data-task-results-prev]');
    state.nextBtn = panel.querySelector('[data-task-results-next]');
    state.viewButtons = Array.from(panel.querySelectorAll('[data-task-results-view]'));
    state.resetBtn = panel.querySelector('[data-task-results-reset]');

    state.viewButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        state.viewMode = btn.dataset.taskResultsView === 'list' ? 'list' : 'card';
        renderTaskSearchPanel(state);
      });
    });
    state.resetBtn?.addEventListener('click', () => {
      state.user = null;
      state.tasks = [];
      state.filtered = [];
      state.page = 1;
      state.filterInput.value = '';
      panel.classList.add('d-none');
    });
    state.filterInput?.addEventListener('input', () => {
      state.page = 1;
      renderTaskSearchPanel(state);
    });
    state.sortSelect?.addEventListener('change', () => {
      state.page = 1;
      renderTaskSearchPanel(state);
    });
    state.perPageSelect?.addEventListener('change', () => {
      const next = parseInt(state.perPageSelect.value || '25', 10);
      state.perPage = [10, 25, 50, 100].includes(next) ? next : 25;
      state.page = 1;
      renderTaskSearchPanel(state);
    });
    state.prevBtn?.addEventListener('click', () => {
      if (state.page <= 1) return;
      state.page -= 1;
      renderTaskSearchPanel(state);
    });
    state.nextBtn?.addEventListener('click', () => {
      state.page += 1;
      renderTaskSearchPanel(state);
    });

    window.__taskSearchPanelState = state;
    return state;
  }

  function getTaskSortValue(task, mode) {
    if (mode === 'updated_asc' || mode === 'updated_desc') {
      return task.updated_at || '';
    }
    if (mode === 'due_asc' || mode === 'due_desc') {
      return task.due_date || '';
    }
    if (mode === 'title_asc' || mode === 'title_desc') {
      return (task.title || '').toLowerCase();
    }
    if (mode === 'project_asc') {
      return (task.project_name || '').toLowerCase();
    }
    return task.updated_at || '';
  }

  function renderTaskSearchPanel(state) {
    if (!state?.panel) return;
    const query = (state.filterInput?.value || '').trim().toLowerCase();
    const sortMode = state.sortSelect?.value || 'updated_desc';
    const sortDesc = sortMode.endsWith('_desc');

    const filtered = state.tasks.filter((task) => {
      if (!query) return true;
      const hay = `${task.title || ''} ${task.project_name || ''} ${task.status || ''} ${task.assignees_display || ''}`.toLowerCase();
      return hay.includes(query);
    });
    filtered.sort((a, b) => {
      const aVal = getTaskSortValue(a, sortMode);
      const bVal = getTaskSortValue(b, sortMode);
      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });

    state.filtered = filtered;
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / state.perPage));
    state.page = Math.max(1, Math.min(state.page, totalPages));
    const start = (state.page - 1) * state.perPage;
    const end = start + state.perPage;
    const visible = filtered.slice(start, end);

    state.userLabel.textContent = state.user ? `${state.user.full_name || state.user.username} (${state.user.email || state.user.username})` : '-';
    state.summary.textContent = total ? `Showing ${start + 1}-${Math.min(end, total)} of ${total} task${total === 1 ? '' : 's'}` : 'Showing 0 of 0 tasks';

    state.empty.classList.toggle('d-none', total > 0);
    state.pagination.classList.toggle('d-none', total <= state.perPage || total === 0);
    state.pageInfo.textContent = `Page ${state.page} / ${totalPages}`;
    state.prevBtn.disabled = state.page <= 1;
    state.nextBtn.disabled = state.page >= totalPages;

    state.viewButtons.forEach((btn) => {
      const active = btn.dataset.taskResultsView === state.viewMode;
      btn.classList.toggle('active', active);
    });
    const isList = state.viewMode === 'list';
    state.cardList.classList.toggle('d-none', isList);
    state.tableWrap.classList.toggle('d-none', !isList);

    state.cardList.innerHTML = '';
    state.tableBody.innerHTML = '';
    visible.forEach((task) => {
      const card = document.createElement('article');
      card.className = 'task-user-result-card';
      const cardMeta = document.createElement('div');
      cardMeta.className = 'task-user-result-meta';
      cardMeta.textContent = `${task.project_name || '-'} | ${task.status || '-'}`;
      const cardTitle = document.createElement('div');
      cardTitle.className = 'task-user-result-title';
      cardTitle.textContent = task.title || '-';
      const cardFoot = document.createElement('div');
      cardFoot.className = 'task-user-result-foot';
      const due = document.createElement('span');
      due.className = 'task-user-result-due';
      due.textContent = task.due_date_display || 'No due';
      const go = document.createElement('a');
      go.href = task.url || '#';
      go.className = 'btn btn-outline-primary btn-sm';
      go.textContent = 'Open';
      cardFoot.appendChild(due);
      cardFoot.appendChild(go);
      card.appendChild(cardMeta);
      card.appendChild(cardTitle);
      card.appendChild(cardFoot);
      state.cardList.appendChild(card);

      const tr = document.createElement('tr');
      const tdTask = document.createElement('td');
      tdTask.textContent = task.title || '-';
      const tdProject = document.createElement('td');
      tdProject.textContent = task.project_name || '-';
      const tdStatus = document.createElement('td');
      tdStatus.textContent = task.status || '-';
      const tdDue = document.createElement('td');
      tdDue.textContent = task.due_date_display || 'No due';
      const tdAction = document.createElement('td');
      tdAction.className = 'text-end';
      const action = document.createElement('a');
      action.href = task.url || '#';
      action.className = 'btn btn-outline-primary btn-sm';
      action.textContent = 'Open';
      tdAction.appendChild(action);
      tr.appendChild(tdTask);
      tr.appendChild(tdProject);
      tr.appendChild(tdStatus);
      tr.appendChild(tdDue);
      tr.appendChild(tdAction);
      state.tableBody.appendChild(tr);
    });
  }

  function showTaskSearchPanelForUser(user) {
    if (!user) return;
    const state = getTaskSearchPanelState();
    state.viewMode = detectActiveTaskResultView();
    state.user = user;
    state.page = 1;

    fetch(`/tasks/search/?${new URLSearchParams({ user_q: `@${user.username}` }).toString()}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).then((resp) => resp.json()).then((resp) => {
      if (!resp.success) {
        state.tasks = [];
      } else {
        state.tasks = Array.isArray(resp.results) ? resp.results : [];
      }
      state.panel.classList.remove('d-none');
      renderTaskSearchPanel(state);
      state.panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }).catch(() => {
      state.tasks = [];
      state.panel.classList.remove('d-none');
      renderTaskSearchPanel(state);
    });
  }

  function initTaskUserSearchWidgets() {
    const widgets = Array.from(document.querySelectorAll('[data-task-user-search-widget]'));
    if (!widgets.length) return;

    widgets.forEach((widget) => {
      const input = widget.querySelector('.task-user-search-input');
      const results = widget.querySelector('[data-task-user-search-results]');
      if (!input || !results) return;

      let timer = null;
      let requestToken = 0;
      let activeIndex = -1;
      let items = [];

      const hideResults = () => {
        results.classList.add('d-none');
        activeIndex = -1;
      };
      const showResults = () => results.classList.remove('d-none');
      const getQuery = () => (input.value || '').trim();
      const isMentionMode = () => getQuery().startsWith('@');

      function refreshInteractiveItems() {
        items = Array.from(results.querySelectorAll('.task-user-search-item'));
        activeIndex = items.length ? 0 : -1;
        items.forEach((el, idx) => el.classList.toggle('is-active', idx === activeIndex));
      }

      function setActiveIndex(nextIndex) {
        if (!items.length) return;
        if (nextIndex < 0) nextIndex = items.length - 1;
        if (nextIndex >= items.length) nextIndex = 0;
        activeIndex = nextIndex;
        items.forEach((el, idx) => el.classList.toggle('is-active', idx === activeIndex));
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
      }

      function renderEmpty(text) {
        results.innerHTML = `<div class="task-user-search-empty">${text}</div>`;
        refreshInteractiveItems();
        showResults();
      }

      function renderTaskItems(taskItems) {
        if (!taskItems.length) {
          renderEmpty('No matching tasks found.');
          return;
        }
        results.innerHTML = '';
        taskItems.slice(0, 12).forEach((item) => {
          const link = document.createElement('a');
          link.href = item.url || '#';
          link.className = 'task-user-search-item';
          link.setAttribute('data-item-type', 'task');
          const body = document.createElement('div');
          body.className = 'task-user-search-user-body';

          const title = document.createElement('div');
          title.className = 'task-user-search-item-title';
          title.textContent = item.title || '-';

          const meta = document.createElement('div');
          meta.className = 'task-user-search-item-meta';
          meta.textContent = `${item.project_name || '-'} | ${item.assignees_display || 'No assignee'} | ${item.status || '-'}`;

          body.appendChild(title);
          body.appendChild(meta);
          link.appendChild(body);
          results.appendChild(link);
        });
        refreshInteractiveItems();
        showResults();
      }

      function fetchTaskResults(query) {
        const token = ++requestToken;
        fetch(`/tasks/search/?${new URLSearchParams({ user_q: query }).toString()}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then((resp) => resp.json()).then((resp) => {
          if (token !== requestToken) return;
          if (!resp.success) {
            renderEmpty('Search failed.');
            return;
          }
          renderTaskItems(resp.results || []);
        }).catch(() => {
          if (token !== requestToken) return;
          renderEmpty('Search failed.');
        });
      }

      function applyUserSelection(user) {
        const mentionValue = `@${user.username}`;
        input.value = mentionValue;
        showTaskSearchPanelForUser(user);
        hideResults();
      }

      function renderUserItems(userItems) {
        if (!userItems.length) {
          renderEmpty('No matching users found.');
          return;
        }
        results.innerHTML = '';
        userItems.slice(0, 12).forEach((user) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'task-user-search-item task-user-search-user';
          button.setAttribute('data-item-type', 'user');
          button.setAttribute('aria-label', `Select ${user.username}`);

          const avatar = document.createElement('div');
          avatar.className = 'task-user-search-avatar';
          const initials = document.createElement('span');
          initials.className = 'task-user-search-avatar-initials';
          initials.textContent = getUserInitials(user);

          if (user.avatar_url) {
            const img = document.createElement('img');
            img.src = user.avatar_url;
            img.alt = user.username;
            img.className = 'task-user-search-avatar-img';
            img.addEventListener('error', () => {
              img.remove();
              avatar.appendChild(initials);
            });
            avatar.appendChild(img);
          } else {
            avatar.appendChild(initials);
          }

          const body = document.createElement('div');
          body.className = 'task-user-search-user-body';
          const title = document.createElement('div');
          title.className = 'task-user-search-item-title';
          title.textContent = user.full_name || user.username;

          const meta = document.createElement('div');
          meta.className = 'task-user-search-item-meta';
          meta.textContent = `${user.username}${user.email ? ` | ${user.email}` : ''}`;

          body.appendChild(title);
          body.appendChild(meta);
          button.appendChild(avatar);
          button.appendChild(body);
          button.addEventListener('click', () => applyUserSelection(user));
          button.addEventListener('mousemove', () => {
            const idx = items.indexOf(button);
            if (idx >= 0) setActiveIndex(idx);
          });
          results.appendChild(button);
        });
        refreshInteractiveItems();
        showResults();
      }

      function runSearch() {
        const rawQuery = getQuery();
        if (!rawQuery) {
          hideResults();
          return;
        }
        if (isMentionMode()) {
          const mentionQuery = normalizeMentionQuery(rawQuery);
          const token = ++requestToken;
          fetchUserMentionSuggestions(mentionQuery, {
            onSuccess: (userItems) => {
              if (token !== requestToken) return;
              renderUserItems(userItems);
            },
            onError: () => {
              if (token !== requestToken) return;
              renderEmpty('User search failed.');
            }
          });
          return;
        }
        fetchTaskResults(rawQuery);
      }

      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(runSearch, isMentionMode() ? 120 : 220);
      });

      input.addEventListener('focus', () => {
        if (!getQuery()) return;
        runSearch();
      });

      input.addEventListener('keydown', (event) => {
        if (results.classList.contains('d-none')) return;
        if (event.key === 'Escape') {
          event.preventDefault();
          hideResults();
          return;
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          setActiveIndex(activeIndex + 1);
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          setActiveIndex(activeIndex - 1);
          return;
        }
        if (event.key === 'Enter') {
          event.preventDefault();
          if (activeIndex >= 0 && items[activeIndex]) {
            items[activeIndex].click();
            return;
          }
          if (isMentionMode()) {
            fetchTaskResults(getQuery());
          }
        }
      });

      document.addEventListener('click', (event) => {
        if (!widget.contains(event.target)) hideResults();
      });
    });
  }

  function initTaskMentionFilterInputs() {
    const inputs = Array.from(document.querySelectorAll('input[data-mention-filter-input="assignee"]'));
    if (!inputs.length) return;

    inputs.forEach((input) => {
      if (input.dataset.mentionReady === '1') return;
      input.dataset.mentionReady = '1';

      const field = input.closest('.tf-field') || input.parentElement;
      if (!field) return;

      const results = document.createElement('div');
      results.className = 'task-user-search-results task-user-search-results-inline d-none';
      field.appendChild(results);

      let timer = null;
      let activeIndex = -1;
      let items = [];
      let requestToken = 0;

      const hideResults = () => {
        results.classList.add('d-none');
        activeIndex = -1;
      };
      const showResults = () => results.classList.remove('d-none');

      const refreshItems = () => {
        items = Array.from(results.querySelectorAll('.task-user-search-item'));
        activeIndex = items.length ? 0 : -1;
        items.forEach((el, idx) => el.classList.toggle('is-active', idx === activeIndex));
      };

      const setActive = (nextIndex) => {
        if (!items.length) return;
        if (nextIndex < 0) nextIndex = items.length - 1;
        if (nextIndex >= items.length) nextIndex = 0;
        activeIndex = nextIndex;
        items.forEach((el, idx) => el.classList.toggle('is-active', idx === activeIndex));
        items[activeIndex]?.scrollIntoView({ block: 'nearest' });
      };

      const renderEmpty = (text) => {
        results.innerHTML = `<div class="task-user-search-empty">${text}</div>`;
        refreshItems();
        showResults();
      };

      const applySelection = (user) => {
        const mentionValue = `@${user.username}`;
        input.value = mentionValue;
        const assigneeSelect = document.querySelector('#task-filter-form select[name="assignee"]');
        if (assigneeSelect) assigneeSelect.value = '';
        hideResults();
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
      };

      const renderUsers = (userItems) => {
        if (!userItems.length) {
          renderEmpty('No matching users found.');
          return;
        }
        results.innerHTML = '';
        userItems.slice(0, 10).forEach((user) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'task-user-search-item task-user-search-user';

          const avatar = document.createElement('div');
          avatar.className = 'task-user-search-avatar';
          const initials = document.createElement('span');
          initials.className = 'task-user-search-avatar-initials';
          initials.textContent = getUserInitials(user);
          if (user.avatar_url) {
            const img = document.createElement('img');
            img.src = user.avatar_url;
            img.alt = user.username;
            img.className = 'task-user-search-avatar-img';
            img.addEventListener('error', () => {
              img.remove();
              avatar.appendChild(initials);
            });
            avatar.appendChild(img);
          } else {
            avatar.appendChild(initials);
          }

          const body = document.createElement('div');
          body.className = 'task-user-search-user-body';
          const title = document.createElement('div');
          title.className = 'task-user-search-item-title';
          title.textContent = user.full_name || user.username;
          const meta = document.createElement('div');
          meta.className = 'task-user-search-item-meta';
          meta.textContent = `${user.username}${user.email ? ` | ${user.email}` : ''}`;

          body.appendChild(title);
          body.appendChild(meta);
          button.appendChild(avatar);
          button.appendChild(body);
          button.addEventListener('click', () => applySelection(user));
          button.addEventListener('mousemove', () => {
            const idx = items.indexOf(button);
            if (idx >= 0) setActive(idx);
          });
          results.appendChild(button);
        });
        refreshItems();
        showResults();
      };

      const runMentionSearch = () => {
        const value = (input.value || '').trim();
        if (!value.startsWith('@')) {
          hideResults();
          return;
        }
        const token = ++requestToken;
        const mentionQuery = normalizeMentionQuery(value);
        fetchUserMentionSuggestions(mentionQuery, {
          onSuccess: (userItems) => {
            if (token !== requestToken) return;
            renderUsers(userItems);
          },
          onError: () => {
            if (token !== requestToken) return;
            renderEmpty('User search failed.');
          }
        });
      };

      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(runMentionSearch, 120);
      });

      input.addEventListener('focus', () => {
        if ((input.value || '').trim().startsWith('@')) {
          runMentionSearch();
        }
      });

      input.addEventListener('keydown', (event) => {
        if (results.classList.contains('d-none')) return;
        if (event.key === 'Escape') {
          event.preventDefault();
          hideResults();
          return;
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          setActive(activeIndex + 1);
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          setActive(activeIndex - 1);
          return;
        }
        if (event.key === 'Enter' && activeIndex >= 0 && items[activeIndex]) {
          event.preventDefault();
          items[activeIndex].click();
        }
      });

      document.addEventListener('click', (event) => {
        if (!field.contains(event.target)) hideResults();
      });
    });
  }

  initTaskUserSearchWidgets();
  initTaskMentionFilterInputs();

  function initSidebarToggleDesktop() {
    const toggleBtn = document.getElementById('sidebarToggleDesktop');
    if (!toggleBtn) return;
    if (toggleBtn.dataset.initialized === '1') return;
    toggleBtn.dataset.initialized = '1';

    const stateKey = 'arva_sidebar_collapsed';
    const desktopQuery = window.matchMedia('(min-width: 992px)');
    const icon = toggleBtn.querySelector('i');

    function setCollapsed(collapsed) {
      document.body.classList.toggle('sidebar-collapsed', collapsed);
      toggleBtn.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
      toggleBtn.setAttribute('title', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      toggleBtn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      if (icon) {
        icon.classList.toggle('bi-list', !collapsed);
        icon.classList.toggle('bi-layout-sidebar-inset', collapsed);
      }
    }

    if (desktopQuery.matches && localStorage.getItem(stateKey) === '1') {
      setCollapsed(true);
    }

    toggleBtn.addEventListener('click', function() {
      if (!desktopQuery.matches) return;
      const collapsed = !document.body.classList.contains('sidebar-collapsed');
      setCollapsed(collapsed);
      localStorage.setItem(stateKey, collapsed ? '1' : '0');
    });

    const handleViewportChange = function(event) {
      if (!event.matches) {
        document.body.classList.remove('sidebar-collapsed');
      } else if (localStorage.getItem(stateKey) === '1') {
        document.body.classList.add('sidebar-collapsed');
      }
    };

    if (desktopQuery.addEventListener) {
      desktopQuery.addEventListener('change', handleViewportChange);
    } else if (desktopQuery.addListener) {
      desktopQuery.addListener(handleViewportChange);
    }
  }

  function initDualViewCollection(config) {
    const root = document.querySelector(config.rootSelector);
    if (!root) return;
    if (root.dataset.initialized === '1') return;
    root.dataset.initialized = '1';

    const state = { page: 1, perPage: 10 };
    const findEl = (selector) => root.querySelector(selector) || document.querySelector(selector);
    const searchInput = config.searchInputSelector ? findEl(config.searchInputSelector) : null;
    const perPageSelect = config.perPageSelector ? findEl(config.perPageSelector) : null;
    const prevButton = config.prevButtonSelector ? findEl(config.prevButtonSelector) : null;
    const nextButton = config.nextButtonSelector ? findEl(config.nextButtonSelector) : null;
    const countLabel = config.countLabelSelector ? findEl(config.countLabelSelector) : null;
    const summaryLabel = config.summarySelector ? findEl(config.summarySelector) : null;
    const paginationControls = config.paginationControlsSelector ? findEl(config.paginationControlsSelector) : null;
    const tableBody = config.tableBodySelector ? findEl(config.tableBodySelector) : null;
    const emptyTableRow = config.emptyTableRowSelector ? findEl(config.emptyTableRowSelector) : null;
    const cardItems = config.cardSelector ? Array.from(root.querySelectorAll(config.cardSelector)) : [];
    const extraFilters = (config.extraFilterSelectors || []).map((selector) => findEl(selector)).filter(Boolean);

    function getTableRows() {
      if (!tableBody) return [];
      return Array.from(tableBody.querySelectorAll(config.tableRowSelector));
    }

    function loadState() {
      try {
        const raw = localStorage.getItem(config.storageKey);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        const parsedPage = parseInt(parsed.page, 10);
        const parsedPerPage = parseInt(parsed.perPage, 10);
        if (Number.isInteger(parsedPage) && parsedPage > 0) state.page = parsedPage;
        if ([10, 25, 50, 100].includes(parsedPerPage)) state.perPage = parsedPerPage;
      } catch (e) {
        state.page = 1;
        state.perPage = 10;
      }
    }

    function saveState() {
      localStorage.setItem(config.storageKey, JSON.stringify(state));
    }

    function getFilterValues() {
      return {
        query: (searchInput?.value || '').trim().toLowerCase(),
        extras: extraFilters.map((control) => control.value || '')
      };
    }

    function apply() {
      const filterValues = getFilterValues();
      const filteredCards = cardItems.filter((item) => config.matchesFilters(item, filterValues));
      const filteredRows = getTableRows().filter((item) => config.matchesFilters(item, filterValues));
      const totalItems = filteredCards.length || filteredRows.length;
      const totalPages = Math.max(1, Math.ceil(totalItems / state.perPage));
      state.page = Math.max(1, Math.min(state.page, totalPages));

      const start = (state.page - 1) * state.perPage;
      const end = start + state.perPage;
      const visibleCards = filteredCards.slice(start, end);
      const visibleRows = filteredRows.slice(start, end);

      cardItems.forEach((item) => { item.style.display = 'none'; });
      visibleCards.forEach((item) => { item.style.display = ''; });

      getTableRows().forEach((item) => { item.style.display = 'none'; });
      visibleRows.forEach((item) => { item.style.display = ''; });

      if (countLabel) {
        countLabel.textContent = config.countText(totalItems);
      }
      if (summaryLabel) {
        summaryLabel.textContent = totalItems ? `Showing ${start + 1}-${Math.min(end, totalItems)} of ${totalItems}` : 'Showing 0 of 0';
      }
      if (prevButton) prevButton.disabled = state.page <= 1;
      if (nextButton) nextButton.disabled = state.page >= totalPages || totalItems === 0;
      if (paginationControls) paginationControls.classList.toggle('d-none', totalItems === 0);
      if (emptyTableRow) emptyTableRow.style.display = getTableRows().length ? 'none' : '';

      if (perPageSelect && String(state.perPage) !== perPageSelect.value) {
        perPageSelect.value = String(state.perPage);
      }
      saveState();
    }

    function sortTable(key, direction) {
      if (!tableBody || !config.getSortValue) return;
      const sorted = getTableRows().slice().sort((a, b) => {
        const aVal = config.getSortValue(a, key);
        const bVal = config.getSortValue(b, key);
        if (aVal < bVal) return direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return direction === 'asc' ? 1 : -1;
        return 0;
      });
      sorted.forEach((row) => tableBody.appendChild(row));
    }

    root.querySelectorAll(config.sortButtonSelector || '.sort-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.sortKey;
        const current = btn.dataset.sortDir || 'desc';
        const nextDir = current === 'asc' ? 'desc' : 'asc';

        root.querySelectorAll(config.sortButtonSelector || '.sort-btn').forEach((other) => {
          other.dataset.sortDir = '';
          other.classList.remove('active');
        });

        btn.dataset.sortDir = nextDir;
        btn.classList.add('active');
        sortTable(key, nextDir);
        apply();
      });
    });

    [searchInput, ...extraFilters].forEach((control) => {
      if (!control) return;
      const handler = () => {
        state.page = 1;
        apply();
      };
      control.addEventListener('input', handler);
      control.addEventListener('change', handler);
    });

    if (perPageSelect) {
      perPageSelect.addEventListener('change', () => {
        const next = parseInt(perPageSelect.value, 10);
        if (![10, 25, 50, 100].includes(next)) return;
        state.perPage = next;
        state.page = 1;
        apply();
      });
    }

    if (prevButton) {
      prevButton.addEventListener('click', () => {
        if (state.page <= 1) return;
        state.page -= 1;
        apply();
      });
    }
    if (nextButton) {
      nextButton.addEventListener('click', () => {
        state.page += 1;
        apply();
      });
    }

    loadState();
    apply();
  }

  function initProjectListPage() {
    initDualViewCollection({
      rootSelector: '#projectViewContent',
      storageKey: 'arva_project_list_paging',
      searchInputSelector: '#project-search',
      perPageSelector: '#project-per-page',
      prevButtonSelector: '#project-page-prev',
      nextButtonSelector: '#project-page-next',
      countLabelSelector: '#project-count',
      summarySelector: '#project-page-summary',
      paginationControlsSelector: '#project-pagination-controls',
      cardSelector: '.project-card-item',
      tableBodySelector: '#project-table tbody',
      tableRowSelector: 'tr[data-name]',
      emptyTableRowSelector: '#project-table tbody tr:not([data-name])',
      sortButtonSelector: '.sort-btn',
      matchesFilters: (el, filters) => {
        const text = `${el.dataset.name || ''} ${el.dataset.owner || ''} ${el.dataset.description || ''}`;
        return !filters.query || text.includes(filters.query);
      },
      countText: (totalItems) => `${totalItems} project${totalItems === 1 ? '' : 's'} found`,
      getSortValue: (row, key) => {
        if (key === 'summary') return `${row.dataset.name || ''} ${row.dataset.description || ''}`;
        if (key === 'owner') return row.dataset.owner || '';
        if (key === 'created') return row.dataset.created || '';
        if (key === 'progress') return parseInt(row.dataset.progress || '0', 10);
        return '';
      }
    });

    const privateToggle = document.getElementById('id_is_private');
    const sharingFields = document.getElementById('project-create-sharing-fields');
    const isProjectToggle = document.getElementById('id_is_project');
    const advancedFields = document.querySelectorAll('.project-advanced-fields');
    const startDateInput = document.getElementById('id_start_date');
    const startDateTbdInput = document.getElementById('id_start_date_tbd');
    const etdInput = document.getElementById('id_etd');
    if (privateToggle && sharingFields) {
      const sync = () => sharingFields.classList.toggle('d-none', !privateToggle.checked);
      privateToggle.addEventListener('change', sync);
      sync();
    }
    if (isProjectToggle) {
      const syncProjectFields = () => {
        const enabled = !!isProjectToggle.checked;
        advancedFields.forEach((el) => el.classList.toggle('d-none', !enabled));
      };
      isProjectToggle.addEventListener('change', syncProjectFields);
      syncProjectFields();
    }
    if (startDateInput && startDateTbdInput) {
      const syncStartDateTbd = () => {
        if (startDateTbdInput.checked) {
          startDateInput.value = '';
        }
        startDateInput.disabled = startDateTbdInput.checked;
      };
      startDateTbdInput.addEventListener('change', syncStartDateTbd);
      startDateInput.addEventListener('change', function() {
        if (startDateInput.value) startDateTbdInput.checked = false;
        syncStartDateTbd();
      });
      etdInput?.addEventListener('change', function() {
        if (startDateInput.value && etdInput.value && etdInput.value < startDateInput.value) {
          showError('ETD cannot be earlier than Start Date.');
          etdInput.value = '';
        }
      });
      syncStartDateTbd();
    }
  }

  function initSubprojectListPage() {
    initDualViewCollection({
      rootSelector: '#subprojectViewContent',
      storageKey: 'arva_subproject_list_paging',
      searchInputSelector: '#subproject-search',
      perPageSelector: '#subproject-per-page',
      prevButtonSelector: '#subproject-page-prev',
      nextButtonSelector: '#subproject-page-next',
      countLabelSelector: '#subproject-count',
      summarySelector: '#subproject-page-summary',
      paginationControlsSelector: '#subproject-pagination-controls',
      cardSelector: '.subproject-card-item',
      tableBodySelector: '#subproject-table tbody',
      tableRowSelector: 'tr[data-name]',
      emptyTableRowSelector: '#subproject-table tbody tr:not([data-name])',
      sortButtonSelector: '.sort-btn',
      matchesFilters: (el, filters) => {
        const text = `${el.dataset.name || ''} ${el.dataset.description || ''}`;
        return !filters.query || text.includes(filters.query);
      },
      countText: (totalItems) => `${totalItems} sub-project${totalItems === 1 ? '' : 's'} found`,
      getSortValue: (row, key) => {
        if (key === 'summary') return `${row.dataset.name || ''} ${row.dataset.description || ''}`;
        if (key === 'created') return row.dataset.created || '';
        if (key === 'progress') return parseInt(row.dataset.progress || '0', 10);
        return '';
      }
    });
  }

  function initMyCardsPage() {
    function getPriorityRank(value) {
      switch (value) {
        case 'critical': return 4;
        case 'high': return 3;
        case 'medium': return 2;
        case 'low': return 1;
        default: return 0;
      }
    }
    initDualViewCollection({
      rootSelector: '#myCardsViewContent',
      storageKey: 'arva_my_cards_paging',
      searchInputSelector: '#mycards-search',
      extraFilterSelectors: ['#mycards-priority', '#mycards-due'],
      perPageSelector: '#mycards-per-page',
      prevButtonSelector: '#mycards-page-prev',
      nextButtonSelector: '#mycards-page-next',
      countLabelSelector: '#mycards-count',
      summarySelector: '#mycards-page-summary',
      paginationControlsSelector: '#mycards-pagination-controls',
      cardSelector: '.mycard-card',
      tableBodySelector: '#mycards-table tbody',
      tableRowSelector: 'tr[data-task-id]',
      emptyTableRowSelector: '#mycards-table tbody tr:not([data-task-id])',
      sortButtonSelector: '.sort-btn',
      matchesFilters: (el, filters) => {
        const text = `${el.dataset.title || ''} ${el.dataset.project || ''} ${el.dataset.list || ''}`;
        const priority = filters.extras[0] || '';
        const due = filters.extras[1] || '';
        const matchesQuery = !filters.query || text.includes(filters.query);
        const matchesPriority = !priority || el.dataset.priority === priority;
        const matchesDue = !due || el.dataset.dueStatus === due;
        return matchesQuery && matchesPriority && matchesDue;
      },
      countText: (totalItems) => `${totalItems} task${totalItems === 1 ? '' : 's'} found`,
      getSortValue: (row, key) => {
        if (key === 'summary') return `${row.dataset.project || ''} ${row.dataset.list || ''} ${row.dataset.title || ''}`;
        if (key === 'priority') return getPriorityRank(row.dataset.priority || '');
        if (key === 'due') return row.dataset.dueDate || '';
        return row.dataset.title || '';
      }
    });
  }

  function initProjectArchivePage() {
    const input = document.getElementById('archive-user-search');
    const items = Array.from(document.querySelectorAll('.archived-task-item'));
    if (!input || !items.length) return;
    if (input.dataset.initialized === '1') return;
    input.dataset.initialized = '1';

    const applyArchiveFilter = () => {
      const q = (input.value || '').trim().toLowerCase();
      items.forEach((item) => {
        const text = `${item.dataset.title || ''} ${item.dataset.assignees || ''}`;
        item.style.display = !q || text.includes(q) ? '' : 'none';
      });
    };
    input.addEventListener('input', applyArchiveFilter);
    applyArchiveFilter();
  }

  function initUserListPage() {
    const table = document.getElementById('user-table');
    if (!table) return;
    if (table.dataset.initialized === '1') return;
    table.dataset.initialized = '1';

    const searchInput = document.getElementById('user-search');
    const activeSelect = document.getElementById('user-active');
    const staffSelect = document.getElementById('user-staff');
    const countLabel = document.getElementById('user-count');
    const rows = Array.from(document.querySelectorAll('#user-table tbody tr'));
    const cards = Array.from(document.querySelectorAll('.user-card'));
    const tableBody = document.querySelector('#user-table tbody');

    function matchesFilters(row, query, active, staff) {
      const text = `${row.dataset.username || ''} ${row.dataset.email || ''}`;
      const matchesQuery = !query || text.includes(query);
      const matchesActive = !active || row.dataset.active === active;
      const matchesStaff = !staff || row.dataset.staff === staff;
      return matchesQuery && matchesActive && matchesStaff;
    }

    function applyFilters() {
      const query = (searchInput?.value || '').trim().toLowerCase();
      const active = activeSelect?.value || '';
      const staff = staffSelect?.value || '';
      let visibleCount = 0;

      rows.forEach((row) => {
        const show = matchesFilters(row, query, active, staff);
        row.style.display = show ? '' : 'none';
        if (show) visibleCount += 1;
      });
      cards.forEach((card) => {
        const show = matchesFilters(card, query, active, staff);
        card.style.display = show ? '' : 'none';
      });
      if (countLabel) {
        countLabel.textContent = `${visibleCount} user${visibleCount === 1 ? '' : 's'} shown`;
      }
    }

    function getBoolRank(value) {
      return value === 'active' || value === 'staff' ? 1 : 0;
    }
    function getStatusRank(value) {
      if (value === 'online') return 3;
      if (value === 'offline') return 2;
      if (value === 'never') return 1;
      return 0;
    }

    function sortTable(key, direction) {
      if (!tableBody) return;
      const sorted = rows.slice().sort((a, b) => {
        let aVal = '';
        let bVal = '';
        if (key === 'user') { aVal = a.dataset.username || ''; bVal = b.dataset.username || ''; }
        else if (key === 'email') { aVal = a.dataset.email || ''; bVal = b.dataset.email || ''; }
        else if (key === 'active') { aVal = getBoolRank(a.dataset.active); bVal = getBoolRank(b.dataset.active); }
        else if (key === 'staff') { aVal = getBoolRank(a.dataset.staff); bVal = getBoolRank(b.dataset.staff); }
        else if (key === 'status') { aVal = getStatusRank(a.dataset.status); bVal = getStatusRank(b.dataset.status); }
        else if (key === 'joined') { aVal = a.dataset.joined || ''; bVal = b.dataset.joined || ''; }
        else if (key === 'last_activity') { aVal = a.dataset.lastActivity || ''; bVal = b.dataset.lastActivity || ''; }
        else if (key === 'last_login') { aVal = a.dataset.lastLogin || ''; bVal = b.dataset.lastLogin || ''; }
        if (aVal < bVal) return direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return direction === 'asc' ? 1 : -1;
        return 0;
      });
      sorted.forEach((row) => tableBody.appendChild(row));
    }

    [searchInput, activeSelect, staffSelect].forEach((control) => {
      if (!control) return;
      control.addEventListener('input', applyFilters);
      control.addEventListener('change', applyFilters);
    });

    document.querySelectorAll('.sort-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.sortKey;
        const current = btn.dataset.sortDir || 'desc';
        const nextDir = current === 'asc' ? 'desc' : 'asc';
        document.querySelectorAll('.sort-btn').forEach((other) => {
          other.dataset.sortDir = '';
          other.classList.remove('active');
        });
        btn.dataset.sortDir = nextDir;
        btn.classList.add('active');
        sortTable(key, nextDir);
      });
    });
    applyFilters();
  }

  function initUserSettingsPage() {
    const layoutBtn = document.getElementById('save-layout-pref');
    const themeBtn = document.getElementById('save-theme-pref');
    if (!layoutBtn && !themeBtn) return;

    const csrfToken = document.getElementById('layout-csrf')?.value || '';
    const layoutMsg = document.getElementById('layout-pref-msg');
    const themeMsg = document.getElementById('theme-pref-msg');
    const themeSelect = document.getElementById('theme-pref');
    const settingsRoot = document.querySelector('[data-user-settings-root]');
    const layoutUrl = settingsRoot?.dataset.layoutUrl || '/profile/layout/update/';
    const themeUrl = settingsRoot?.dataset.themeUrl || '/profile/theme/update/';

    layoutBtn?.addEventListener('click', function() {
      const selected = document.querySelector('input[name="layout"]:checked');
      if (!selected) return;
      fetch(layoutUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams({ layout: selected.value })
      }).then((res) => {
        if (!res.ok) throw new Error('Failed');
        return res.json();
      }).then((data) => {
        localStorage.setItem('arva_layout_preference', data.layout || selected.value);
        if (layoutMsg) layoutMsg.textContent = 'Saved. Reloading...';
        setTimeout(() => window.location.reload(), 250);
      }).catch(() => {
        if (layoutMsg) layoutMsg.textContent = 'Failed to save layout.';
      });
    });

    themeBtn?.addEventListener('click', function() {
      const theme = themeSelect?.value || 'inherit';
      fetch(themeUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams({ theme: theme })
      }).then((res) => {
        if (!res.ok) throw new Error('Failed');
        return res.json();
      }).then(() => {
        if (themeMsg) themeMsg.textContent = 'Saved. Reloading...';
        setTimeout(() => window.location.reload(), 250);
      }).catch(() => {
        if (themeMsg) themeMsg.textContent = 'Failed to save theme.';
      });
    });
  }

  function initWebsiteSettingsPage() {
    const themeInput = document.querySelector('[name="theme_mode"]');
    const primaryInput = document.querySelector('[name="primary_color"]');
    const textInput = document.querySelector('[name="text_color"]');
    const navbarInput = document.querySelector('[name="navbar_bg"]');
    const bodyInput = document.querySelector('[name="body_bg"]');
    if (!themeInput && !primaryInput) return;

    const root = document.documentElement;
    const setVar = (name, value) => { if (value) root.style.setProperty(name, value); };
    const bindLive = (input, cssVar) => {
      if (!input) return;
      const handler = () => setVar(cssVar, input.value);
      input.addEventListener('input', handler);
      input.addEventListener('change', handler);
      handler();
    };

    bindLive(primaryInput, '--primary-color');
    bindLive(textInput, '--text-color');
    bindLive(navbarInput, '--navbar-bg');
    bindLive(bodyInput, '--body-bg');

    if (themeInput) {
      const applyTheme = () => root.setAttribute('data-theme', themeInput.value || 'light');
      themeInput.addEventListener('change', applyTheme);
      applyTheme();
    }
  }

  function initProjectDetailPage() {
    const boardRoot = document.getElementById('task-board');
    if (!boardRoot) return;
    if (boardRoot.dataset.projectDetailInitialized === '1') return;
    boardRoot.dataset.projectDetailInitialized = '1';

    const storageKey = 'arva_project_detail_view_mode';
    const sortState = { key: '', dir: 'asc' };

    function getBoardRoot() {
      return document.getElementById('task-board');
    }

    function isProjectLocked() {
      const root = getBoardRoot();
      return (root?.dataset.isClosed || '0') === '1';
    }

    function syncListEmpty() {
      const root = getBoardRoot();
      if (!root) return;
      const rows = root.querySelectorAll('.task-list-row');
      const empty = root.querySelector('.task-list-empty');
      if (!empty) return;
      empty.classList.toggle('d-none', rows.length > 0);
    }

    function applyMode(mode) {
      const root = getBoardRoot();
      const cardPanel = root?.querySelector('.board-view-card');
      const listPanel = root?.querySelector('.board-view-list');
      if (!cardPanel || !listPanel) return;
      const isList = mode === 'list';
      cardPanel.classList.toggle('d-none', isList);
      listPanel.classList.toggle('d-none', !isList);
      document.querySelectorAll('[data-view-mode]').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.viewMode === mode);
      });
      localStorage.setItem(storageKey, mode);
      syncListEmpty();
    }

    function collectVisibleListOptions() {
      const root = getBoardRoot();
      if (!root) return [];
      return Array.from(root.querySelectorAll('.board-view-card .board-list[data-list-id]')).map((el) => {
        const listId = el.getAttribute('data-list-id');
        const titleEl = el.querySelector('.list-title');
        const name = (titleEl?.textContent || '').trim();
        return { id: listId, name: name || `List ${listId}` };
      });
    }

    function openListTaskCreateModal() {
      const root = getBoardRoot();
      if (isProjectLocked()) {
        showError('Project is closed. Re-open the project to make changes.');
        return;
      }
      const isStructuredProject = (root?.dataset.isProject || '0') === '1';
      const structuredOnlyFields = document.querySelectorAll('#listTaskCreateModal .task-structured-only');
      const statusSelect = document.getElementById('list-task-status');
      const form = document.getElementById('list-view-task-create-form');
      const assigneeSelect = document.getElementById('list-task-assignees');
      const startDateInput = document.getElementById('list-task-start-date');
      const startDateTbdInput = document.getElementById('list-task-start-date-tbd');
      const endDateInput = document.getElementById('list-task-end-date');
      const prioritySelect = document.getElementById('list-task-priority');
      const workStatusSelect = document.getElementById('list-task-work-status');
      const projectEtd = (root?.dataset.projectEtd || '').trim();
      if (!statusSelect || !form) return;
      form.reset();
      structuredOnlyFields.forEach((el) => el.classList.toggle('d-none', !isStructuredProject));
      statusSelect.innerHTML = '';
      if (startDateInput && startDateTbdInput) {
        startDateInput.disabled = false;
        startDateInput.required = false;
        startDateTbdInput.checked = false;
      }
      if (endDateInput) {
        endDateInput.required = false;
        endDateInput.removeAttribute('max');
      }
      if (prioritySelect) prioritySelect.required = false;
      if (workStatusSelect) workStatusSelect.required = false;
      if (assigneeSelect) {
        assigneeSelect.required = false;
        assigneeSelect.multiple = true;
        assigneeSelect.size = 4;
      }
      const options = collectVisibleListOptions();
      if (!options.length) {
        showError('No status/column available. Create a list first.');
        return;
      }
      options.forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt.id;
        option.textContent = opt.name;
        statusSelect.appendChild(option);
      });
      const defaultListId = window.currentStructuredDefaultListId || '';
      if (defaultListId) {
        statusSelect.value = defaultListId;
        window.currentStructuredDefaultListId = '';
      }

      if (isStructuredProject) {
        if (startDateInput) startDateInput.required = true;
        if (endDateInput) {
          endDateInput.required = true;
          if (projectEtd) endDateInput.max = projectEtd;
        }
        if (prioritySelect) prioritySelect.required = true;
        if (workStatusSelect) workStatusSelect.required = true;
        if (assigneeSelect) {
          assigneeSelect.required = true;
          assigneeSelect.multiple = false;
          assigneeSelect.size = 1;
        }
      }
      const modalEl = document.getElementById('listTaskCreateModal');
      if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    function getSortValue(row, key) {
      const value = row.dataset[key] || '';
      if (key === 'due') return value || '9999-12-31';
      return value;
    }

    function sortListRows(key) {
      const root = getBoardRoot();
      const body = root?.querySelector('#task-list-body');
      if (!body) return;
      const rows = Array.from(body.querySelectorAll('.task-list-row'));
      const nextDir = sortState.key === key && sortState.dir === 'asc' ? 'desc' : 'asc';
      sortState.key = key;
      sortState.dir = nextDir;
      rows.sort((a, b) => {
        const av = getSortValue(a, key);
        const bv = getSortValue(b, key);
        if (av < bv) return nextDir === 'asc' ? -1 : 1;
        if (av > bv) return nextDir === 'asc' ? 1 : -1;
        return 0;
      }).forEach((row) => body.appendChild(row));
      document.querySelectorAll('.task-list-sort').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.sortKey === key);
      });
    }

    window.applyProjectBoardViewMode = function() {
      const saved = localStorage.getItem(storageKey) || 'card';
      applyMode(saved);
    };
    window.applyProjectBoardViewMode();

    const projectPrivateInput = document.getElementById('project-edit-private');
    const projectSharingFields = document.querySelectorAll('.project-edit-sharing-fields');
    const projectIsProjectInput = document.getElementById('project-edit-is-project');
    const projectAdvancedFields = document.querySelectorAll('.project-edit-advanced-fields');
    const projectStartDateInput = document.getElementById('project-edit-start-date');
    const projectStartDateTbdInput = document.getElementById('project-edit-start-date-tbd');
    const projectEtdInput = document.getElementById('project-edit-etd');
    const syncProjectEditSharingVisibility = () => {
      if (!projectPrivateInput || !projectSharingFields.length) return;
      const show = projectPrivateInput.checked;
      projectSharingFields.forEach((el) => el.classList.toggle('d-none', !show));
    };
    if (projectPrivateInput) {
      projectPrivateInput.addEventListener('change', syncProjectEditSharingVisibility);
      syncProjectEditSharingVisibility();
    }
    if (projectIsProjectInput) {
      const syncEditProjectFields = () => {
        const enabled = !!projectIsProjectInput.checked;
        projectAdvancedFields.forEach((el) => el.classList.toggle('d-none', !enabled));
      };
      projectIsProjectInput.addEventListener('change', syncEditProjectFields);
      syncEditProjectFields();
    }
    if (projectStartDateInput && projectStartDateTbdInput) {
      const syncEditStartDateTbd = () => {
        if (projectStartDateTbdInput.checked) {
          projectStartDateInput.value = '';
        }
        projectStartDateInput.disabled = projectStartDateTbdInput.checked;
      };
      projectStartDateTbdInput.addEventListener('change', syncEditStartDateTbd);
      projectStartDateInput.addEventListener('change', function() {
        if (projectStartDateInput.value) projectStartDateTbdInput.checked = false;
        syncEditStartDateTbd();
      });
      projectEtdInput?.addEventListener('change', function() {
        if (projectStartDateInput.value && projectEtdInput.value && projectEtdInput.value < projectStartDateInput.value) {
          showError('ETD cannot be earlier than Start Date.');
          projectEtdInput.value = '';
        }
      });
      syncEditStartDateTbd();
    }

    document.addEventListener('click', function(e) {
      const modeBtn = e.target.closest('[data-view-mode]');
      if (modeBtn) applyMode(modeBtn.dataset.viewMode || 'card');

      const sortBtn = e.target.closest('.task-list-sort');
      if (sortBtn) sortListRows(sortBtn.dataset.sortKey || 'title');

      const listAddBtn = e.target.closest('.btn-list-add-task');
      if (listAddBtn) {
        if (isProjectLocked()) {
          showError('Project is closed. Re-open the project to make changes.');
          return;
        }
        window.currentStructuredDefaultListId = listAddBtn.dataset.defaultListId || '';
        openListTaskCreateModal();
      }
    });

    document.addEventListener('keydown', function(e) {
      const row = e.target.closest('.task-list-row');
      if (!row) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        row.click();
      }
    });

    const createForm = document.getElementById('list-view-task-create-form');
    const listStartDateInput = document.getElementById('list-task-start-date');
    const listStartDateTbdInput = document.getElementById('list-task-start-date-tbd');
    const listEndDateInput = document.getElementById('list-task-end-date');
    if (listStartDateInput && listStartDateTbdInput) {
      const syncListStartDateTbd = () => {
        if (listStartDateTbdInput.checked) {
          listStartDateInput.value = '';
        }
        listStartDateInput.disabled = listStartDateTbdInput.checked;
        listStartDateInput.required = !listStartDateTbdInput.checked && ((getBoardRoot()?.dataset.isProject || '0') === '1');
      };
      listStartDateTbdInput.addEventListener('change', syncListStartDateTbd);
      listStartDateInput.addEventListener('change', function() {
        if (listStartDateInput.value) listStartDateTbdInput.checked = false;
        syncListStartDateTbd();
      });
      syncListStartDateTbd();
    }
    createForm?.addEventListener('submit', function(e) {
      e.preventDefault();
      const root = getBoardRoot();
      if (isProjectLocked()) {
        return showError('Project is closed. Re-open the project to make changes.');
      }
      const projectId = root?.dataset.projectId;
      const isStructuredProject = (root?.dataset.isProject || '0') === '1';
      const projectEtd = (root?.dataset.projectEtd || '').trim();
      if (!projectId) return;

      const fd = new FormData(createForm);
      const title = (fd.get('title') || '').toString().trim();
      const listId = (fd.get('task_list_id') || '').toString();
      if (!title) return showError('Task title is required.');
      if (!listId) return showError('Please select a status/column.');
      const assignees = fd.getAll('assignees');
      const startDate = (fd.get('start_date') || '').toString();
      const startDateTbd = !!fd.get('start_date_tbd');
      const endDate = (fd.get('due_date') || '').toString();
      if (isStructuredProject) {
        if (!assignees.length) return showError('Assignee is required.');
        if (assignees.length > 1) return showError('Only one assignee is allowed.');
        if (!startDate && !startDateTbd) return showError('Start Date is required or mark it as TBD.');
        if (!endDate) return showError('End Date is required.');
        if (startDate && endDate && endDate < startDate) return showError('End Date cannot be earlier than Start Date.');
        if (projectEtd && endDate > projectEtd) return showError('End Date must not exceed project ETD.');
      }

      fetch(`/project/${projectId}/task/create/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': (document.querySelector('#list-view-task-create-form [name=csrfmiddlewaretoken]')?.value || ''),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: fd
      }).then((resp) => resp.json()).then((resp) => {
        if (!resp.success) {
          const firstError = resp?.errors ? Object.values(resp.errors)[0] : null;
          showError(firstError ? String(firstError).replace(/[\[\]']/g, '') : 'Failed to create task.');
          return;
        }
        const searchInput = document.querySelector('#task-filter-form input[name="q"]');
        if (window.$ && searchInput) {
          window.$(searchInput).trigger('keyup');
        } else {
          if (resp.html) {
            const col = document.querySelector(`.task-column[data-list-id="${resp.task_list_id}"]`);
            if (col) col.insertAdjacentHTML('beforeend', resp.html);
          }
          if (resp.list_row_html) {
            const body = document.getElementById('task-list-body');
            if (body) body.insertAdjacentHTML('beforeend', resp.list_row_html);
          }
        }
        const modalEl = document.getElementById('listTaskCreateModal');
        bootstrap.Modal.getInstance(modalEl)?.hide();
      }).catch(() => showError('Failed to create task.'));
    });
  }

  initSidebarToggleDesktop();
  initProjectListPage();
  initSubprojectListPage();
  initMyCardsPage();
  initProjectArchivePage();
  initUserListPage();
  initUserSettingsPage();
  initWebsiteSettingsPage();
  initProjectDetailPage();

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
          $('#id_is_private').trigger('change');
          $('#id_is_project').trigger('change');
          $('#id_start_date_tbd').trigger('change');
          const $convertSelect = $('#project-convert-target');
          if ($convertSelect.length && resp.project_id && resp.project_name) {
            $convertSelect.append(
              $('<option>').val(resp.project_id).text(resp.project_name)
            );
          }
        }
      },
      error: function() {
        const errors = arguments[0]?.responseJSON?.errors;
        if (errors) {
          const first = Object.values(errors)[0];
          showError(Array.isArray(first) ? first[0] : String(first));
          return;
        }
        showError('Failed to create project');
      }
    });
  });

  $(document).on("click", "#btn-edit-project", function() {
    $("#projectEditModal").modal("show");
  });

  $(document).on('click', '#btn-project-close-toggle', async function() {
    const btn = this;
    const projectId = btn.getAttribute('data-project-id');
    const nextAction = btn.getAttribute('data-next-action');
    if (!projectId || !nextAction) return;

    const isClose = nextAction === 'close';
    const confirmed = await showConfirm(
      isClose
        ? 'Close this project and lock all tasks as read-only?'
        : 'Re-open this project and allow task updates again?',
      isClose ? 'Close project' : 'Re-open project'
    );
    if (!confirmed) return;

    fetch(`/project/${projectId}/${isClose ? 'close' : 'reopen'}/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrftoken,
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).then((resp) => resp.json().then((data) => ({ ok: resp.ok, data })))
      .then(({ ok, data }) => {
        if (!ok || !data.success) {
          showError(data?.error || 'Failed to update project status.');
          return;
        }
        window.location.reload();
      }).catch(() => {
        showError('Failed to update project status.');
      });
  });

  $("#project-edit-form").on("submit", function(e) {
    e.preventDefault();
    const projectId = $("#task-board").data("project-id");

    $.post({
      url: `/project/${projectId}/edit/`,
      data: $(this).serialize(),
      success: function(resp) {
        if (resp.success) {
          $("#projectEditModal").modal("hide");
          // Refresh to ensure access badges and shared-user indicators stay in sync.
          window.location.reload();
        }
      },
      error: function() {
        const errors = arguments[0]?.responseJSON?.errors;
        if (errors) {
          const first = Object.values(errors)[0];
          showError(Array.isArray(first) ? first[0] : String(first));
          return;
        }
        showError("Failed to save changes.");
      }
    });
  });

  $(document).on('change', '#subproject-select', function() {
    const projectId = $(this).data('project-id');
    const subId = $(this).val();
    if (!projectId || !subId) return;
    if (subId === 'all') {
      window.location.href = `/project/${projectId}/?sub=all`;
    } else {
      window.location.href = `/project/${projectId}/?sub=${subId}`;
    }
  });

  $(document).on('click', '#btn-open-subproject-modal', function() {
    const form = $('#subproject-create-form');
    form[0].reset();
    $('#subprojectCreateModal').modal('show');
  });

  $(document).on('click', '#btn-edit-subproject', function() {
    const id = $(this).data('subproject-id');
    const name = $(this).data('subproject-name');
    const description = $(this).data('subproject-description') || '';

    $('#subproject-edit-id').val(id);
    $('#subproject-edit-name').val(name);
    $('#subproject-edit-description').val(description);
    $('#subprojectEditModal').modal('show');
  });

  $('#subproject-create-form').on('submit', function(e) {
    e.preventDefault();
    const $form = $(this);
    const projectId = $form.data('project-id');

    $.post({
      url: `/project/${projectId}/subproject/create/`,
      data: $form.serialize(),
      success: function(resp) {
        if (resp.success) {
          if ($('#subproject-list').length) {
            $('#subprojectCreateModal').modal('hide');
            $form[0].reset();
            refreshSubprojectList();
          } else {
            window.location.href = `/project/${projectId}/?sub=${resp.subproject_id}`;
          }
        }
      },
      error: function(xhr) {
        if (xhr.responseJSON && xhr.responseJSON.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError('Failed to create sub-project');
        }
      }
    });
  });

  $('#subproject-edit-form').on('submit', function(e) {
    e.preventDefault();
    const $form = $(this);
    const subId = $('#subproject-edit-id').val();
    const projectId = $('#task-board').data('project-id');

    $.post({
      url: `/subproject/${subId}/edit/`,
      data: $form.serialize(),
      success: function(resp) {
        if (resp.success) {
          $('#subprojectEditModal').modal('hide');
          if (projectId && subId) {
            window.location.href = `/project/${projectId}/?sub=${subId}`;
          }
        } else {
          showError('Failed to update sub-project.');
        }
      },
      error: function(xhr) {
        if (xhr.responseJSON && xhr.responseJSON.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError('Failed to update sub-project.');
        }
      }
    });
  });

  $(document).on('click', '#btn-delete-subproject', async function() {
    const subId = $(this).data('subproject-id');
    const projectId = $('#task-board').data('project-id');
    if (!subId || !projectId) return;

    if (!await showConfirm('Delete this sub-project? This will not remove tasks if any exist.', 'Delete sub-project')) return;

    $.post({
      url: `/subproject/${subId}/delete/`,
      success: function(resp) {
        if (resp.success) {
          if (resp.redirect_sub) {
            window.location.href = `/project/${projectId}/?sub=${resp.redirect_sub}`;
          } else {
            window.location.href = `/project/${projectId}/`;
          }
        } else {
          showError(resp.error || 'Failed to delete sub-project.');
        }
      },
      error: function(xhr) {
        if (xhr.responseJSON && xhr.responseJSON.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError('Failed to delete sub-project.');
        }
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

  $(document).on('submit', '.add-list-form-inline', function(e) {
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
          // Insert the new list before the add-list-column in the same group
          $(resp.html).insertBefore($form.closest('.add-list-column'));
          $form[0].reset();
          initSortable();
        }
      },
      error: function() {
        showError(arguments[0]?.responseJSON?.error || 'Failed to create list');
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
        showError(arguments[0]?.responseJSON?.error || 'Failed to delete list');
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
        showError(arguments[0]?.responseJSON?.error || 'Failed to archive list');
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
          showError('You do not have access to create tasks on this task.');
        } else if (xhr.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError('Failed to create task');
        }
      }
    });
  });

  function inlineUpdate(taskId, field, value, onSuccess, onError) {
    if (!taskId) {
      showError('Task ID not found on page. Please reload and try again.');
      if (typeof onError === 'function') onError();
      return;
    }
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
        } else {
          showError(resp.error || `Update failed for field "${field}".`);
          if (typeof onError === 'function') onError();
        }
      },
      error: function(xhr) {
        const serverMsg = xhr.responseJSON?.error || xhr.responseJSON?.detail;
        if (xhr.status === 0) {
          showError(`Network error while saving "${field}". Check your connection and try again.`);
        } else if (xhr.status === 401) {
          showError('Your session has expired. Please log in again.');
        } else if (xhr.status === 403) {
          showError(serverMsg || `Access denied: you cannot edit "${field}" on this task.`);
        } else if (xhr.status === 404) {
          showError(`Task not found (ID: ${taskId}). It may have been deleted.`);
        } else if (xhr.status === 400) {
          showError(serverMsg || `Invalid value for "${field}". Please check your input.`);
        } else if (xhr.status >= 500) {
          showError(serverMsg || `Server error (${xhr.status}) while saving "${field}". Please try again.`);
        } else {
          showError(serverMsg || `Failed to save "${field}" (HTTP ${xhr.status}).`);
        }
        if (typeof onError === 'function') onError();
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

  function renderTaskSkeleton() {
    return `
      <div class="task-skeleton">
        <div class="skel-line skel-title"></div>
        <div class="skel-line"></div>
        <div class="skel-line" style="width: 85%;"></div>
        <div class="skel-line skel-block"></div>
        <div class="skel-line" style="width: 40%;"></div>
      </div>
    `;
  }

  $(document).on('change', '#task-view-title', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'title', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-desc', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'description', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-due', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'due_date', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-priority', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'priority', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-status', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'status', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-start-date', function() {
        const taskId = getCurrentTaskId();
    inlineUpdate(taskId, 'start_date', $(this).val(), function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-start-date-tbd', function() {
    const taskId = getCurrentTaskId();
    const checkbox = this;
    const wasChecked = !checkbox.checked; // previous state (flipped by click)
    const isChecked = checkbox.checked;
    const $pill = $(checkbox).closest('.tbd-pill');
    const $dateInput = $('#task-view-start-date');

    // Instant visual feedback on the pill + date input.
    $pill.toggleClass('is-active', isChecked);
    if (isChecked) {
      $dateInput.val('').prop('disabled', true);
    } else {
      $dateInput.prop('disabled', false);
    }

    inlineUpdate(
      taskId,
      'start_date_tbd',
      isChecked ? '1' : '0',
      function() {
        loadTaskView(taskId);
      },
      function() {
        // Rollback UI if backend rejects so state stays consistent.
        checkbox.checked = wasChecked;
        $pill.toggleClass('is-active', wasChecked);
        if (wasChecked) {
          $dateInput.prop('disabled', true);
        } else {
          $dateInput.prop('disabled', false);
        }
      }
    );
  });

  $(document).on('change', '#task-view-assignees', function() {
        const taskId = getCurrentTaskId();
    const raw = $(this).val();
    const values = Array.isArray(raw) ? raw.join(',') : (raw || '');
    inlineUpdate(taskId, 'assignees', values, function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('change', '#task-view-labels', function() {
        const taskId = getCurrentTaskId();
    const values = $(this).val() ? $(this).val().join(',') : '';
    inlineUpdate(taskId, 'labels', values, function() {
      loadTaskView(taskId);
    });
  });

  $(document).on('click', '.cover-color-box', function() {
        const taskId = getCurrentTaskId();
    const color = $(this).data('color');
    inlineUpdate(taskId, 'cover_color', color, () => {
      loadTaskView(taskId);
    });
  });

  $(document).on('click', '.btn-view-task', function(e) {
    // Jika element adalah <a> tag, biarkan browser navigasi ke halaman task detail
    if (this.tagName === 'A') {
      return;
    }
    // Fallback untuk element non-anchor (legacy)
    e.preventDefault();
    const target = $(this).closest('[data-task-id]');
    const taskId = target.data('task-id');
    if (!taskId) return;

    $('#taskViewModal').data('task-id', taskId);

    $('#task-view-body').html(renderTaskSkeleton());
    $('#taskViewModal').modal('show');

    loadTaskView(taskId);
  });

  function getCurrentTaskId() {
    // Prefer modal context first (board/list view), then standalone task detail page.
    return $('#taskViewModal').data('task-id') || $('#task-view-body').data('task-id');
  }

  function loadTaskView(taskId) {
    if (!taskId) {
      showError('Task ID missing. Cannot reload task view.');
      return;
    }
    $.get(`/task/${taskId}/view/`, function(resp) {
      if (resp.success) {
        $('#task-view-body').html(resp.html);
        const scope = $('#taskViewModal').length ? $('#taskViewModal') : $('#task-view-body');
        autoResizeTextareas(scope);
      } else {
        $('#task-view-body').html('<div class="text-danger">You are not allowed to view this task.</div>');
      }
    }).fail(function(xhr) {
      if (xhr.status === 403) {
        $('#task-view-body').html('<div class="text-danger">You are not allowed to view this task.</div>');
      } else if (xhr.status === 404) {
        $('#task-view-body').html(`<div class="text-danger">Task not found (ID: ${taskId}).</div>`);
      } else {
        $('#task-view-body').html(`<div class="text-danger">Failed to load task (HTTP ${xhr.status}).</div>`);
      }
    });
  }

  function autoResizeTextareas($scope) {
    $scope.find('textarea[data-autoresize="true"]').each(function() {
      const el = this;
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight}px`;
    });
  }

  $(document).on('input', 'textarea[data-autoresize="true"]', function() {
    this.style.height = 'auto';
    this.style.height = `${this.scrollHeight}px`;
  });

  function loadProjectSubprojects(projectId, $select, selectedId, onDone) {
    if (!projectId || !$select) return;
    $.get(`/project/${projectId}/subprojects/`, function(resp) {
      if (!resp.success) return;
      $select.empty();
      if (resp.subprojects && resp.subprojects.length) {
        resp.subprojects.forEach((sp) => {
          const option = $('<option>').val(sp.id).text(sp.name);
          if (selectedId && String(sp.id) === String(selectedId)) {
            option.attr('selected', 'selected');
          }
          $select.append(option);
        });
      } else {
        $select.append($('<option>').val('').text('No sub-projects'));
      }
      if (typeof onDone === 'function') onDone(resp.subprojects || []);
    });
  }

  function loadProjectLists(projectId, $select, selectedId, subProjectId) {
    if (!projectId || !$select) return;
    $.get(`/project/${projectId}/lists/`, { sub_project_id: subProjectId || '' }, function(resp) {
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
    const $subSelect = $('#task-move-subproject');
    loadProjectSubprojects(projectId, $subSelect, null, function() {
      const subId = $subSelect.val();
      loadProjectLists(projectId, $listSelect, null, subId);
    });
  });

  $(document).on('change', '#task-move-subproject', function() {
    const projectId = $('#task-move-project').val();
    const subId = $(this).val();
    const $listSelect = $('#task-move-list');
    loadProjectLists(projectId, $listSelect, null, subId);
  });

  $(document).on('click', '#btn-move-task', function() {
    const taskId = $(this).data('task-id');
    const projectId = $('#task-move-project').val();
    const listId = $('#task-move-list').val();
    const subId = $('#task-move-subproject').val();
    if (!taskId || !projectId) return;

    $.post({
      url: `/task/${taskId}/transfer/`,
      data: {
        project_id: projectId,
        task_list_id: listId,
        sub_project_id: subId
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
    loadProjectSubprojects(projectId, $('#quick-move-subproject'), null, function() {
      const subId = $('#quick-move-subproject').val();
      loadProjectLists(projectId, $('#quick-move-list'), null, subId);
    });
    $modal.modal('show');
  });

  $(document).on('change', '#quick-move-project', function() {
    const projectId = $(this).val();
    loadProjectSubprojects(projectId, $('#quick-move-subproject'), null, function() {
      const subId = $('#quick-move-subproject').val();
      loadProjectLists(projectId, $('#quick-move-list'), null, subId);
    });
  });

  $(document).on('change', '#quick-move-subproject', function() {
    const projectId = $('#quick-move-project').val();
    const subId = $(this).val();
    loadProjectLists(projectId, $('#quick-move-list'), null, subId);
  });

  $(document).on('click', '#btn-quick-move-confirm', function() {
    const $modal = $('#taskMoveModal');
    const taskId = $modal.data('task-id');
    const projectId = $('#quick-move-project').val();
    const listId = $('#quick-move-list').val();
    const subId = $('#quick-move-subproject').val();
    if (!taskId || !projectId) return;

    $.post({
      url: `/task/${taskId}/transfer/`,
      data: {
        project_id: projectId,
        task_list_id: listId,
        sub_project_id: subId
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
        const taskId = getCurrentTaskId();
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
        } else if (xhr.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
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
        const taskId = getCurrentTaskId();

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
        const xhr = arguments[0];
        if (xhr?.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError("Failed to send reply.");
        }
      }
    });
  });

  $(document).on('click', '.btn-delete-comment', async function() {
    if (!await showConfirm("Delete this comment?", "Delete comment")) return;

    const commentId = $(this).data("id");
        const taskId = getCurrentTaskId();

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
        } else if (xhr.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError("Failed to delete comment.");
        }
      }
    });
  });

  $(document).on('click', '#btn-add-checkitem', async function() {
        const taskId = getCurrentTaskId();
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
        } else if (xhr.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError('Failed to add checklist.');
        }
      }
    });
  });

  $(document).on('change', '#task-view-checklist .checklist-toggle', function() {
    const li = $(this).closest('li');
    const itemId = li.data('id');
        const taskId = getCurrentTaskId();
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
        const taskId = getCurrentTaskId();
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

            const taskId = getCurrentTaskId();
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
        const taskId = getCurrentTaskId();

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
                        <tr data-user-id="${resp.user.id}"
                            data-username="${(resp.user.username || '').toLowerCase()}"
                            data-email="${(resp.user.email || '').toLowerCase()}"
                            data-active="active"
                            data-staff="non-staff"
                            data-last-activity=""
                            data-last-login=""
                            data-joined=""
                            data-status="never">
                          <td>${resp.user.username}</td>
                          <td>${resp.user.email}</td>
                          <td><span class="badge bg-success">Yes</span></td>
                          <td><span class="badge bg-secondary">No</span></td>
                          <td>-</td>
                          <td></td>
                          <td></td>
                          <td><span class="status-pill status-never">Never</span></td>
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

  function reloadProjectDetailBoard(resetPage = false) {
    const projectId = $('#task-board').data('project-id');
    if (!projectId || !$('#task-filter-form').length) return;

    const subProjectId = $('#task-board').data('subproject-id');
    const taskScope = $('#task-board').data('task-scope');
    if (resetPage) {
      $('#task-filter-page').val('1');
    }

    const params = new URLSearchParams($('#task-filter-form').serialize());
    const pageValue = ($('#task-filter-page').val() || '1').toString();
    const perPageValue = ($('#task-filter-per-page').val() || '25').toString();
    params.set('page', pageValue);
    params.set('per_page', perPageValue);

    if (taskScope === 'all') {
      params.set('sub', 'all');
    } else if (subProjectId) {
      params.set('sub', subProjectId);
    }

    $.get({
      url: `/project/${projectId}/`,
      data: params.toString(),
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      },
      success: function(resp) {
        $('#task-board-wrapper').html(resp.html);
        initSortable();
        if (typeof window.applyProjectBoardViewMode === 'function') {
          window.applyProjectBoardViewMode();
        }
      },
      error: function() {
        showError('Failed to apply filter');
      }
    });
  }

  $(document).on('change', '#task-filter-form select, #task-filter-form input[type="date"]', function() {
    reloadProjectDetailBoard(true);
  });

  $(document).on('keyup', '#task-filter-form input[type="text"]', function() {
    reloadProjectDetailBoard(true);
  });

  $(document).on('click', '.task-list-page-link', function() {
    const page = $(this).data('page');
    if (!page) return;
    $('#task-filter-page').val(page);
    reloadProjectDetailBoard(false);
  });

  $(document).on('change', '#task-list-per-page', function() {
    const perPage = ($(this).val() || '25').toString();
    $('#task-filter-per-page').val(perPage);
    $('#task-filter-page').val('1');
    reloadProjectDetailBoard(false);
  });

  $(document).on('click', '.btn-convert-subproject', function() {
    const projectId = $(this).data('project-id');
    const name = $(this).data('project-name');
    $('#project-convert-id').val(projectId);
    $('#projectConvertModal .modal-title').text(`Convert Project: ${name}`);
    const $select = $('#project-convert-target');
    $select.find('option').prop('disabled', false).show();
    $select.find(`option[value='${projectId}']`).prop('disabled', true).hide();
    if ($select.find('option:not([disabled])').length) {
      $select.val($select.find('option:not([disabled])').first().val());
    }
    $('#projectConvertModal').modal('show');
  });

  $('#project-convert-form').on('submit', function(e) {
    e.preventDefault();
    const projectId = $('#project-convert-id').val();
    const targetId = $('#project-convert-target').val();
    if (!projectId || !targetId) return;

    $.post({
      url: `/project/${projectId}/convert-subproject/`,
      data: { target_project_id: targetId },
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (resp.success) {
          $('#projectConvertModal').modal('hide');
          location.reload();
        } else {
          showError(resp.error || 'Failed to convert project.');
        }
      },
      error: function(xhr) {
        showError(xhr.responseJSON?.error || 'Failed to convert project.');
      }
    });
  });

  $(document).on('click', '.btn-move-subproject', function() {
    const subId = $(this).data('subproject-id');
    const name = $(this).data('subproject-name');
    $('#subproject-move-id').val(subId);
    $('#subprojectMoveModal .modal-title').text(`Move Sub-project: ${name}`);
    $('#subprojectMoveModal').modal('show');
  });

  $(document).on('click', '.btn-convert-subproject-project', function() {
    const subId = $(this).data('subproject-id');
    const name = $(this).data('subproject-name');
    $('#subproject-convert-id').val(subId);
    $('#subprojectConvertModal .modal-title').text(`Convert Sub-project: ${name}`);
    $('#subprojectConvertModal').modal('show');
  });

  $('#subproject-convert-form').on('submit', function(e) {
    e.preventDefault();
    const subId = $('#subproject-convert-id').val();
    if (!subId) return;

    $.post({
      url: `/subproject/${subId}/convert-project/`,
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (resp.success) {
          $('#subprojectConvertModal').modal('hide');
          if ($('#subproject-list').length) {
            refreshSubprojectList();
          } else if (resp.project_id) {
            window.location.href = `/project/${resp.project_id}/`;
          } else {
            location.reload();
          }
        } else {
          showError(resp.error || 'Failed to convert sub-project.');
        }
      },
      error: function(xhr) {
        showError(xhr.responseJSON?.error || 'Failed to convert sub-project.');
      }
    });
  });

  $('#subproject-move-form').on('submit', function(e) {
    e.preventDefault();
    const subId = $('#subproject-move-id').val();
    const projectId = $('#subproject-move-project').val();
    if (!subId || !projectId) return;

    $.post({
      url: `/subproject/${subId}/move/`,
      data: { project_id: projectId },
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (resp.success) {
          $('#subprojectMoveModal').modal('hide');
          if ($('#subproject-list').length) {
            refreshSubprojectList();
          } else {
            location.reload();
          }
        } else {
          showError(resp.error || 'Failed to move sub-project.');
        }
      },
      error: function(xhr) {
        showError(xhr.responseJSON?.error || 'Failed to move sub-project.');
      }
    });
  });


  function refreshSubprojectList() {
    const $list = $('#subproject-list');
    const $table = $('#subproject-table tbody');
    if (!$list.length || !$table.length) return;

    $.get(window.location.href, function(html) {
      const $html = $('<div>').append($.parseHTML(html));
      const $newList = $html.find('#subproject-list');
      const $newTableBody = $html.find('#subproject-table tbody');
      const $newCount = $html.find('#subproject-count');

      if ($newList.length) $list.html($newList.html());
      if ($newTableBody.length) $table.html($newTableBody.html());
      if ($newCount.length) $('#subproject-count').text($newCount.text());
    });
  }

  function reorderListsOnServer() {
    const projectId = $('#task-board').data('project-id');
    const subProjectId = $('#task-board').data('subproject-id');
    const orderedIds = [];
    $('#board-lists .board-list').each(function() {
      const id = $(this).data('list-id');
      if (id) orderedIds.push(id);
    });

    if (!orderedIds.length) return;

    $.post({
      url: `/project/${projectId}/list/reorder/`,
      data: {
        'ordered_ids[]': orderedIds,
        'sub_project_id': subProjectId || ''
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
    if ($('#board-lists').data('ui-sortable')) {
      $('#board-lists').sortable('destroy');
    }

    $('.task-column').each(function() {
      if ($(this).data('ui-sortable')) {
        $(this).sortable('destroy');
      }
    });

    const isClosed = String($('#task-board').data('is-closed') || '0') === '1';
    if (isClosed) return;

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
      tolerance: 'pointer',
      scroll: true,
      scrollSensitivity: 60,
      scrollSpeed: 18,
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
            } else if (xhr.status === 400 && xhr.responseJSON?.error) {
              showError(xhr.responseJSON.error);
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

// Settings Submenu Toggle with Smooth Dropdown
$(document).on('click', '#settings-menu-toggle', function(e) {
  e.preventDefault();
  e.stopPropagation();
  
  const $toggle = $(this);
  // Find the submenu within the SAME sidebar context (desktop or mobile offcanvas)
  const $sidebar = $toggle.closest('.sidebar-menu-group');
  const $submenu = $sidebar.find('.sidebar-submenu');
  
  // Toggle active class on parent link
  $toggle.toggleClass('active');
  
  // Toggle submenu visibility with smooth animation
  if ($submenu.hasClass('show')) {
    // Close submenu
    $submenu.removeClass('show');
  } else {
    // Open submenu - close other open submenus first
    $toggle.closest('.sidebar-nav, .offcanvas-body').find('.sidebar-submenu.show').not($submenu).removeClass('show');
    $toggle.closest('.sidebar-nav, .offcanvas-body').find('.sidebar-link.active').not($toggle).removeClass('active');
    
    // Open this submenu
    $submenu.addClass('show');
  }
});

// Prevent submenu link clicks from closing the submenu
$(document).on('click', '.sidebar-submenu-link', function(e) {
  // Allow normal navigation but keep submenu open during transition
  const $submenu = $(this).closest('.sidebar-submenu');
  setTimeout(function() {
    $submenu.addClass('show');
  }, 50);
});

// Close other submenus when one is opened (optional - for future expansion)
$(document).on('click', '.sidebar-link[id$="-toggle"]', function(e) {
  if (!$(this).attr('id').startsWith('settings-menu-toggle')) {
    // Close settings submenu if clicking other toggles in future
    $(this).closest('.sidebar-nav, .offcanvas-body').find('#settings-menu-toggle').removeClass('active');
    $(this).closest('.sidebar-nav, .offcanvas-body').find('#settings-submenu').removeClass('show');
  }
});

// Task card actions toggle - show on click, hide when clicking outside or another card
$(document).on('click', '.task-card', function(e) {
  // Don't toggle if clicking on buttons, links, or inside task-actions
  if ($(e.target).closest('button, a, .task-actions, input, textarea').length) {
    return;
  }
  
  // Remove show-actions from all other cards
  $('.task-card.show-actions').not(this).removeClass('show-actions');
  
  // Toggle show-actions on this card
  $(this).toggleClass('show-actions');
});

// Hide task actions when clicking outside task cards
$(document).on('click', function(e) {
  if (!$(e.target).closest('.task-card').length) {
    $('.task-card.show-actions').removeClass('show-actions');
  }
});
