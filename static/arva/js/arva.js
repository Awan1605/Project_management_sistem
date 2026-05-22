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

function showSuccess(message, title = 'Success') {
  if (typeof Swal !== 'undefined') {
    Swal.fire({
      icon: 'success',
      title: title,
      text: message,
      timer: 1800,
      showConfirmButton: false
    });
    return;
  }
  // Fallback when SweetAlert is unavailable.
  alert(message);
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

  function ensureNotificationEmptyState(dropdown) {
    const list = dropdown ? dropdown.querySelector('.js-notification-list') : null;
    if (!list) return;
    const hasNotificationItem = Boolean(list.querySelector('.js-notification-item'));
    if (hasNotificationItem) {
      const emptyNode = list.querySelector('.js-notification-empty');
      if (emptyNode) emptyNode.remove();
      return;
    }
    if (!list.querySelector('.js-notification-empty')) {
      const empty = document.createElement('div');
      empty.className = 'list-group-item border-0 small text-muted js-notification-empty';
      empty.textContent = 'No new notifications.';
      list.appendChild(empty);
    }
  }

  function decrementNotificationBadge(dropdown) {
    const badge = dropdown ? dropdown.querySelector('.js-notification-badge') : null;
    if (!badge) return;
    const current = Number.parseInt(badge.textContent || '0', 10);
    const next = Number.isFinite(current) ? Math.max(current - 1, 0) : 0;
    if (next <= 0) {
      badge.remove();
      return;
    }
    badge.textContent = String(next);
  }

  document.addEventListener('click', function (event) {
    const item = event.target.closest('.js-notification-item');
    if (!item) return;

    const markUrl = item.getAttribute('data-mark-read-url');
    const href = item.getAttribute('href') || '';
    if (!markUrl) return;

    event.preventDefault();
    item.classList.add('disabled');
    item.style.pointerEvents = 'none';

    fetch(markUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrftoken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
    }).finally(() => {
      const dropdown = item.closest('.js-notification-dropdown');
      item.remove();
      ensureNotificationEmptyState(dropdown);
      decrementNotificationBadge(dropdown);
      if (href) {
        window.location.href = href;
      }
    });
  });

  function parseTaskSortCreated(item) {
    const raw = (item.dataset.taskSortCreated || item.dataset.created || '').toString().trim();
    if (!raw) return 0;
    const asNumber = Number(raw);
    if (Number.isFinite(asNumber)) return asNumber;
    const asDate = Date.parse(raw);
    return Number.isFinite(asDate) ? asDate : 0;
  }

  function isTaskDoneForSort(item) {
    const raw = (item.dataset.taskSortDone || '').toString().trim();
    if (raw === '1') return true;
    if (raw === '0') return false;
    const status = (item.dataset.status || item.dataset.list || '').toString().trim().toLowerCase();
    return status === 'done';
  }

  function sortTaskItemsInContainer(container) {
    if (!container) return;
    const mode = (container.dataset.taskResultsSort || '').toLowerCase();
    if (!mode) return;
    const selector = container.dataset.taskResultsItem || '';
    if (!selector) return;
    const items = Array.from(container.querySelectorAll(selector));
    if (items.length < 2) return;

    items.sort((a, b) => {
      const doneA = isTaskDoneForSort(a) ? 1 : 0;
      const doneB = isTaskDoneForSort(b) ? 1 : 0;
      if (doneA !== doneB) return doneA - doneB;

      const createdA = parseTaskSortCreated(a);
      const createdB = parseTaskSortCreated(b);
      if (createdA !== createdB) return createdB - createdA;

      const idA = Number(a.dataset.taskId || 0);
      const idB = Number(b.dataset.taskId || 0);
      return idB - idA;
    });

    items.forEach((item) => {
      if (item.parentNode === container) {
        container.appendChild(item);
      }
    });
  }

  function applyTaskResultsSort(root = document) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-task-results-sort]').forEach((container) => {
      sortTaskItemsInContainer(container);
    });
  }

  function syncProjectDetailTaskResultsSortMode(mode) {
    const selectedMode = String(mode || 'default').trim().toLowerCase();
    const boardWrapper = document.getElementById('task-board-wrapper');
    if (!boardWrapper) return;
    const containers = boardWrapper.querySelectorAll('[data-task-results-item]');
    containers.forEach((container) => {
      const fallback = container.dataset.defaultTaskResultsSort || container.getAttribute('data-task-results-sort') || 'status-created-desc';
      container.dataset.defaultTaskResultsSort = fallback;
      if (selectedMode === 'default') {
        container.setAttribute('data-task-results-sort', fallback);
      } else {
        container.removeAttribute('data-task-results-sort');
      }
    });
    if (selectedMode === 'default') {
      applyTaskResultsSort(boardWrapper);
    }
  }

  function parseSortDateValue(raw) {
    if (raw === undefined || raw === null) return 0;
    const text = String(raw).trim();
    if (!text) return 0;
    if (/^\d+$/.test(text)) {
      const num = Number(text);
      return Number.isFinite(num) ? num : 0;
    }
    const parsed = Date.parse(text);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function getCollectionItemSortValue(item, key) {
    if (!item || !item.dataset) return '';
    const dataset = item.dataset;
    if (key === 'updated') {
      return dataset.updated || dataset.lastActivity || dataset.lastLogin || dataset.taskSortCreated || dataset.created || '';
    }
    if (key === 'due') {
      return dataset.due || dataset.dueDate || '';
    }
    if (key === 'title') {
      return dataset.title || dataset.name || dataset.username || dataset.email || '';
    }
    if (key === 'project') {
      return dataset.project || dataset.owner || dataset.name || '';
    }
    if (key === 'created') {
      return dataset.created || dataset.joined || dataset.taskSortCreated || '';
    }
    return dataset[key] || '';
  }

  function compareCollectionItemsByOrder(a, b, orderValue) {
    const value = String(orderValue || 'default').trim().toLowerCase();
    if (!value || value === 'default') return 0;
    const match = value.match(/^(.+?)_(asc|desc)$/);
    if (!match) return 0;
    const key = match[1];
    const dir = match[2] === 'asc' ? 1 : -1;
    const dateLikeKeys = new Set(['updated', 'due', 'created', 'joined', 'last_activity', 'last_login']);

    const aValRaw = getCollectionItemSortValue(a, key);
    const bValRaw = getCollectionItemSortValue(b, key);
    if (dateLikeKeys.has(key)) {
      const aVal = parseSortDateValue(aValRaw);
      const bVal = parseSortDateValue(bValRaw);
      if (aVal < bVal) return -1 * dir;
      if (aVal > bVal) return 1 * dir;
      return 0;
    }

    const aVal = String(aValRaw || '').toLowerCase();
    const bVal = String(bValRaw || '').toLowerCase();
    if (aVal < bVal) return -1 * dir;
    if (aVal > bVal) return 1 * dir;
    return 0;
  }

  function getDefaultOrderOptions() {
    return [
      { value: 'default', label: 'Default order' },
      { value: 'updated_desc', label: 'Recently updated' },
      { value: 'updated_asc', label: 'Oldest updated' },
      { value: 'due_asc', label: 'Due date (soonest)' },
      { value: 'due_desc', label: 'Due date (latest)' },
      { value: 'title_asc', label: 'Title (A-Z)' },
      { value: 'title_desc', label: 'Title (Z-A)' },
      { value: 'project_asc', label: 'Project (A-Z)' },
      { value: 'project_desc', label: 'Project (Z-A)' },
    ];
  }

  applyTaskResultsSort();

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

  function fetchUserMentionSuggestions(query, handlers, options = {}) {
    fetch(`/tasks/user-suggestions/?${new URLSearchParams({ q: query }).toString()}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: options.signal
    }).then((resp) => resp.json()).then((resp) => {
      if (!resp.success) {
        handlers.onError?.();
        return;
      }
      handlers.onSuccess?.(resp.results || []);
    }).catch(() => {
      if (options.signal?.aborted) return;
      handlers.onError?.();
    });
  }

  const TASK_RESULTS_VIEW_KEY = 'arva_task_user_results_view';
  const TASK_RESULTS_SORT_KEY = 'arva_task_user_results_sort';

  function normalizeTaskResultsView(value) {
    const raw = (value || '').toString().trim().toLowerCase();
    if (raw === 'list' || raw === 'table' || raw.includes('list') || raw.includes('table')) return 'list';
    if (raw === 'card' || raw === 'grid' || raw.includes('card') || raw.includes('grid')) return 'card';
    return '';
  }

  function resolveTaskResultsDefaultView() {
    const explicit = normalizeTaskResultsView(localStorage.getItem(TASK_RESULTS_VIEW_KEY));
    if (explicit) return explicit;

    const fallbackKeys = [
      'arva_project_detail_view_mode',
      'arva_my_cards_view',
      'arva_user_view',
      'arva_project_view',
      'arva_subproject_view',
    ];
    for (const key of fallbackKeys) {
      const normalized = normalizeTaskResultsView(localStorage.getItem(key));
      if (normalized) return normalized;
    }
    return 'list';
  }

  function getTaskSearchPanelHost() {
    return document.querySelector('.app-content') ||
      document.querySelector('main.container-fluid') ||
      document.querySelector('main') ||
      document.body;
  }

  function collectDefaultTaskContainers(state) {
    if (!state?.host) return [];
    return Array.from(state.host.children).filter((el) => el !== state.panel);
  }

  function setDefaultTaskContainersVisibility(state, visible) {
    if (!state) return;
    state.defaultContainers = collectDefaultTaskContainers(state);
    state.defaultContainers.forEach((container) => {
      container.classList.add('default-task-container');
      container.classList.toggle('is-hidden', !visible);
    });
  }

  function getTaskSearchPanelState() {
    if (window.__taskSearchPanelState) return window.__taskSearchPanelState;

    const host = getTaskSearchPanelHost();
    const panel = document.createElement('section');
    panel.id = 'task-user-results-panel';
    panel.className = 'task-user-results-panel search-task-container card shadow-sm border-0 h-100 mb-3 d-none';
    panel.innerHTML = `
      <div class="card-body">
      <div class="task-user-results-header">
        <div class="task-user-summary-card">
          <div class="task-user-summary-avatar">
            <img src="" alt="" data-task-user-results-avatar-img class="d-none">
            <span data-task-user-results-avatar-fallback>U</span>
          </div>
          <div class="task-user-summary-body">
            <div class="task-user-results-title">Showing tasks for:</div>
            <div class="task-user-results-user" data-task-user-results-user></div>
            <div class="task-user-results-email" data-task-user-results-email></div>
          </div>
        </div>
        <div class="task-user-results-actions">
          <div class="btn-group btn-group-sm" role="group" aria-label="Task result view mode">
            <button type="button" class="btn btn-outline-secondary" data-task-results-view="card"><i class="bi bi-grid-3x3-gap me-1"></i>Card View</button>
            <button type="button" class="btn btn-outline-secondary active" data-task-results-view="list"><i class="bi bi-list-ul me-1"></i>List View</button>
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm" data-task-results-reset>
            <i class="bi bi-x-circle me-1"></i>Reset Filter
          </button>
        </div>
      </div>
      <div class="task-user-results-toolbar">
        <div class="task-user-results-search">
          <i class="bi bi-search"></i>
          <input type="text" class="form-control form-control-sm" placeholder="Filter this user's tasks..." data-task-results-filter>
        </div>
        <select class="form-select form-select-sm" data-task-results-sort>
          <option value="default" selected>Default order</option>
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
      <div class="task-user-results-card-list"
           data-task-results-cards
           data-task-results-sort="status-created-desc"
           data-task-results-item=".task-user-result-card[data-task-id]"></div>
      <div class="task-user-results-list-shell d-none" data-task-results-table-wrap>
        <div class="task-user-results-list-head">
          <span>Priority / Status + Task</span>
          <span>Reporter / Assignee</span>
          <span>Start / End</span>
          <span class="text-end">Recent Activity</span>
        </div>
        <div class="task-user-results-list-body"
             data-task-results-table-body
             data-task-results-sort="status-created-desc"
             data-task-results-item=".task-user-result-list-row[data-task-id]"></div>
      </div>
      <div class="task-user-results-pagination d-none" data-task-results-pagination>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-task-results-prev><i class="bi bi-chevron-left"></i></button>
        <span data-task-results-page-info></span>
        <button type="button" class="btn btn-outline-secondary btn-sm" data-task-results-next><i class="bi bi-chevron-right"></i></button>
      </div>
      </div>
    `;
    host.prepend(panel);

    const state = {
      host,
      panel,
      user: null,
      tasks: [],
      filtered: [],
      defaultContainers: [],
      page: 1,
      perPage: 25,
      viewMode: resolveTaskResultsDefaultView(),
      isSearchActive: false,
      fetchController: null,
      loadedUserKey: '',
      loadedSortMode: '',
    };

    state.userLabel = panel.querySelector('[data-task-user-results-user]');
    state.userEmail = panel.querySelector('[data-task-user-results-email]');
    state.userAvatarImg = panel.querySelector('[data-task-user-results-avatar-img]');
    state.userAvatarFallback = panel.querySelector('[data-task-user-results-avatar-fallback]');
    state.userAvatarImg?.addEventListener('error', () => {
      state.userAvatarImg.classList.add('d-none');
      state.userAvatarFallback.classList.remove('d-none');
    });
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
    if (state.sortSelect) {
      const savedSort = (localStorage.getItem(TASK_RESULTS_SORT_KEY) || 'default').toLowerCase();
      if (Array.from(state.sortSelect.options).some((opt) => opt.value === savedSort)) {
        state.sortSelect.value = savedSort;
      } else {
        state.sortSelect.value = 'default';
      }
    }

    state.viewButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        state.viewMode = btn.dataset.taskResultsView === 'list' ? 'list' : 'card';
        localStorage.setItem(TASK_RESULTS_VIEW_KEY, state.viewMode);
        renderTaskSearchPanel(state);
      });
    });
    state.resetBtn?.addEventListener('click', () => {
      if (state.fetchController) {
        state.fetchController.abort();
        state.fetchController = null;
      }
      state.user = null;
      state.tasks = [];
      state.filtered = [];
      state.loadedUserKey = '';
      state.loadedSortMode = '';
      state.page = 1;
      state.filterInput.value = '';
      state.userLabel.textContent = '';
      state.userEmail.textContent = '';
      document.querySelectorAll('.task-user-search-input').forEach((el) => {
        el.value = '';
      });
      state.isSearchActive = false;
      setDefaultTaskContainersVisibility(state, true);
      panel.classList.add('d-none');
    });
    state.filterInput?.addEventListener('input', () => {
      state.page = 1;
      renderTaskSearchPanel(state);
    });
    state.sortSelect?.addEventListener('change', () => {
      localStorage.setItem(TASK_RESULTS_SORT_KEY, state.sortSelect.value || 'default');
      state.page = 1;
      fetchTaskSearchResultsForSelectedUser(state, { force: true, scrollIntoView: false });
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

  function createAvatarNode(userInfo, fallbackText, sizeClass = '') {
    const wrapper = document.createElement('span');
    wrapper.className = `task-result-avatar ${sizeClass}`.trim();
    const img = document.createElement('img');
    img.className = 'task-result-avatar-img';
    const initials = document.createElement('span');
    initials.className = 'task-result-avatar-fallback';
    initials.textContent = fallbackText || 'U';

    const avatarUrl = userInfo?.avatar_url || '';
    if (avatarUrl) {
      img.src = avatarUrl;
      img.alt = userInfo?.username || '';
      img.addEventListener('error', () => {
        img.remove();
        wrapper.appendChild(initials);
      });
      wrapper.appendChild(img);
    } else {
      wrapper.appendChild(initials);
    }
    return wrapper;
  }

  function buildPriorityChip(task) {
    const chip = document.createElement('span');
    const priorityCode = (task.priority || 'p2').toLowerCase();
    chip.className = `task-chip task-chip-priority task-chip-priority-${priorityCode}`;
    chip.textContent = task.priority_display || 'P2 - Medium';
    return chip;
  }

  function buildStatusChip(task) {
    const chip = document.createElement('span');
    const rawCode = (task.status_code || '').toLowerCase();
    const normalizedCode = rawCode || (String((task.status || '').toLowerCase()) === 'done' ? 'done' : '-');
    chip.className = `task-chip task-chip-status task-chip-status-${normalizedCode}`;
    chip.textContent = task.status || '-';
    return chip;
  }

  function buildDueBadge(task) {
    const wrap = document.createElement('span');
    if (!task.due_date_display || task.due_date_display === 'No due') {
      wrap.textContent = '-';
      return wrap;
    }
    const badge = document.createElement('span');
    badge.className = 'due-badge';
    const dueStatus = (task.due_status || 'none').toLowerCase();
    if (dueStatus === 'overdue') badge.classList.add('due-overdue');
    else if (dueStatus === 'today') badge.classList.add('due-today');
    else if (dueStatus === 'soon') badge.classList.add('due-soon');
    else badge.classList.add('bg-success', 'text-light');
    badge.textContent = task.due_date_display;
    wrap.appendChild(badge);
    return wrap;
  }

  function buildPersonMetaBlock(label, iconClass, personInfo, extraSuffix = '') {
    const item = document.createElement('div');
    item.className = 'task-structured-meta-item';

    const lbl = document.createElement('span');
    lbl.className = 'task-meta-label';
    lbl.innerHTML = `<i class="bi ${iconClass} me-1"></i>${label}`;

    const val = document.createElement('span');
    val.className = 'task-meta-value';
    const username = personInfo?.username || '-';
    const avatar = createAvatarNode(personInfo, personInfo?.initial || (username[0] || 'U'), 'sm');
    val.appendChild(avatar);
    const text = document.createElement('span');
    text.className = 'task-result-text-truncate';
    text.textContent = username;
    val.appendChild(text);
    if (extraSuffix) {
      const suffix = document.createElement('small');
      suffix.className = 'text-muted ms-1';
      suffix.textContent = extraSuffix;
      val.appendChild(suffix);
    }

    item.appendChild(lbl);
    item.appendChild(val);
    return item;
  }

  function timeSince(isoValue) {
    if (!isoValue) return '';
    const date = new Date(isoValue);
    if (Number.isNaN(date.getTime())) return '';
    const seconds = Math.max(1, Math.floor((Date.now() - date.getTime()) / 1000));
    const units = [
      { name: 'year', sec: 31536000 },
      { name: 'month', sec: 2592000 },
      { name: 'day', sec: 86400 },
      { name: 'hour', sec: 3600 },
      { name: 'minute', sec: 60 },
    ];
    for (const unit of units) {
      const value = Math.floor(seconds / unit.sec);
      if (value >= 1) return `${value} ${unit.name}${value > 1 ? 's' : ''}`;
    }
    return `${seconds} second${seconds > 1 ? 's' : ''}`;
  }

  function renderTaskSearchPanel(state) {
    if (!state?.panel) return;
    const query = (state.filterInput?.value || '').trim().toLowerCase();
    const activeSortMode = (state.sortSelect?.value || 'default').toLowerCase();

    const filtered = state.tasks.filter((task) => {
      if (!query) return true;
      const hay = `${task.title || ''} ${task.project_name || ''} ${task.status || ''} ${task.assignees_display || ''}`.toLowerCase();
      return hay.includes(query);
    });

    state.filtered = filtered;
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / state.perPage));
    state.page = Math.max(1, Math.min(state.page, totalPages));
    const start = (state.page - 1) * state.perPage;
    const end = start + state.perPage;
    const visible = filtered.slice(start, end);

    if (state.user) {
      const name = state.user.full_name || state.user.username || '-';
      const email = state.user.email || state.user.username || '-';
      state.userLabel.textContent = name;
      state.userEmail.textContent = email;
      state.userAvatarFallback.textContent = getUserInitials(state.user);
      if (state.user.avatar_url) {
        state.userAvatarImg.src = state.user.avatar_url;
        state.userAvatarImg.alt = name;
        state.userAvatarImg.classList.remove('d-none');
        state.userAvatarFallback.classList.add('d-none');
      } else {
        state.userAvatarImg.classList.add('d-none');
        state.userAvatarFallback.classList.remove('d-none');
      }
    } else {
      state.userLabel.textContent = '-';
      state.userEmail.textContent = '-';
      state.userAvatarImg.classList.add('d-none');
      state.userAvatarFallback.classList.remove('d-none');
      state.userAvatarFallback.textContent = 'U';
    }
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
    if (activeSortMode === 'default') {
      state.cardList.setAttribute('data-task-results-sort', 'status-created-desc');
      state.tableBody.setAttribute('data-task-results-sort', 'status-created-desc');
    } else {
      state.cardList.removeAttribute('data-task-results-sort');
      state.tableBody.removeAttribute('data-task-results-sort');
    }
    visible.forEach((task) => {
      const card = document.createElement('a');
      card.href = task.url || '#';
      card.className = 'task-user-result-card task-card shadow-sm text-decoration-none';
      card.setAttribute('data-search-task-link', '1');
      card.setAttribute('aria-label', `Open task ${task.title || ''}`);
      card.dataset.taskId = String(task.id || '');
      card.dataset.taskSortDone = (String((task.status_code || '').toLowerCase()) === 'done') ? '1' : '0';
      card.dataset.taskSortCreated = task.created_at ? String(Date.parse(task.created_at) || 0) : '0';

      const cardBody = document.createElement('div');
      cardBody.className = 'card-body p-3';

      const chipRow = document.createElement('div');
      chipRow.className = 'd-flex flex-wrap gap-1 justify-content-start mb-2';
      chipRow.appendChild(buildPriorityChip(task));
      chipRow.appendChild(buildStatusChip(task));

      const cardTitle = document.createElement('div');
      cardTitle.className = 'fw-bold font-size-95 task-card-title-main';
      cardTitle.textContent = task.title || '-';

      const metaGrid = document.createElement('div');
      metaGrid.className = 'task-structured-meta mt-2';
      const assigneeSuffix = task.assignee?.extra_count ? `+${task.assignee.extra_count}` : '';
      metaGrid.appendChild(buildPersonMetaBlock('Reporter', 'bi-person-circle', task.reporter));
      metaGrid.appendChild(buildPersonMetaBlock('Assignee', 'bi-person-badge', task.assignee, assigneeSuffix));

      const startItem = document.createElement('div');
      startItem.className = 'task-structured-meta-item';
      startItem.innerHTML = `<span class="task-meta-label"><i class="bi bi-play-circle me-1"></i>Start Date</span>`;
      const startValue = document.createElement('span');
      startValue.className = 'task-meta-value';
      startValue.textContent = task.start_date_tbd ? 'TBD' : (task.start_date_display || '-');
      startItem.appendChild(startValue);
      metaGrid.appendChild(startItem);

      const endItem = document.createElement('div');
      endItem.className = `task-structured-meta-item ${task.due_status === 'overdue' ? 'text-danger fw-semibold' : (task.due_status === 'today' ? 'text-warning-emphasis fw-semibold' : '')}`.trim();
      endItem.innerHTML = `<span class="task-meta-label"><i class="bi bi-calendar-check me-1"></i>End Date</span>`;
      const endValue = document.createElement('span');
      endValue.className = 'task-meta-value';
      endValue.appendChild(buildDueBadge(task));
      endItem.appendChild(endValue);
      metaGrid.appendChild(endItem);

      const subMeta = document.createElement('div');
      subMeta.className = 'task-result-project-line mt-2';
      const projectBadge = document.createElement('span');
      projectBadge.className = 'badge bg-light text-dark border';
      projectBadge.textContent = task.project_name || '-';
      subMeta.appendChild(projectBadge);
      if (task.task_list_name) {
        const listBadge = document.createElement('span');
        listBadge.className = 'badge bg-light text-dark border ms-1';
        listBadge.textContent = task.task_list_name;
        subMeta.appendChild(listBadge);
      }

      const cardFoot = document.createElement('div');
      cardFoot.className = 'mt-3 d-flex justify-content-between align-items-center task-actions';
      const activity = document.createElement('small');
      activity.className = 'text-muted';
      activity.textContent = task.updated_at ? `${timeSince(task.updated_at)} ago` : '';
      const go = document.createElement('span');
      go.className = 'btn btn-outline-primary btn-sm';
      go.textContent = 'Open';
      cardFoot.appendChild(activity);
      cardFoot.appendChild(go);
      cardBody.appendChild(chipRow);
      cardBody.appendChild(cardTitle);
      cardBody.appendChild(metaGrid);
      cardBody.appendChild(subMeta);
      cardBody.appendChild(cardFoot);
      card.appendChild(cardBody);
      state.cardList.appendChild(card);

      const row = document.createElement('a');
      row.href = task.url || '#';
      row.className = 'task-user-result-list-row task-list-row text-decoration-none';
      row.setAttribute('data-search-task-link', '1');
      row.setAttribute('aria-label', `Open task ${task.title || ''}`);
      row.dataset.taskId = String(task.id || '');
      row.dataset.taskSortDone = (String((task.status_code || '').toLowerCase()) === 'done') ? '1' : '0';
      row.dataset.taskSortCreated = task.created_at ? String(Date.parse(task.created_at) || 0) : '0';

      const rowMain = document.createElement('div');
      rowMain.className = 'task-row-main';
      const rowChips = document.createElement('div');
      rowChips.className = 'task-row-sub';
      rowChips.appendChild(buildPriorityChip(task));
      rowChips.appendChild(buildStatusChip(task));
      const rowTitle = document.createElement('div');
      rowTitle.className = 'task-row-title';
      rowTitle.textContent = task.title || '-';
      const rowSub = document.createElement('div');
      rowSub.className = 'task-row-sub';
      const pBadge = document.createElement('span');
      pBadge.className = 'badge bg-light text-dark border';
      pBadge.textContent = task.project_name || '-';
      rowSub.appendChild(pBadge);
      if (task.task_list_name) {
        const lBadge = document.createElement('span');
        lBadge.className = 'badge bg-light text-dark border';
        lBadge.textContent = task.task_list_name;
        rowSub.appendChild(lBadge);
      }
      rowMain.appendChild(rowChips);
      rowMain.appendChild(rowTitle);
      rowMain.appendChild(rowSub);

      const rowMeta = document.createElement('div');
      rowMeta.className = 'task-row-meta';
      const rowMetaGrid = document.createElement('div');
      rowMetaGrid.className = 'task-structured-list-meta';
      rowMetaGrid.appendChild(buildPersonMetaBlock('Reporter', 'bi-person-circle', task.reporter));
      rowMetaGrid.appendChild(buildPersonMetaBlock('Assignee', 'bi-person-badge', task.assignee, assigneeSuffix));
      rowMeta.appendChild(rowMetaGrid);

      const rowDue = document.createElement('div');
      rowDue.className = 'task-row-due';
      const rowDueGrid = document.createElement('div');
      rowDueGrid.className = 'task-structured-list-meta';
      const rowStart = document.createElement('span');
      rowStart.innerHTML = `<span class="task-meta-label"><i class="bi bi-play-circle me-1"></i>Start Date</span><span class="task-meta-value">${task.start_date_tbd ? 'TBD' : (task.start_date_display || '-')}</span>`;
      const rowEnd = document.createElement('span');
      rowEnd.className = task.due_status === 'overdue' ? 'text-danger fw-semibold' : (task.due_status === 'today' ? 'text-warning-emphasis fw-semibold' : '');
      const rowEndLabel = document.createElement('span');
      rowEndLabel.className = 'task-meta-label';
      rowEndLabel.innerHTML = '<i class="bi bi-calendar-check me-1"></i>End Date';
      const rowEndValue = document.createElement('span');
      rowEndValue.className = 'task-meta-value';
      rowEndValue.appendChild(buildDueBadge(task));
      rowEnd.appendChild(rowEndLabel);
      rowEnd.appendChild(rowEndValue);
      rowDueGrid.appendChild(rowStart);
      rowDueGrid.appendChild(rowEnd);
      rowDue.appendChild(rowDueGrid);

      const rowActivity = document.createElement('div');
      rowActivity.className = 'task-row-activity';
      rowActivity.innerHTML = `<span class="activity-dot"></span><small class="text-muted">${task.updated_at ? `${timeSince(task.updated_at)} ago` : ''}</small>`;

      row.appendChild(rowMain);
      row.appendChild(rowMeta);
      row.appendChild(rowDue);
      row.appendChild(rowActivity);
      state.tableBody.appendChild(row);
    });
    if (activeSortMode === 'default') {
      applyTaskResultsSort(state.panel);
    }
  }

  function fetchTaskSearchResultsForSelectedUser(state, options = {}) {
    if (!state?.user) return;
    const force = !!options.force;
    const scrollIntoView = options.scrollIntoView !== false;
    const sortMode = (state.sortSelect?.value || 'default').toLowerCase();
    const userKey = String(state.user.id || state.user.username || '').toLowerCase();
    if (!force && state.loadedUserKey === userKey && state.loadedSortMode === sortMode && Array.isArray(state.tasks) && state.tasks.length) {
      setDefaultTaskContainersVisibility(state, false);
      state.isSearchActive = true;
      state.panel.classList.remove('d-none');
      renderTaskSearchPanel(state);
      return;
    }

    if (state.fetchController) {
      state.fetchController.abort();
    }
    state.fetchController = new AbortController();
    const params = new URLSearchParams({
      user_q: state.user.username || state.user.email || '',
      sort: sortMode || 'default',
    });

    fetch(`/tasks/search/?${params.toString()}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: state.fetchController.signal
    }).then((resp) => resp.json()).then((resp) => {
      state.fetchController = null;
      state.tasks = resp.success && Array.isArray(resp.results) ? resp.results : [];
      state.loadedUserKey = userKey;
      state.loadedSortMode = sortMode;
      setDefaultTaskContainersVisibility(state, false);
      state.isSearchActive = true;
      state.panel.classList.remove('d-none');
      renderTaskSearchPanel(state);
      if (scrollIntoView) {
        state.panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
      }
    }).catch(() => {
      if (state.fetchController?.signal?.aborted) return;
      state.fetchController = null;
      state.tasks = [];
      state.loadedUserKey = userKey;
      state.loadedSortMode = sortMode;
      setDefaultTaskContainersVisibility(state, false);
      state.isSearchActive = true;
      state.panel.classList.remove('d-none');
      renderTaskSearchPanel(state);
    });
  }

  function showTaskSearchPanelForUser(user) {
    if (!user) return;
    const state = getTaskSearchPanelState();
    state.viewMode = normalizeTaskResultsView(localStorage.getItem(TASK_RESULTS_VIEW_KEY)) || state.viewMode || 'list';
    state.user = user;
    state.page = 1;
    fetchTaskSearchResultsForSelectedUser(state, { force: false, scrollIntoView: true });
  }

  function initTaskUserSearchWidgets() {
    const widgets = Array.from(document.querySelectorAll('[data-task-user-search-widget]'));
    if (!widgets.length) return;

    widgets.forEach((widget) => {
      const input = widget.querySelector('.task-user-search-input');
      const results = widget.querySelector('[data-task-user-search-results]');
      if (!input || !results) return;

      let timer = null;
      let activeIndex = -1;
      let items = [];
      let usersCache = [];
      let lastSearchedKey = null;
      let suggestionsController = null;

      const hideResults = () => {
        results.classList.add('d-none');
        activeIndex = -1;
      };
      const showResults = () => results.classList.remove('d-none');
      const getQuery = () => (input.value || '').trim();

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

      function applyUserSelection(user) {
        input.value = user.username || '';
        showTaskSearchPanelForUser(user);
        hideResults();
      }

      function renderUserItems(userItems) {
        if (!userItems.length) {
          renderEmpty('No matching users found.');
          return;
        }
        results.innerHTML = '';
        usersCache = userItems.slice(0, 12);
        usersCache.forEach((user, idx) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'task-user-search-item task-user-search-user';
          button.setAttribute('data-item-type', 'user');
          button.setAttribute('data-user-index', String(idx));
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
          results.appendChild(button);
        });
        refreshInteractiveItems();
        showResults();
      }

      function runSearch() {
        const rawQuery = getQuery();
        if (!rawQuery) {
          if (suggestionsController) {
            suggestionsController.abort();
            suggestionsController = null;
          }
          usersCache = [];
          lastSearchedKey = null;
          hideResults();
          return;
        }
        const mentionQuery = normalizeMentionQuery(rawQuery);
        const queryKey = mentionQuery.toLowerCase();
        if (queryKey === lastSearchedKey) return;
        lastSearchedKey = queryKey;
        if (suggestionsController) {
          suggestionsController.abort();
        }
        suggestionsController = new AbortController();
        fetchUserMentionSuggestions(mentionQuery, {
          onSuccess: (userItems) => {
            renderUserItems(userItems);
          },
          onError: () => {
            renderEmpty('User search failed.');
          }
        }, { signal: suggestionsController.signal });
      }

      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(runSearch, 140);
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
            const idx = parseInt(items[activeIndex].dataset.userIndex || '-1', 10);
            if (Number.isInteger(idx) && idx >= 0 && usersCache[idx]) {
              applyUserSelection(usersCache[idx]);
            }
          } else {
            const firstBtn = items[0];
            const idx = firstBtn ? parseInt(firstBtn.dataset.userIndex || '-1', 10) : -1;
            if (Number.isInteger(idx) && idx >= 0 && usersCache[idx]) {
              applyUserSelection(usersCache[idx]);
            }
          }
        }
      });

      results.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-user-index]');
        if (!trigger) return;
        const idx = parseInt(trigger.dataset.userIndex || '-1', 10);
        if (!Number.isInteger(idx) || idx < 0 || !usersCache[idx]) return;
        event.preventDefault();
        applyUserSelection(usersCache[idx]);
      });

      results.addEventListener('mousemove', (event) => {
        const trigger = event.target.closest('[data-user-index]');
        if (!trigger) return;
        const idx = parseInt(trigger.dataset.userIndex || '-1', 10);
        if (Number.isInteger(idx) && idx >= 0) setActiveIndex(idx);
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
      let mentionController = null;
      let lastMentionKey = null;

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
          if (mentionController) {
            mentionController.abort();
            mentionController = null;
          }
          lastMentionKey = null;
          hideResults();
          return;
        }
        const mentionQuery = normalizeMentionQuery(value);
        const mentionKey = mentionQuery.toLowerCase();
        if (mentionKey === lastMentionKey) return;
        lastMentionKey = mentionKey;
        if (mentionController) {
          mentionController.abort();
        }
        mentionController = new AbortController();
        fetchUserMentionSuggestions(mentionQuery, {
          onSuccess: (userItems) => {
            renderUsers(userItems);
          },
          onError: () => {
            renderEmpty('User search failed.');
          }
        }, { signal: mentionController.signal });
      };

      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(runMentionSearch, 120);
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

  document.addEventListener('click', function(event) {
    const link = event.target.closest('.search-task-container [data-search-task-link]');
    if (!link || !(link instanceof HTMLAnchorElement)) return;
    if (event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.location.assign(link.href);
  });

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

    const allowedPerPage = Array.isArray(config.allowedPerPage) && config.allowedPerPage.length
      ? config.allowedPerPage.map((v) => parseInt(v, 10)).filter((v) => Number.isInteger(v) && v > 0)
      : [10, 25, 50, 100];
    const defaultPerPage = allowedPerPage.includes(parseInt(config.defaultPerPage, 10))
      ? parseInt(config.defaultPerPage, 10)
      : allowedPerPage[0];
    const state = { page: 1, perPage: defaultPerPage, order: 'default' };
    const findEl = (selector) => root.querySelector(selector) || document.querySelector(selector);
    const searchInput = config.searchInputSelector ? findEl(config.searchInputSelector) : null;
    const perPageSelect = config.perPageSelector ? findEl(config.perPageSelector) : null;
    const prevButton = config.prevButtonSelector ? findEl(config.prevButtonSelector) : null;
    const nextButton = config.nextButtonSelector ? findEl(config.nextButtonSelector) : null;
    const countLabel = config.countLabelSelector ? findEl(config.countLabelSelector) : null;
    const summaryLabel = config.summarySelector ? findEl(config.summarySelector) : null;
    const paginationControls = config.paginationControlsSelector ? findEl(config.paginationControlsSelector) : null;
    const orderSelect = config.orderSelectSelector ? findEl(config.orderSelectSelector) : null;
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
        if (allowedPerPage.includes(parsedPerPage)) state.perPage = parsedPerPage;
        const parsedOrder = String(parsed.order || 'default').trim().toLowerCase();
        state.order = parsedOrder || 'default';
      } catch (e) {
        state.page = 1;
        state.perPage = defaultPerPage;
        state.order = 'default';
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
      if (state.order && state.order !== 'default') {
        filteredCards.sort((a, b) => compareCollectionItemsByOrder(a, b, state.order));
        filteredRows.sort((a, b) => compareCollectionItemsByOrder(a, b, state.order));
      }

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
      if (orderSelect && orderSelect.value !== state.order) {
        orderSelect.value = state.order;
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

    function resetToDefaultOrder() {
      root.querySelectorAll(config.sortButtonSelector || '.sort-btn').forEach((btn) => {
        btn.dataset.sortDir = '';
        btn.classList.remove('active');
      });
      applyTaskResultsSort(tableBody || root);
      applyTaskResultsSort(root);
      state.page = 1;
      state.order = 'default';
      apply();
    }

    root.querySelectorAll(config.sortButtonSelector || '.sort-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.sortKey;
        const current = btn.dataset.sortDir || '';
        const nextDir = current === '' ? 'asc' : (current === 'asc' ? 'desc' : '');

        root.querySelectorAll(config.sortButtonSelector || '.sort-btn').forEach((other) => {
          other.dataset.sortDir = '';
          other.classList.remove('active');
        });

        if (nextDir) {
          btn.dataset.sortDir = nextDir;
          btn.classList.add('active');
          sortTable(key, nextDir);
        } else {
          applyTaskResultsSort(tableBody || root);
          applyTaskResultsSort(root);
        }
        apply();
      });
    });

    if (paginationControls) {
      const actionsHost = paginationControls.querySelector('.page-pagination-right') || paginationControls;
      if (actionsHost && orderSelect && !orderSelect.dataset.orderOptionsReady) {
        const options = config.orderOptions || getDefaultOrderOptions();
        orderSelect.innerHTML = '';
        options.forEach((opt) => {
          const option = document.createElement('option');
          option.value = opt.value;
          option.textContent = opt.label;
          orderSelect.appendChild(option);
        });
        orderSelect.dataset.orderOptionsReady = '1';
      }
    }

    if (orderSelect) {
      orderSelect.addEventListener('change', () => {
        state.order = (orderSelect.value || 'default').toLowerCase();
        state.page = 1;
        apply();
      });
    }

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
        if (!allowedPerPage.includes(next)) return;
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
    applyTaskResultsSort(tableBody || root);
    apply();
  }

  function initProjectListPage() {
    initDualViewCollection({
      rootSelector: '#projectViewContent',
      storageKey: 'arva_project_list_paging',
      searchInputSelector: '#project-search',
      perPageSelector: '#project-per-page',
      orderSelectSelector: '#project-order',
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
      orderSelectSelector: '#subproject-order',
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
      allowedPerPage: [25, 50, 100],
      defaultPerPage: 25,
      perPageSelector: '#mycards-per-page',
      orderSelectSelector: '#mycards-order',
      prevButtonSelector: '#mycards-page-prev',
      nextButtonSelector: '#mycards-page-next',
      countLabelSelector: '#mycards-count',
      summarySelector: '#mycards-page-summary',
      paginationControlsSelector: '#mycards-pagination-controls',
      cardSelector: '.mycard-card',
      tableBodySelector: '#mycards-list-body',
      tableRowSelector: '.task-user-result-list-row[data-task-id]',
      emptyTableRowSelector: '#mycards-list-body .mycards-empty-row',
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

    function resetToDefaultOrder() {
      document.querySelectorAll('.sort-btn').forEach((btn) => {
        btn.dataset.sortDir = '';
        btn.classList.remove('active');
      });
      applyTaskResultsSort(tableBody);
      applyTaskResultsSort(document.getElementById('user-card-view'));
      applyFilters();
    }

    [searchInput, activeSelect, staffSelect].forEach((control) => {
      if (!control) return;
      control.addEventListener('input', applyFilters);
      control.addEventListener('change', applyFilters);
    });

    document.querySelectorAll('.sort-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.sortKey;
        const current = btn.dataset.sortDir || '';
        const nextDir = current === '' ? 'asc' : (current === 'asc' ? 'desc' : '');
        document.querySelectorAll('.sort-btn').forEach((other) => {
          other.dataset.sortDir = '';
          other.classList.remove('active');
        });
        if (nextDir) {
          btn.dataset.sortDir = nextDir;
          btn.classList.add('active');
          sortTable(key, nextDir);
        } else {
          applyTaskResultsSort(tableBody);
          applyTaskResultsSort(document.getElementById('user-card-view'));
        }
        applyFilters();
      });
    });
    const userPagination = document.getElementById('user-pagination-controls');
    applyTaskResultsSort(tableBody);
    applyTaskResultsSort(document.getElementById('user-card-view'));
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
      const listInput = document.getElementById('list-task-list-id');
      const listLabel = document.getElementById('list-task-list-label');
      const form = document.getElementById('list-view-task-create-form');
      const assigneeSelect = document.getElementById('list-task-assignees');
      const startDateInput = document.getElementById('list-task-start-date');
      const startDateTbdInput = document.getElementById('list-task-start-date-tbd');
      const endDateInput = document.getElementById('list-task-end-date');
      const prioritySelect = document.getElementById('list-task-priority');
      const workStatusSelect = document.getElementById('list-task-work-status');
      const projectEtd = (root?.dataset.projectEtd || '').trim();
      if (!listInput || !form) return;
      form.reset();
      const descRoot = form.querySelector('[data-task-rich-editor]');
      const descInput = descRoot?.querySelector('[data-editor-input]');
      const descTextarea = descRoot?.querySelector('[data-editor-textarea]');
      if (descInput) {
        descInput.innerHTML = '<p><br></p>';
      }
      if (descTextarea) {
        descTextarea.value = '';
      }
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
      let selectedListId = window.currentStructuredDefaultListId || '';
      const listExists = options.some((opt) => String(opt.id) === String(selectedListId));
      if (!selectedListId || !listExists) {
        selectedListId = options[0].id;
      }
      listInput.value = selectedListId;
      const selectedList = options.find((opt) => String(opt.id) === String(selectedListId));
      if (listLabel) {
        listLabel.textContent = selectedList?.name || '-';
      }
      window.currentStructuredDefaultListId = '';

      if (isStructuredProject) {
        if (startDateInput) startDateInput.required = true;
        if (endDateInput) {
          endDateInput.required = true;
          if (projectEtd) endDateInput.max = projectEtd;
        }
        if (prioritySelect) prioritySelect.value = 'p2';
        if (workStatusSelect) workStatusSelect.value = '-';
        if (assigneeSelect) {
          assigneeSelect.required = true;
          assigneeSelect.multiple = false;
          assigneeSelect.size = 1;
        }
      } else {
        if (prioritySelect) prioritySelect.value = 'p2';
        if (workStatusSelect) workStatusSelect.value = '-';
      }
      const modalEl = document.getElementById('listTaskCreateModal');
      if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    function getSortValue(row, key) {
      const value = row.dataset[key] || '';
      if (key === 'due') return value || '9999-12-31';
      return value;
    }

    function applyTaskListOrder(orderValue) {
      const root = getBoardRoot();
      const body = root?.querySelector('#task-list-body');
      if (!body) return;
      const value = String(orderValue || 'default').trim().toLowerCase();
      if (!value || value === 'default') {
        applyTaskResultsSort(body);
        sortState.key = '';
        sortState.dir = '';
        document.querySelectorAll('.task-list-sort').forEach((btn) => btn.classList.remove('active'));
        return;
      }
      const match = value.match(/^(.+?)_(asc|desc)$/);
      if (!match) return;
      const key = match[1];
      const dir = match[2];
      sortState.key = key;
      sortState.dir = dir;
      const rows = Array.from(body.querySelectorAll('.task-list-row'));
      rows.sort((a, b) => {
        const av = getSortValue(a, key);
        const bv = getSortValue(b, key);
        if (av < bv) return dir === 'asc' ? -1 : 1;
        if (av > bv) return dir === 'asc' ? 1 : -1;
        return 0;
      }).forEach((row) => body.appendChild(row));
      document.querySelectorAll('.task-list-sort').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.sortKey === key);
      });
    }

    function sortListRows(key) {
      const root = getBoardRoot();
      const body = root?.querySelector('#task-list-body');
      if (!body) return;
      const rows = Array.from(body.querySelectorAll('.task-list-row'));
      const isSameKey = sortState.key === key;
      const nextDir = !isSameKey ? 'asc' : (sortState.dir === 'asc' ? 'desc' : (sortState.dir === 'desc' ? '' : 'asc'));
      sortState.key = nextDir ? key : '';
      sortState.dir = nextDir;
      if (!nextDir) {
        applyTaskListOrder('default');
        const orderSelect = document.getElementById('task-list-order');
        if (orderSelect) orderSelect.value = 'default';
        return;
      }
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
      const orderSelect = document.getElementById('task-list-order');
      if (orderSelect) {
        const optionValue = `${key}_${nextDir}`;
        if (Array.from(orderSelect.options).some((opt) => opt.value === optionValue)) {
          orderSelect.value = optionValue;
        } else {
          orderSelect.value = 'default';
        }
      }
    }

    window.applyProjectBoardViewMode = function() {
      const saved = localStorage.getItem(storageKey) || 'card';
      applyMode(saved);
    };
    window.applyProjectBoardViewMode();

    const taskListOrderSelect = document.getElementById('task-list-order');
    if (taskListOrderSelect) {
      const hiddenSortInput = document.getElementById('task-filter-sort');
      const currentOrder = (hiddenSortInput?.value || '').toLowerCase();
      const savedOrder = (localStorage.getItem('arva_project_detail_list_order') || 'default').toLowerCase();
      const initialOrder = Array.from(taskListOrderSelect.options).some((opt) => opt.value === currentOrder) ? currentOrder : savedOrder;
      if (Array.from(taskListOrderSelect.options).some((opt) => opt.value === initialOrder)) {
        taskListOrderSelect.value = initialOrder;
      } else {
        taskListOrderSelect.value = 'default';
      }
      if (hiddenSortInput) hiddenSortInput.value = taskListOrderSelect.value;
      syncProjectDetailTaskResultsSortMode(taskListOrderSelect.value);
    }

    $(document).on('change', '#task-list-order', function() {
      const selected = ($(this).val() || 'default').toString();
      localStorage.setItem('arva_project_detail_list_order', selected);
      $('#task-filter-sort').val(selected);
      reloadProjectDetailBoard(true);
    });

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

      const createDescRoot = createForm.querySelector('[data-task-rich-editor]');
      const createDescEditor = createDescRoot?.querySelector('[data-editor-input]');
      const createDescTextarea = createDescRoot?.querySelector('[data-editor-textarea]');
      if (createDescEditor && createDescTextarea) {
        createDescTextarea.value = sanitizeRichEditorHtml(createDescEditor.innerHTML || '');
      }

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
            if (col) {
              col.insertAdjacentHTML('beforeend', resp.html);
              applyTaskResultsSort(col);
            }
          }
          if (resp.list_row_html) {
            const body = document.getElementById('task-list-body');
            if (body) {
              body.insertAdjacentHTML('beforeend', resp.list_row_html);
              applyTaskResultsSort(body);
            }
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
  initTaskRichEditors($(document));

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
          applyTaskResultsSort(document.getElementById('projectViewContent'));
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
          applyTaskResultsSort(column.get(0));
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
          if (resp.task) {
            updateTaskDetailUI(resp.task);
          }
          if (typeof onSuccess === 'function') onSuccess(resp);
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

  function resolveStageStatusCode(stageName) {
    const name = String(stageName || '').trim().toLowerCase();
    if (name === 'done') return 'done';
    if (name === 'in progress') return 'in_progress';
    if (name === 'infeasible') return 'infeasible';
    return 'active';
  }

  function updateNonProjectStageBadges(stageName) {
    const code = resolveStageStatusCode(stageName);
    const $overview = $('#task-overview-status-badge');
    if ($overview.length) {
      $overview.attr('class', `task-chip task-chip-status task-chip-status-${code}`);
      $overview.text(stageName || '-');
    }
    const $inline = $('#task-stage-active-badge');
    if ($inline.length) {
      $inline.attr('class', `task-chip task-chip-status task-chip-status-${code}`);
      $inline.text(stageName || '-');
    }
  }

  function moveTaskCardToListColumn(taskId, listId) {
    const $card = $(`.task-card[data-task-id='${taskId}']`);
    const $targetColumn = $(`.task-column[data-list-id='${listId}']`);
    if (!$card.length || !$targetColumn.length) return;
    const $oldColumn = $card.closest('.task-column');
    $card.appendTo($targetColumn);
    if ($oldColumn.length && typeof checkEmptyState === 'function') checkEmptyState($oldColumn);
    if (typeof checkEmptyState === 'function') checkEmptyState($targetColumn);
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
    inlineUpdate(taskId, 'description', $(this).val());
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

  $(document).on('change', '#task-view-stage', function() {
    const taskId = getCurrentTaskId();
    const $select = $(this);
    const previousValue = ($select.data('prev') || '').toString();
    const nextValue = $select.val();
    const nextLabel = $select.find('option:selected').text().trim();
    const prevLabel = previousValue ? $select.find(`option[value="${previousValue}"]`).text().trim() : '';
    if (!taskId || !nextValue) return;
    if (previousValue && String(previousValue) === String(nextValue)) return;

    $select.prop('disabled', true).addClass('is-updating');
    updateNonProjectStageBadges(nextLabel);

    $.post({
      url: `/task/${taskId}/move/`,
      data: { task_list_id: nextValue },
      headers: { "X-CSRFToken": csrftoken },
      success: function(resp) {
        if (!resp.success) {
          updateNonProjectStageBadges(prevLabel);
          $select.val(previousValue);
          showError(resp.error || 'Failed to update stage.');
          return;
        }
        $select.data('prev', nextValue);
        moveTaskCardToListColumn(taskId, nextValue);
        if ($('#task-board').length && typeof reloadProjectDetailBoard === 'function') {
          reloadProjectDetailBoard(false);
        }
        showSuccess('Task stage updated.');
      },
      error: function(xhr) {
        if (previousValue) {
          updateNonProjectStageBadges(prevLabel);
          $select.val(previousValue);
        }
        const msg = xhr.responseJSON?.error || 'Failed to update stage.';
        showError(msg);
      },
      complete: function() {
        $select.prop('disabled', false).removeClass('is-updating');
      }
    });
  });

  $(document).on('focus mousedown', '#task-view-stage', function() {
    $(this).data('prev', $(this).val() || '');
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
    if (typeof ensureTaskCommentPasteTask === 'function') {
      ensureTaskCommentPasteTask(taskId);
    }
    const isTaskDetailPage = !$('#taskViewModal').length && !!$('#task-view-body').length;
    const query = isTaskDetailPage ? '?detail_read_only=1' : '';
    $.get(`/task/${taskId}/view/${query}`, function(resp) {
      if (resp.success) {
        hideMentionMenu();
        if (typeof resetAllReplyDrafts === 'function') {
          resetAllReplyDrafts();
        }
        $('#task-view-body').html(resp.html);
        if (typeof resetTaskCommentPasteState === 'function') {
          resetTaskCommentPasteState(taskId);
        }
        const scope = $('#taskViewModal').length ? $('#taskViewModal') : $('#task-view-body');
        autoResizeTextareas(scope);
        initTaskRichEditors(scope);
        const $stage = $('#task-view-stage');
        if ($stage.length) {
          $stage.data('prev', $stage.val() || '');
          const label = $stage.find('option:selected').text().trim();
          updateNonProjectStageBadges(label);
        }
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

  function updateTaskDetailUI(taskData) {
    if (!taskData || typeof taskData !== 'object') return;
    const $title = $('#task-overview-title');
    if ($title.length && taskData.title !== undefined) {
      $title.text(taskData.title || '');
      if (document.title && document.title.includes(' - ')) {
        const parts = document.title.split(' - ');
        const suffix = parts.length > 1 ? parts.slice(1).join(' - ') : '';
        if (suffix) document.title = `${taskData.title || ''} - ${suffix}`;
      }
    }

    const $status = $('#task-overview-status-badge');
    if ($status.length && taskData.status) {
      const code = (taskData.status.code || 'active').toString().toLowerCase();
      $status.attr('class', `task-chip task-chip-status task-chip-status-${code}`);
      $status.text(taskData.status.label || '-');
    }

    const $priority = $('#task-overview-priority-badge');
    if ($priority.length && taskData.priority) {
      const pCode = (taskData.priority.code || 'p2').toString().toLowerCase();
      $priority.attr('class', `task-chip task-chip-priority task-chip-priority-${pCode}`);
      $priority.text(taskData.priority.label || 'P2 - Medium');
    }

    const renderPerson = (person) => {
      if (!person || !person.username) return '<span class="text-muted">-</span>';
      const safeName = $('<div>').text(person.username).html();
      const initial = $('<div>').text((person.initial || 'U').toString().slice(0, 1).toUpperCase()).html();
      if (person.avatar_url) {
        const safeUrl = $('<div>').text(person.avatar_url).html();
        return `<img src="${safeUrl}" class="assignee-avatar" alt="${safeName}"><span class="text-truncate">${safeName}</span>`;
      }
      return `<span class="assignee-avatar-fallback">${initial}</span><span class="text-truncate">${safeName}</span>`;
    };

    const $reporter = $('#task-overview-reporter');
    if ($reporter.length && taskData.reporter) {
      $reporter.html(renderPerson(taskData.reporter));
    }

    const $assignee = $('#task-overview-assignee');
    if ($assignee.length) {
      if (Array.isArray(taskData.assignees) && taskData.assignees.length) {
        const listHtml = taskData.assignees.map((person) => {
          const personHtml = renderPerson(person);
          return `<span class="d-inline-flex align-items-center gap-1 me-2 mb-1">${personHtml}</span>`;
        }).join('');
        $assignee.html(`<div class="d-flex flex-wrap gap-1">${listHtml}</div>`);
      } else if (taskData.assignee) {
        const html = renderPerson(taskData.assignee);
        const extra = Number(taskData.assignee.extra_count || 0);
        $assignee.html(extra > 0 ? `${html}<small class="text-muted ms-1">+${extra}</small>` : html);
      }
    }

    const $start = $('#task-overview-start-date');
    if ($start.length && taskData.start_date) {
      $start.text(taskData.start_date.display || '-');
    }

    const $end = $('#task-overview-end-date');
    if ($end.length && taskData.due_date) {
      $end
        .toggleClass('text-danger fw-semibold', !!taskData.due_date.is_overdue)
        .text(taskData.due_date.display || '-');
    }

    const $desc = $('#task-overview-description');
    if ($desc.length) {
      const rich = sanitizeRichEditorHtml(taskData.description_html || '');
      $desc.html(rich || '<span class="text-muted">No description yet.</span>');
    }

    const $descField = $('#task-view-desc');
    if ($descField.length && taskData.description_html !== undefined) {
      $descField.val(taskData.description_html || '');
    }
    const editorEl = document.querySelector('[data-task-rich-editor] [data-editor-input]');
    if (editorEl && taskData.description_html !== undefined) {
      editorEl.innerHTML = sanitizeRichEditorHtml(taskData.description_html || '') || '<p><br></p>';
    }

    if (taskData.start_date && $('#task-view-start-date').length) {
      $('#task-view-start-date').val(taskData.start_date.value || '');
      $('#task-view-start-date-tbd')
        .prop('checked', !!taskData.start_date.is_tbd)
        .closest('.tbd-pill')
        .toggleClass('is-active', !!taskData.start_date.is_tbd);
    }
    if (taskData.due_date && $('#task-view-due').length) {
      $('#task-view-due').val(taskData.due_date.value || '');
    }
  }

  function sanitizeRichEditorHtml(html) {
    const source = document.createElement('div');
    source.innerHTML = html || '';
    const allowedTags = new Set(['P', 'BR', 'STRONG', 'B', 'EM', 'I', 'U', 'UL', 'OL', 'LI', 'A']);
    const normalizeTag = (tagName) => {
      if (!tagName) return '';
      const upper = tagName.toUpperCase();
      if (upper === 'DIV') return 'P';
      return upper;
    };
    const sanitizeUrl = (value) => {
      const raw = (value || '').trim();
      if (!raw) return '';
      if (/^(https?:|mailto:|\/)/i.test(raw)) return raw;
      if (/^\/\//.test(raw)) return `https:${raw}`;
      if (!/^[a-z][a-z0-9+.-]*:/i.test(raw)) return `https://${raw}`;
      return '';
    };

    const linkifyText = (text) => {
      const content = String(text || '');
      if (!content) return document.createTextNode('');
      const regex = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/gi;
      let lastIndex = 0;
      let match;
      const fragment = document.createDocumentFragment();
      while ((match = regex.exec(content)) !== null) {
        const start = match.index;
        const rawUrl = match[0];
        if (start > lastIndex) {
          fragment.appendChild(document.createTextNode(content.slice(lastIndex, start)));
        }
        const href = sanitizeUrl(rawUrl);
        if (href) {
          const anchor = document.createElement('a');
          anchor.setAttribute('href', href);
          anchor.setAttribute('target', '_blank');
          anchor.setAttribute('rel', 'noopener noreferrer nofollow');
          anchor.textContent = rawUrl;
          fragment.appendChild(anchor);
        } else {
          fragment.appendChild(document.createTextNode(rawUrl));
        }
        lastIndex = start + rawUrl.length;
      }
      if (lastIndex < content.length) {
        fragment.appendChild(document.createTextNode(content.slice(lastIndex)));
      }
      return fragment.childNodes.length ? fragment : document.createTextNode(content);
    };

    const sanitizeNode = (node) => {
      if (!node) return null;
      if (node.nodeType === Node.TEXT_NODE) {
        return linkifyText(node.textContent || '');
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return null;
      }

      const tag = normalizeTag(node.tagName);
      const children = Array.from(node.childNodes || []).map(sanitizeNode).filter(Boolean);

      if (!allowedTags.has(tag)) {
        const fragment = document.createDocumentFragment();
        children.forEach((child) => fragment.appendChild(child));
        return fragment;
      }

      const safeEl = document.createElement(tag.toLowerCase());
      children.forEach((child) => safeEl.appendChild(child));

      if (tag === 'A') {
        const href = sanitizeUrl(node.getAttribute('href') || node.dataset.href || node.textContent || '');
        if (!href) {
          const fragment = document.createDocumentFragment();
          while (safeEl.firstChild) fragment.appendChild(safeEl.firstChild);
          return fragment;
        }
        safeEl.setAttribute('href', href);
        safeEl.setAttribute('target', '_blank');
        safeEl.setAttribute('rel', 'noopener noreferrer nofollow');
      }
      return safeEl;
    };

    const output = document.createElement('div');
    Array.from(source.childNodes || []).forEach((child) => {
      const safe = sanitizeNode(child);
      if (safe) output.appendChild(safe);
    });
    return output.innerHTML.trim();
  }

  function sanitizeUrlForEditor(raw) {
    const value = (raw || '').trim();
    if (!value) return '';
    if (/^(https?:|mailto:)/i.test(value)) return value;
    if (/^\/\//.test(value)) return `https:${value}`;
    if (/^www\./i.test(value)) return `https://${value}`;
    if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) return `https://${value}`;
    return '';
  }

  function initTaskRichEditors($scope) {
    const $roots = ($scope && $scope.length ? $scope : $(document)).find('[data-task-rich-editor]');
    $roots.each(function() {
      const root = this;
      if (root.dataset.editorInitialized === '1') return;
      const textarea = root.querySelector('[data-editor-textarea]') || root.querySelector('#task-view-desc');
      const editor = root.querySelector('[data-editor-input]');
      if (!textarea || !editor) return;
      root.dataset.editorInitialized = '1';
      const isDisabled = root.dataset.disabled === '1' || textarea.disabled;
      editor.innerHTML = sanitizeRichEditorHtml(textarea.value || '') || '<p><br></p>';
      editor.setAttribute('contenteditable', isDisabled ? 'false' : 'true');
      root.querySelectorAll('[data-editor-cmd]').forEach((btn) => {
        if (isDisabled) btn.setAttribute('disabled', 'disabled');
      });
      let autoSaveTimer = null;

      const syncToTextarea = (triggerChange = false) => {
        const sanitized = sanitizeRichEditorHtml(editor.innerHTML);
        if (textarea.value !== sanitized) {
          textarea.value = sanitized;
        }
        if (triggerChange) {
          $(textarea).trigger('change');
        }
      };

      editor.addEventListener('input', () => {
        syncToTextarea(false);
        const overviewDesc = document.getElementById('task-overview-description');
        if (overviewDesc) {
          const plainText = (editor.textContent || '').trim();
          overviewDesc.innerHTML = plainText ? $('<div>').text(plainText).html() : '<span class="text-muted">No description yet.</span>';
        }
        if (isDisabled) return;
        if (autoSaveTimer) window.clearTimeout(autoSaveTimer);
        autoSaveTimer = window.setTimeout(() => {
          syncToTextarea(true);
        }, 700);
      });
      editor.addEventListener('blur', () => {
        window.setTimeout(() => {
          if (root.contains(document.activeElement)) return;
          if (autoSaveTimer) {
            window.clearTimeout(autoSaveTimer);
            autoSaveTimer = null;
          }
          syncToTextarea(true);
        }, 0);
      });

      editor.addEventListener('paste', (event) => {
        const text = event.clipboardData?.getData('text/plain') || '';
        const trimmed = text.trim();
        if (!trimmed) return;
        const isUrlOnly = /^(https?:\/\/|www\.)[^\s]+$/i.test(trimmed);
        if (!isUrlOnly) return;
        event.preventDefault();
        const href = sanitizeUrlForEditor(trimmed);
        if (!href) {
          document.execCommand('insertText', false, trimmed);
          syncToTextarea(false);
          return;
        }
        document.execCommand('insertHTML', false, `<a href="${href}" target="_blank" rel="noopener noreferrer nofollow">${trimmed}</a>`);
        syncToTextarea(false);
      });

      root.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-editor-cmd]');
        if (!btn || isDisabled) return;
        event.preventDefault();
        const cmd = btn.dataset.editorCmd;
        editor.focus();
        if (cmd === 'createLink') {
          const selectedText = window.getSelection()?.toString() || '';
          const raw = window.prompt('Enter link URL', selectedText && /^https?:\/\//i.test(selectedText) ? selectedText : 'https://');
          if (!raw) return;
          const href = sanitizeUrlForEditor(raw.trim());
          if (!href) return;
          document.execCommand('createLink', false, href);
          const selection = window.getSelection();
          if (selection?.anchorNode?.parentElement?.tagName === 'A') {
            const anchor = selection.anchorNode.parentElement;
            anchor.setAttribute('target', '_blank');
            anchor.setAttribute('rel', 'noopener noreferrer nofollow');
          }
        } else {
          document.execCommand(cmd, false, null);
        }
        syncToTextarea(false);
      });
    });
  }

  $(document).on('input', 'textarea[data-autoresize="true"]', function() {
    this.style.height = 'auto';
    this.style.height = `${this.scrollHeight}px`;
  });

  $(document).on('click', '#task-share-btn', async function() {
    const rawUrl = ($(this).data('task-share-url') || window.location.href || '').toString();
    const shareTitle = (($(this).data('task-share-title') || document.title || 'Task') + '').trim() || 'Task';
    let url = '';
    try {
      url = new URL(rawUrl, window.location.origin).href;
    } catch (e) {
      url = (window.location.href || '').toString();
    }
    if (!url) return;
    const shareText = `${shareTitle}\n${url}`;

    try {
      if (navigator.share) {
        // WhatsApp and some targets rely on `text`; include both text and url.
        const shareData = { title: shareTitle, text: shareText, url };
        if (navigator.canShare && !navigator.canShare(shareData)) {
          await navigator.share({ text: shareText });
        } else {
          await navigator.share(shareData);
        }
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(shareText);
      } else {
        const temp = document.createElement('textarea');
        temp.value = shareText;
        document.body.appendChild(temp);
        temp.select();
        document.execCommand('copy');
        document.body.removeChild(temp);
      }
      showSuccess('Task link copied.');
    } catch (error) {
      if (error && error.name === 'AbortError') {
        // User cancelled native share dialog; this is not an application error.
        return;
      }
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(shareText);
          showSuccess('Task link copied.');
          return;
        } catch (fallbackError) {
          // continue to error message
        }
      }
      showError('Failed to share task link.');
    }
  });

  function inlineUpdateRequest(taskId, field, value) {
    return new Promise((resolve, reject) => {
      $.post({
        url: `/task/${taskId}/inline-update/`,
        data: { field, value },
        headers: { "X-CSRFToken": csrftoken },
        success: function(resp) {
          if (resp && resp.success) {
            resolve(resp);
          } else {
            reject(new Error(resp?.error || `Failed to update ${field}.`));
          }
        },
        error: function(xhr) {
          reject(new Error(xhr.responseJSON?.error || `Failed to update ${field}.`));
        }
      });
    });
  }

  function collectTaskEditSnapshot() {
    const editModalEditor = document.querySelector('#taskEditModal [data-task-rich-editor] [data-editor-input]');
    if (editModalEditor) {
      $('#task-edit-desc').val(sanitizeRichEditorHtml(editModalEditor.innerHTML || ''));
    }
    const assigneesVal = $('#task-edit-assignees').val();
    const labelsVal = $('#task-edit-labels').val();
    return {
      title: ($('#task-edit-title').val() || '').trim(),
      status: ($('#task-edit-status').val() || '').trim(),
      priority: ($('#task-edit-priority').val() || '').trim(),
      start_date_tbd: $('#task-edit-start-date-tbd').is(':checked') ? '1' : '0',
      start_date: ($('#task-edit-start-date').val() || '').trim(),
      due_date: ($('#task-edit-due-date').val() || '').trim(),
      description: ($('#task-edit-desc').val() || '').trim(),
      assignees: Array.isArray(assigneesVal) ? assigneesVal.join(',') : (assigneesVal || ''),
      labels: Array.isArray(labelsVal) ? labelsVal.join(',') : (labelsVal || ''),
    };
  }

  function openTaskEditModal() {
    const $modal = $('#taskEditModal');
    if (!$modal.length) return;
    $('#task-edit-title').val($('#task-view-title').val() || $('#task-overview-title').text().trim());
    if ($('#task-edit-status').length) {
      const statusFromView = $('#task-view-status').val();
      if (statusFromView) $('#task-edit-status').val(statusFromView);
    }
    $('#task-edit-priority').val($('#task-view-priority').val() || 'p2');
    if ($('#task-view-start-date').length) {
      const startVal = $('#task-view-start-date').val();
      if (startVal !== undefined && startVal !== null && String(startVal).trim() !== '') {
        $('#task-edit-start-date').val(startVal);
      }
    }
    if ($('#task-view-due').length) {
      const dueVal = $('#task-view-due').val();
      if (dueVal !== undefined && dueVal !== null && String(dueVal).trim() !== '') {
        $('#task-edit-due-date').val(dueVal);
      }
    }

    let startTbd = $('#task-edit-start-date-tbd').is(':checked');
    if ($('#task-view-start-date-tbd').length) {
      startTbd = $('#task-view-start-date-tbd').is(':checked');
      $('#task-edit-start-date-tbd').prop('checked', startTbd);
    }
    $('#task-edit-start-tbd-pill').toggleClass('is-active', startTbd);
    $('#task-edit-start-date').prop('disabled', startTbd);

    if ($('#task-view-assignees').length) {
      const assignees = $('#task-view-assignees').val();
      if (assignees !== undefined && assignees !== null) {
        $('#task-edit-assignees').val(assignees || []);
      }
    }
    if ($('#task-view-labels').length) {
      const labels = $('#task-view-labels').val();
      if (labels !== undefined && labels !== null) {
        $('#task-edit-labels').val(labels || []);
      }
    }

    if ($('#task-view-desc').length) {
      const descVal = $('#task-view-desc').val();
      if (descVal !== undefined && descVal !== null && String(descVal).trim() !== '') {
        $('#task-edit-desc').val(descVal);
      }
    }
    const editor = $modal[0].querySelector('[data-task-rich-editor] [data-editor-input]');
    if (editor) {
      editor.innerHTML = sanitizeRichEditorHtml($('#task-edit-desc').val() || '') || '<p><br></p>';
    }
    initTaskRichEditors($modal);

    $modal.data('snapshot', collectTaskEditSnapshot());
    $modal.modal('show');
  }

  $(document).on('click', '#btn-edit-task-detail', function() {
    openTaskEditModal();
  });

  $(document).on('change', '#task-edit-start-date-tbd', function() {
    const checked = $(this).is(':checked');
    $('#task-edit-start-tbd-pill').toggleClass('is-active', checked);
    if (checked) {
      $('#task-edit-start-date').val('').prop('disabled', true);
    } else {
      $('#task-edit-start-date').prop('disabled', false);
    }
  });

  $(document).on('click', '#btn-save-task-edit', async function() {
    const $btn = $(this);
    const taskId = getCurrentTaskId();
    const $modal = $('#taskEditModal');
    if (!taskId || !$modal.length) return;

    const before = $modal.data('snapshot') || {};
    const after = collectTaskEditSnapshot();
    const updates = [];

    const maybePush = (field, next, prev) => {
      if (String(next || '') !== String(prev || '')) updates.push({ field, value: next });
    };

    maybePush('title', after.title, before.title);
    if ($('#task-edit-status').length) {
      maybePush('status', after.status, before.status);
    }
    maybePush('priority', after.priority, before.priority);
    maybePush('start_date_tbd', after.start_date_tbd, before.start_date_tbd);
    maybePush('start_date', after.start_date, before.start_date);
    maybePush('due_date', after.due_date, before.due_date);
    maybePush('assignees', after.assignees, before.assignees);
    if ($('#task-edit-labels').length) {
      maybePush('labels', after.labels, before.labels);
    }
    maybePush('description', after.description, before.description);

    if (!updates.length) {
      $modal.modal('hide');
      return;
    }

    $btn.addClass('is-saving').text('Saving...');
    try {
      let lastResp = null;
      for (const upd of updates) {
        // eslint-disable-next-line no-await-in-loop
        lastResp = await inlineUpdateRequest(taskId, upd.field, upd.value);
      }
      if (lastResp?.task) updateTaskDetailUI(lastResp.task);
      loadTaskView(taskId);
      $modal.modal('hide');
      showSuccess('Task updated successfully.');
    } catch (err) {
      showError(err.message || 'Failed to update task.');
    } finally {
      $btn.removeClass('is-saving').text('Save Changes');
    }
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

    $(`#mycards-list-body .task-user-result-list-row[data-task-id='${taskId}']`).remove();
    if ($('#mycards-search').length) {
      $('#mycards-search').trigger('input');
    }

    $('#taskViewModal').modal('hide');
    $('#taskMoveModal').modal('hide');

    // Always refresh after move so data/state is fully synchronized.
    if ($('#task-board').length && typeof reloadProjectDetailBoard === 'function') {
      reloadProjectDetailBoard(false);
      return;
    }
    window.location.reload();
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

  const COMMENT_IMAGE_ALLOWED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const COMMENT_IMAGE_MAX_SIZE = 5 * 1024 * 1024;
  const COMMENT_IMAGE_MAX_COUNT = 5;
  const COMMENT_IMAGE_TARGET_SIZE = 1200 * 1024;
  const COMMENT_IMAGE_MAX_DIMENSION = 1920;
  const taskCommentPasteState = {
    taskId: null,
    items: [],
  };

  function formatCommentBytes(bytes) {
    if (!bytes || bytes < 1024) return `${bytes || 0} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function getCommentComposerElements() {
    const $scope = $('#task-view-body');
    return {
      $preview: $scope.find('.task-comment-paste-previews').first(),
      $progressWrap: $scope.find('.task-comment-upload-progress').first(),
      $progressBar: $scope.find('.task-comment-upload-progress .progress-bar').first(),
    };
  }

  function renderTaskCommentPastePreviews() {
    const { $preview } = getCommentComposerElements();
    if (!$preview.length) return;
    $preview.empty();
    taskCommentPasteState.items.forEach((item, index) => {
      const $item = $('<div class="task-comment-paste-item"></div>');
      const $thumb = $('<img class="task-comment-paste-thumb" alt="Pasted image preview">').attr('src', item.previewUrl);
      const $meta = $('<div class="task-comment-paste-meta"></div>').text(`${item.file.name} (${formatCommentBytes(item.file.size)})`);
      const $remove = $('<button type="button" class="task-comment-paste-remove" title="Remove image"><i class="bi bi-x"></i></button>')
        .attr('data-index', index);
      $item.append($thumb, $meta, $remove);
      $preview.append($item);
    });
  }

  function resetTaskCommentPasteState(nextTaskId = null) {
    taskCommentPasteState.items.forEach((item) => {
      if (item.previewUrl) {
        URL.revokeObjectURL(item.previewUrl);
      }
    });
    taskCommentPasteState.items = [];
    taskCommentPasteState.taskId = nextTaskId;
    const { $progressWrap, $progressBar } = getCommentComposerElements();
    if ($progressBar.length) {
      $progressBar.css('width', '0%').text('0%');
    }
    if ($progressWrap.length) {
      $progressWrap.addClass('d-none');
    }
    renderTaskCommentPastePreviews();
  }

  function ensureTaskCommentPasteTask(taskId) {
    if (!taskId) return;
    if (taskCommentPasteState.taskId === null) {
      taskCommentPasteState.taskId = taskId;
      return;
    }
    if (String(taskCommentPasteState.taskId) !== String(taskId)) {
      resetTaskCommentPasteState(taskId);
    }
  }

  function compressPastedImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('Failed to read image data.'));
      reader.onload = () => {
        const img = new Image();
        img.onerror = () => reject(new Error('Failed to load pasted image.'));
        img.onload = () => {
          const ratio = Math.min(
            1,
            COMMENT_IMAGE_MAX_DIMENSION / Math.max(img.width || 1, 1),
            COMMENT_IMAGE_MAX_DIMENSION / Math.max(img.height || 1, 1)
          );
          const width = Math.max(1, Math.round((img.width || 1) * ratio));
          const height = Math.max(1, Math.round((img.height || 1) * ratio));
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            reject(new Error('Failed to initialize image canvas.'));
            return;
          }
          ctx.drawImage(img, 0, 0, width, height);

          const qualities = [0.9, 0.82, 0.74, 0.66, 0.58];
          const tryCompressAt = (idx) => {
            const quality = qualities[Math.min(idx, qualities.length - 1)];
            canvas.toBlob((blob) => {
              if (!blob) {
                reject(new Error('Image compression failed.'));
                return;
              }
              if (blob.size <= COMMENT_IMAGE_TARGET_SIZE || idx >= qualities.length - 1) {
                const originalName = file.name || `pasted-${Date.now()}.png`;
                const safeName = originalName.replace(/\.[^.]+$/, '') || `pasted-${Date.now()}`;
                const finalType = blob.type || 'image/jpeg';
                const ext = finalType === 'image/webp' ? 'webp' : 'jpg';
                resolve(new File([blob], `${safeName}.${ext}`, { type: finalType, lastModified: Date.now() }));
                return;
              }
              tryCompressAt(idx + 1);
            }, 'image/jpeg', quality);
          };

          tryCompressAt(0);
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function addCommentImagesFromFiles(files) {
    if (!files || !files.length) return;
    const remaining = Math.max(0, COMMENT_IMAGE_MAX_COUNT - taskCommentPasteState.items.length);
    if (!remaining) {
      showError(`Maximum ${COMMENT_IMAGE_MAX_COUNT} images per comment.`);
      return;
    }

    const inputFiles = Array.from(files).slice(0, remaining);
    for (const rawFile of inputFiles) {
      const type = (rawFile.type || '').toLowerCase();
      if (!COMMENT_IMAGE_ALLOWED_TYPES.has(type)) {
        showError('Only PNG, JPG, and WEBP images are supported.');
        continue;
      }
      if (rawFile.size > 15 * 1024 * 1024) {
        showError('Image is too large to process. Please use an image under 15 MB.');
        continue;
      }
      try {
        const compressedFile = await compressPastedImage(rawFile);
        if (compressedFile.size > COMMENT_IMAGE_MAX_SIZE) {
          showError('Compressed image is still too large (max 5 MB).');
          continue;
        }
        taskCommentPasteState.items.push({
          file: compressedFile,
          previewUrl: URL.createObjectURL(compressedFile),
        });
      } catch (err) {
        showError(err?.message || 'Failed to process pasted image.');
      }
    }

    if (files.length > remaining) {
      showError(`Only ${COMMENT_IMAGE_MAX_COUNT} images can be attached to one comment.`);
    }

    renderTaskCommentPastePreviews();
  }

  $(document).on('paste', '#task-view-comment-input', async function(e) {
    const taskId = getCurrentTaskId();
    if (!taskId || this.disabled) return;
    ensureTaskCommentPasteTask(taskId);

    const clipboardData = e.originalEvent?.clipboardData;
    const items = Array.from(clipboardData?.items || []);
    const imageItems = items.filter((item) => item.kind === 'file' && (item.type || '').toLowerCase().startsWith('image/'));
    if (!imageItems.length) return;

    e.preventDefault();

    const files = imageItems.map((item) => item.getAsFile()).filter(Boolean);
    await addCommentImagesFromFiles(files);
  });

  $(document).on('change', '#task-view-comment-image-input', async function() {
    const taskId = getCurrentTaskId();
    if (!taskId || this.disabled) return;
    ensureTaskCommentPasteTask(taskId);
    const files = this.files || [];
    await addCommentImagesFromFiles(files);
    this.value = '';
  });

  $(document).on('click', '.task-comment-paste-remove', function() {
    const index = Number($(this).attr('data-index'));
    if (!Number.isInteger(index)) return;
    const item = taskCommentPasteState.items[index];
    if (item?.previewUrl) {
      URL.revokeObjectURL(item.previewUrl);
    }
    taskCommentPasteState.items.splice(index, 1);
    renderTaskCommentPastePreviews();
  });

  $(document).on('hidden.bs.modal', '#taskViewModal', function() {
    resetTaskCommentPasteState(null);
    resetAllReplyDrafts();
    hideMentionMenu();
  });

  function ensureCommentAttachmentPreviewModal() {
    let modalEl = document.getElementById('commentAttachmentPreviewModal');
    if (modalEl) return modalEl;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div class="modal fade" id="commentAttachmentPreviewModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-xl">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="commentAttachmentPreviewTitle">Attachment Preview</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div id="commentAttachmentPreviewBody" class="text-center"></div>
            </div>
          </div>
        </div>
      </div>
    `.trim();
    modalEl = wrapper.firstElementChild;
    document.body.appendChild(modalEl);
    return modalEl;
  }

  function isPreviewableImageUrl(url) {
    const clean = String(url || '').split('?')[0].toLowerCase();
    return /\.(png|jpe?g|webp|gif|bmp|svg)$/.test(clean);
  }

  $(document).on('click', '.js-comment-attachment-preview', function(e) {
    e.preventDefault();
    const url = $(this).data('attachment-url') || $(this).attr('href') || '';
    if (!url) return;
    const name = ($(this).data('attachment-name') || 'Attachment Preview').toString();
    const modalEl = ensureCommentAttachmentPreviewModal();
    const $title = $('#commentAttachmentPreviewTitle');
    const $body = $('#commentAttachmentPreviewBody');

    $title.text(name);
    if (isPreviewableImageUrl(url)) {
      $body.html(`<img src="${url}" alt="${$('<div>').text(name).html()}" class="img-fluid rounded border">`);
    } else {
      const safeUrl = $('<div>').text(String(url)).html();
      $body.html(`
        <iframe src="${safeUrl}" style="width:100%;height:70vh;border:1px solid rgba(15,23,42,0.12);border-radius:10px;"></iframe>
        <div class="mt-2 text-muted small">Preview is shown in popup only.</div>
      `);
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  });

  $(document).on('click', '#btn-add-comment', function() {
    const taskId = getCurrentTaskId();
    if (!taskId) return;
    ensureTaskCommentPasteTask(taskId);

    const content = ($('#task-view-comment-input').val() || '').trim();
    const hasImages = taskCommentPasteState.items.length > 0;
    if (!content && !hasImages) return;

    const formData = new FormData();
    formData.append('content', content);
    taskCommentPasteState.items.forEach((item) => {
      formData.append('images', item.file, item.file.name);
    });

    const { $progressWrap, $progressBar } = getCommentComposerElements();
    if ($progressWrap.length) {
      $progressWrap.removeClass('d-none');
    }
    if ($progressBar.length) {
      $progressBar.css('width', '0%').text('0%');
    }

    $.ajax({
      url: `/task/${taskId}/comment/add/`,
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      xhr: function() {
        const xhr = $.ajaxSettings.xhr();
        if (xhr.upload && $progressBar.length) {
          xhr.upload.addEventListener('progress', function(evt) {
            if (!evt.lengthComputable) return;
            const percent = Math.max(0, Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
            $progressBar.css('width', `${percent}%`).text(`${percent}%`);
          });
        }
        return xhr;
      },
      success: function(resp) {
        if (resp.success) {
          resetTaskCommentPasteState(taskId);
          $('#task-view-comment-input').val('');
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
      },
      complete: function() {
        if ($progressWrap.length) {
          setTimeout(() => {
            $progressWrap.addClass('d-none');
            if ($progressBar.length) {
              $progressBar.css('width', '0%').text('0%');
            }
          }, 300);
        }
      }
    });
  });

  const replyCommentDrafts = new Map();
  const mentionUiState = {
    $menu: null,
    activeTextarea: null,
    queryStart: null,
    queryEnd: null,
    results: [],
    activeIndex: -1,
    debounceTimer: null,
    pendingRequest: null,
  };

  function getReplyDraft(commentId) {
    const key = String(commentId);
    if (!replyCommentDrafts.has(key)) {
      replyCommentDrafts.set(key, []);
    }
    return replyCommentDrafts.get(key);
  }

  function resetReplyDraft(commentId) {
    const key = String(commentId);
    const items = replyCommentDrafts.get(key) || [];
    items.forEach((item) => {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    });
    replyCommentDrafts.delete(key);
  }

  function resetAllReplyDrafts() {
    Array.from(replyCommentDrafts.keys()).forEach((key) => {
      resetReplyDraft(key);
    });
  }

  function ensureMentionMenu() {
    if (mentionUiState.$menu && mentionUiState.$menu.length) return mentionUiState.$menu;
    mentionUiState.$menu = $(`
      <div class="comment-mention-menu d-none" role="listbox" aria-label="Mention suggestions">
        <div class="comment-mention-menu-list"></div>
      </div>
    `);
    $('body').append(mentionUiState.$menu);
    return mentionUiState.$menu;
  }

  function hideMentionMenu() {
    if (mentionUiState.pendingRequest) {
      mentionUiState.pendingRequest.abort();
      mentionUiState.pendingRequest = null;
    }
    if (mentionUiState.debounceTimer) {
      window.clearTimeout(mentionUiState.debounceTimer);
      mentionUiState.debounceTimer = null;
    }
    if (mentionUiState.$menu) {
      mentionUiState.$menu.addClass('d-none');
    }
    mentionUiState.results = [];
    mentionUiState.activeIndex = -1;
    mentionUiState.activeTextarea = null;
    mentionUiState.queryStart = null;
    mentionUiState.queryEnd = null;
  }

  function extractMentionQuery(textarea) {
    const value = textarea.value || '';
    const caret = textarea.selectionStart || 0;
    const before = value.slice(0, caret);
    const match = before.match(/(?:^|\s)@([A-Za-z0-9_.+-]{0,150})$/);
    if (!match) return null;
    const query = (match[1] || '').trim();
    const atPos = before.lastIndexOf('@');
    if (atPos < 0) return null;
    return { query, start: atPos, end: caret };
  }

  function positionMentionMenu(textarea) {
    const $menu = ensureMentionMenu();
    const rect = textarea.getBoundingClientRect();
    $menu.css({
      position: 'fixed',
      top: `${Math.min(window.innerHeight - 220, rect.bottom + 6)}px`,
      left: `${Math.max(8, rect.left)}px`,
      width: `${Math.min(360, Math.max(240, rect.width))}px`,
      zIndex: 12000,
    });
  }

  function renderMentionMenuResults(results) {
    const $menu = ensureMentionMenu();
    const $list = $menu.find('.comment-mention-menu-list');
    $list.empty();
    mentionUiState.results = results || [];
    mentionUiState.activeIndex = results.length ? 0 : -1;
    if (!results.length) {
      $list.append('<div class="comment-mention-empty">No users found.</div>');
      $menu.removeClass('d-none');
      return;
    }
    results.forEach((u, idx) => {
      const displayName = (u.full_name || '').trim() || u.username;
      const $item = $(`
        <button type="button" class="comment-mention-item" role="option">
          <img class="comment-mention-avatar" alt="">
          <div class="comment-mention-meta">
            <div class="comment-mention-name"></div>
            <div class="comment-mention-email"></div>
          </div>
        </button>
      `);
      $item.attr('data-index', idx);
      $item.find('.comment-mention-avatar').attr('src', u.avatar_url || '/static/arva/img/default-avatar.png');
      $item.find('.comment-mention-name').text(displayName);
      $item.find('.comment-mention-email').text(u.email || `@${u.username}`);
      if (idx === mentionUiState.activeIndex) $item.addClass('is-active');
      $list.append($item);
    });
    $menu.removeClass('d-none');
  }

  function updateMentionMenuActiveItem() {
    if (!mentionUiState.$menu) return;
    mentionUiState.$menu.find('.comment-mention-item').removeClass('is-active');
    mentionUiState.$menu.find(`.comment-mention-item[data-index="${mentionUiState.activeIndex}"]`).addClass('is-active');
  }

  function insertMentionToTextarea(user) {
    const textarea = mentionUiState.activeTextarea;
    if (!textarea || !user) return;
    const value = textarea.value || '';
    const start = mentionUiState.queryStart;
    const end = mentionUiState.queryEnd;
    if (start === null || end === null || start < 0 || end < start) return;
    const mentionText = `@${user.username} `;
    const nextValue = `${value.slice(0, start)}${mentionText}${value.slice(end)}`;
    textarea.value = nextValue;
    const nextCaret = start + mentionText.length;
    textarea.setSelectionRange(nextCaret, nextCaret);
    $(textarea).trigger('input');
    textarea.focus();
    hideMentionMenu();
  }

  function requestMentionSuggestions(textarea, queryMeta) {
    mentionUiState.activeTextarea = textarea;
    mentionUiState.queryStart = queryMeta.start;
    mentionUiState.queryEnd = queryMeta.end;
    positionMentionMenu(textarea);

    if (mentionUiState.pendingRequest) {
      mentionUiState.pendingRequest.abort();
      mentionUiState.pendingRequest = null;
    }
    if (mentionUiState.debounceTimer) {
      window.clearTimeout(mentionUiState.debounceTimer);
    }

    mentionUiState.debounceTimer = window.setTimeout(() => {
      mentionUiState.pendingRequest = $.get('/tasks/user-suggestions/', { q: queryMeta.query || '' })
        .done((resp) => {
          const results = Array.isArray(resp?.results) ? resp.results : [];
          renderMentionMenuResults(results);
        })
        .fail((xhr) => {
          if (xhr?.statusText !== 'abort') {
            hideMentionMenu();
          }
        })
        .always(() => {
          mentionUiState.pendingRequest = null;
        });
    }, 220);
  }

  function renderReplyDraftPreview($container, commentId) {
    const items = getReplyDraft(commentId);
    const $previewWrap = $container.find('.reply-paste-previews').first();
    if (!$previewWrap.length) return;
    $previewWrap.empty();
    items.forEach((item, idx) => {
      const $item = $('<div class="reply-preview-item"></div>');
      const $img = $('<img class="reply-preview-thumb" alt="Reply image preview">').attr('src', item.previewUrl);
      const $remove = $('<button type="button" class="reply-preview-remove" title="Remove image"><i class="bi bi-x"></i></button>')
        .attr('data-comment-id', commentId)
        .attr('data-index', idx);
      $item.append($img, $remove);
      $previewWrap.append($item);
    });
  }

  async function addReplyImages(commentId, files, $container) {
    if (!files || !files.length) return;
    const draft = getReplyDraft(commentId);
    const remaining = Math.max(0, COMMENT_IMAGE_MAX_COUNT - draft.length);
    if (!remaining) {
      showError(`Maximum ${COMMENT_IMAGE_MAX_COUNT} images per reply.`);
      return;
    }
    const inputFiles = Array.from(files).slice(0, remaining);
    for (const rawFile of inputFiles) {
      const type = (rawFile.type || '').toLowerCase();
      if (!COMMENT_IMAGE_ALLOWED_TYPES.has(type)) {
        showError('Only PNG, JPG, and WEBP images are supported.');
        continue;
      }
      if (rawFile.size > 15 * 1024 * 1024) {
        showError('Image is too large to process. Please use an image under 15 MB.');
        continue;
      }
      try {
        const compressedFile = await compressPastedImage(rawFile);
        if (compressedFile.size > COMMENT_IMAGE_MAX_SIZE) {
          showError('Compressed image is still too large (max 5 MB).');
          continue;
        }
        draft.push({
          file: compressedFile,
          previewUrl: URL.createObjectURL(compressedFile),
        });
      } catch (err) {
        showError(err?.message || 'Failed to process pasted image.');
      }
    }
    if (files.length > remaining) {
      showError(`Only ${COMMENT_IMAGE_MAX_COUNT} images can be attached to one reply.`);
    }
    renderReplyDraftPreview($container, commentId);
  }

  $(document).on('click', '.btn-reply-comment', function() {
    const commentId = $(this).data('id');
    const container = $(this).closest('.comment-item').find('.reply-form');

    container.html(`
      <div class="reply-form-panel">
        <textarea class="form-control reply-input" rows="2" placeholder="Write a reply..."></textarea>
        <div class="reply-form-toolbar mt-2">
          <label class="btn btn-light btn-sm mb-0">
            <i class="bi bi-image me-1"></i>Add image
            <input type="file" class="d-none reply-image-input" accept="image/png,image/jpeg,image/webp" multiple data-comment-id="${commentId}">
          </label>
          <small class="text-muted">Tip: paste screenshots with Ctrl+V.</small>
        </div>
        <div class="reply-paste-previews"></div>
        <div class="progress reply-progress d-none" role="progressbar" aria-label="Reply upload progress">
          <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%">0%</div>
        </div>
        <div class="reply-actions">
          <button class="btn btn-sm btn-primary btn-submit-reply" data-id="${commentId}">Reply</button>
          <button class="btn btn-sm btn-secondary btn-cancel-reply">Cancel</button>
        </div>
      </div>
    `);

    renderReplyDraftPreview(container, commentId);
    container.show();
  });

  $(document).on('click', '.btn-cancel-reply', function() {
    const container = $(this).closest('.reply-form');
    const commentId = container.closest('.comment-item').data('id');
    resetReplyDraft(commentId);
    container.html('').hide();
  });

  $(document).on('input click', '#task-view-comment-input, .reply-input', function() {
    if (this.disabled) return;
    const meta = extractMentionQuery(this);
    if (!meta) {
      hideMentionMenu();
      return;
    }
    requestMentionSuggestions(this, meta);
  });

  $(document).on('keydown', '#task-view-comment-input, .reply-input', function(e) {
    if (!mentionUiState.$menu || mentionUiState.$menu.hasClass('d-none')) return;
    if (mentionUiState.activeTextarea !== this) return;
    if (!mentionUiState.results.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      mentionUiState.activeIndex = (mentionUiState.activeIndex + 1) % mentionUiState.results.length;
      updateMentionMenuActiveItem();
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      mentionUiState.activeIndex = (mentionUiState.activeIndex - 1 + mentionUiState.results.length) % mentionUiState.results.length;
      updateMentionMenuActiveItem();
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const chosen = mentionUiState.results[mentionUiState.activeIndex];
      if (chosen) insertMentionToTextarea(chosen);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      hideMentionMenu();
    }
  });

  $(document).on('blur', '#task-view-comment-input, .reply-input', function() {
    window.setTimeout(() => {
      const active = document.activeElement;
      if (active && $(active).closest('.comment-mention-menu').length) return;
      hideMentionMenu();
    }, 120);
  });

  $(document).on('mousedown', '.comment-mention-item', function(e) {
    e.preventDefault();
    const idx = Number($(this).attr('data-index'));
    const selected = mentionUiState.results[idx];
    if (selected) insertMentionToTextarea(selected);
  });

  $(document).on('paste', '.reply-input', async function(e) {
    const $container = $(this).closest('.reply-form');
    const commentId = $container.closest('.comment-item').data('id');
    if (!commentId || this.disabled) return;
    const clipboardData = e.originalEvent?.clipboardData;
    const items = Array.from(clipboardData?.items || []);
    const imageItems = items.filter((item) => item.kind === 'file' && (item.type || '').toLowerCase().startsWith('image/'));
    if (!imageItems.length) return;
    e.preventDefault();
    const files = imageItems.map((item) => item.getAsFile()).filter(Boolean);
    await addReplyImages(commentId, files, $container);
  });

  $(document).on('change', '.reply-image-input', async function() {
    const commentId = $(this).data('comment-id');
    const $container = $(this).closest('.reply-form');
    await addReplyImages(commentId, this.files || [], $container);
    this.value = '';
  });

  $(document).on('click', '.reply-preview-remove', function() {
    const commentId = $(this).data('comment-id');
    const idx = Number($(this).data('index'));
    const draft = getReplyDraft(commentId);
    if (Number.isInteger(idx) && draft[idx]?.previewUrl) {
      URL.revokeObjectURL(draft[idx].previewUrl);
    }
    if (Number.isInteger(idx)) {
      draft.splice(idx, 1);
    }
    const $container = $(this).closest('.reply-form');
    renderReplyDraftPreview($container, commentId);
  });

  $(document).on('click', '.btn-submit-reply', function() {
    const commentId = $(this).data('id');
    const container = $(this).closest('.reply-form');
    const content = container.find('.reply-input').val().trim();
    const taskId = getCurrentTaskId();
    const draft = getReplyDraft(commentId);
    if (!content && !draft.length) return;

    const formData = new FormData();
    formData.append('content', content);
    draft.forEach((item) => {
      formData.append('images', item.file, item.file.name);
    });
    const $progress = container.find('.reply-progress');
    const $progressBar = container.find('.reply-progress .progress-bar');
    $progress.removeClass('d-none');
    $progressBar.css('width', '0%').text('0%');

    $.ajax({
      url: `/comment/${commentId}/reply/`,
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      xhr: function() {
        const xhr = $.ajaxSettings.xhr();
        if (xhr.upload) {
          xhr.upload.addEventListener('progress', function(evt) {
            if (!evt.lengthComputable) return;
            const percent = Math.max(0, Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
            $progressBar.css('width', `${percent}%`).text(`${percent}%`);
          });
        }
        return xhr;
      },
      success: function(resp) {
        if (resp.success) {
          resetReplyDraft(commentId);
          loadTaskView(taskId);
        }
      },
      error: function(xhr) {
        if (xhr?.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError("Failed to send reply.");
        }
      },
      complete: function() {
        setTimeout(() => {
          $progress.addClass('d-none');
          $progressBar.css('width', '0%').text('0%');
        }, 250);
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

  $(document).on('click', '.btn-delete-attachment', async function(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!await showConfirm('Delete this attachment?', 'Delete attachment')) return;

    const $btn = $(this);
    const attachmentId = $btn.data('attachment-id') || $btn.closest('[data-attachment-id]').data('attachment-id') || $btn.closest('li[data-id]').data('id');
    if (!attachmentId) {
      showError('Attachment ID not found.');
      return;
    }

    $.post({
      url: `/attachment/${attachmentId}/delete/`,
      success: function(resp) {
        if (!resp.success) {
          showError(resp.error || 'Failed to delete attachment.');
          return;
        }
        const $row = $btn.closest('[data-attachment-id], li[data-id]');
        if ($row.length) {
          $row.fadeOut(120, function() { $(this).remove(); });
        }
      },
      error: function(xhr) {
        if (xhr.status === 403) {
          showError('You do not have access to delete this attachment.');
        } else if (xhr.status === 400 && xhr.responseJSON?.error) {
          showError(xhr.responseJSON.error);
        } else {
          showError(xhr.responseJSON?.error || 'Failed to delete attachment.');
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
            const now = new Date();
            const joinedDateIso = now.toISOString().slice(0, 10);
            const joinedDateHuman = now.toLocaleDateString('en-GB', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            });
            const joinedEpoch = Math.floor(now.getTime() / 1000);
            $('#user-table tbody').append(`
                        <tr data-user-id="${resp.user.id}"
                            data-username="${(resp.user.username || '').toLowerCase()}"
                            data-email="${(resp.user.email || '').toLowerCase()}"
                            data-task-sort-created="${joinedEpoch}"
                            data-task-sort-done="0"
                            data-active="active"
                            data-staff="non-staff"
                            data-last-activity=""
                            data-last-login=""
                            data-joined="${joinedDateIso}"
                            data-status="never">
                          <td>${resp.user.username}</td>
                          <td>${resp.user.email}</td>
                          <td><span class="badge bg-success">Yes</span></td>
                          <td><span class="badge bg-secondary">No</span></td>
                          <td>-</td>
                          <td>-</td>
                          <td>${joinedDateHuman}</td>
                          <td><span class="status-pill status-never">Never</span></td>
                          <td>
                            <a href="/users/${resp.user.id}/edit/" class="btn btn-sm btn-outline-secondary">Edit</a>
                            <button class="btn btn-sm btn-outline-info btn-reset-password">Reset Password</button>
                            <button class="btn btn-sm btn-outline-warning btn-toggle-active">Toggle Active</button>
                            <button class="btn btn-sm btn-outline-danger btn-delete-user">Delete</button>
                          </td>
                        </tr>
                    `);
            applyTaskResultsSort(document.querySelector('#user-table tbody'));
            applyTaskResultsSort(document.getElementById('user-card-view'));
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
    const sortValue = ($('#task-list-order').val() || $('#task-filter-sort').val() || 'default').toString();
    params.set('page', pageValue);
    params.set('per_page', perPageValue);
    params.set('sort', sortValue);

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
        const savedOrder = localStorage.getItem('arva_project_detail_list_order') || $('#task-filter-sort').val() || 'default';
        const $orderSelect = $('#task-list-order');
        if ($orderSelect.length) {
          $orderSelect.val(savedOrder);
        }
        $('#task-filter-sort').val(savedOrder);
        syncProjectDetailTaskResultsSortMode(savedOrder);
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
      applyTaskResultsSort(document.getElementById('subprojectViewContent'));
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

  const $initialStageSelect = $('#task-view-stage');
  if ($initialStageSelect.length) {
    $initialStageSelect.data('prev', $initialStageSelect.val() || '');
    const initialStageLabel = $initialStageSelect.find('option:selected').text().trim();
    updateNonProjectStageBadges(initialStageLabel);
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
