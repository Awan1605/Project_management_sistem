/**
 * AI Priority Queue - JavaScript
 * ================================
 * Menangani tampilan dan interaksi halaman AI Priority Queue.
 * 
 * Fitur utama:
 * - Tampilkan task yang diprioritaskan oleh AI
 * - Filter berdasarkan level prioritas
 * - Sorting berdasarkan skor/due date
 * - Mobile accordion view
 * - Refresh analisis AI via AJAX
 */

// Data task - diisi dari template Django
const TASKS = [];

// Konfigurasi tampilan per level prioritas
const PRIO = {
    Critical: { tc:'c-red-txt', bc:'c-red-bg', icon:'bi-fire' },
    High:     { tc:'c-amb-txt', bc:'c-amb-bg', icon:'bi-arrow-up-circle-fill' },
    Medium:   { tc:'c-blu-txt', bc:'c-blu-bg', icon:'bi-activity' },
    Low:      { tc:'c-grn-txt', bc:'c-grn-bg', icon:'bi-arrow-down-circle' }
};

/**
 * Inisialisasi data task dari template Django
 * @param {Array} tasksData - Array task dari context Django
 */
function initializeTasks(tasksData) {
    TASKS.length = 0; // Hapus data lama
    Array.prototype.push.apply(TASKS, tasksData);
}

/**
 * Toggle accordion untuk tampilan mobile
 * @param {number} idx - Index task
 */
function toggleMobile(idx) {
    const card = document.getElementById('mc-' + idx);
    if (!card) return;
    const wasOpen = card.classList.contains('open');
    // Tutup semua card yang terbuka
    document.querySelectorAll('.m-task-card.open').forEach(c => c.classList.remove('open'));
    if (!wasOpen) card.classList.add('open');
}

/**
 * Navigasi ke halaman detail task
 * @param {string|number} pid - Project ID
 * @param {string|number} tid - Task ID
 */
function gotoTask(pid, tid) {
    window.location.href = '/project/' + pid + '/?open_task=' + tid;
}

/**
 * Buka modal detail untuk task
 * @param {number} idx - Index task
 */
function openDetail(idx) {
    const t = TASKS[idx];
    if (!t) return;
    const p = PRIO[t.priority_level] || PRIO.Low;

    // Update modal score dot
    const dot = document.getElementById('modal-score-dot');
    dot.className = 'score-dot ' + p.bc + ' ' + p.tc;
    dot.textContent = t.priority_score || '?';

    // Update modal content
    document.getElementById('modal-task-title').textContent = t.task_title;
    document.getElementById('modal-project-name').innerHTML =
        `<i class="bi bi-folder2-open me-1"></i>${t.project_name}`;

    document.getElementById('modal-priority').innerHTML =
        `<span class="prio-pill ${p.bc} ${p.tc}"><i class="bi ${p.icon}"></i> ${t.priority_level}</span>`;

    const sc = document.getElementById('modal-score');
    sc.textContent = t.priority_score || '—';
    sc.className = 'fw-bold ' + p.tc;
    sc.style.fontSize = '1.4rem';

    document.getElementById('modal-complexity').textContent = t.complexity || '—';
    document.getElementById('modal-list').textContent = t.task_list || '—';

    // Due date pill — 4 states based on days remaining
    const dueEl = document.getElementById('modal-due');
    if (t.due_date) {
        let cls, icon;
        switch (t.due_status) {
            case 'overdue':
                cls = 'overdue';
                icon = 'bi-exclamation-circle-fill';
                break;
            case 'urgent':
                cls = 'urgent';
                icon = 'bi-clock-fill';
                break;
            case 'warning':
                cls = 'warning';
                icon = 'bi-clock';
                break;
            default:
                cls = 'safe';
                icon = 'bi-calendar-check-fill';
        }
        dueEl.innerHTML = `<span class="due-pill ${cls}"><i class="bi ${icon}"></i> ${t.due_date}</span>`;
    } else {
        dueEl.textContent = '—';
    }

    // Sub-project row
    const subRow = document.getElementById('modal-subproject-row');
    subRow.style.display = t.sub_project_name ? '' : 'none';
    if (t.sub_project_name) document.getElementById('modal-subproject').textContent = t.sub_project_name;

    // Reasoning row
    const reaRow = document.getElementById('modal-reasoning-row');
    reaRow.style.display = t.reasoning ? '' : 'none';
    if (t.reasoning) document.getElementById('modal-reasoning').textContent = t.reasoning;

    // Open button action
    document.getElementById('modal-open-btn').onclick = () => gotoTask(t.project_id, t.task_id);
    
    // Show modal
    new bootstrap.Modal(document.getElementById('detailModal')).show();
}

/**
 * Refresh AI analysis
 */
function refreshAnalysis() {
    const btn = document.querySelector('[onclick="refreshAnalysis()"]');
    if (!btn) return;
    
    const orig = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Analyzing...';
    btn.disabled = true;

    Swal.fire({
        title: 'AI is analyzing your tasks...',
        html: `<div class="d-flex flex-column align-items-center">
                 <div class="spinner-border text-success mb-3" style="width:3rem;height:3rem;" role="status"></div>
                 <p class="text-muted mb-0">This may take a few moments</p></div>`,
        allowOutsideClick:false, 
        allowEscapeKey:false, 
        showConfirmButton:false
    });

    fetch('/ai/priority-refresh/', {
        method:'POST',
        headers:{'X-CSRFToken':getCookie('csrftoken'),'Content-Type':'application/json'}
    })
    .then(r => {
        // Check for rate limit (429 status)
        if (r.status === 429) {
            return r.json().then(data => {
                throw {limitReached: true, message: data.error};
            });
        }
        return r.json();
    })
    .then(data => {
        if (data.success) {
            // Update usage info
            const usageInfo = document.getElementById('usage-info');
            if (usageInfo && data.remaining_usage !== undefined) {
                usageInfo.innerHTML = `<i class="bi bi-info-circle"></i> Sisa refresh hari ini: ${data.remaining_usage}x`;
            }
            
            Swal.fire({ 
                icon:'success', 
                title:'Analysis Complete!',
                html:`<p>Analyzed <strong>${data.analyzed_count}</strong> tasks</p><p class="text-muted small">Sisa refresh hari ini: ${data.remaining_usage}x</p>`,
                timer:2000, 
                showConfirmButton:false 
            });
            setTimeout(() => window.location.reload(), 2000);
        } else {
            Swal.fire({
                icon:'error', 
                title:'Analysis Failed', 
                text:data.error||'Failed'
            }).then(() => { 
                btn.innerHTML = orig; 
                btn.disabled = false; 
            });
        }
    })
    .catch(err => {
        if (err.limitReached) {
            Swal.fire({
                icon:'warning', 
                title:'Limit Tercapai', 
                html:`<p>${err.message}</p><p class="text-muted small">Silakan coba lagi besok.</p>`,
                confirmButtonText: 'Mengerti'
            }).then(() => { 
                btn.innerHTML = orig; 
                btn.disabled = false; 
            });
        } else {
            Swal.fire({icon:'error', title:'Error', text:'An error occurred'})
               .then(() => { 
                   btn.innerHTML = orig; 
                   btn.disabled = false; 
               });
        }
    });
}

/**
 * Get CSRF cookie value
 * @param {string} name - Cookie name
 * @returns {string|null} Cookie value
 */
function getCookie(name) {
    const c = document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith(name+'='));
    return c ? decodeURIComponent(c.split('=')[1]) : null;
}

/**
 * Initialize stats and event listeners on DOM ready
 */
document.addEventListener('DOMContentLoaded', () => {
    // Count priority stats
    let c=0, h=0, m=0, l=0;
    document.querySelectorAll('#priority-table tbody tr').forEach(row => {
        const pill = row.querySelector('.prio-pill');
        if (!pill) return;
        if      (pill.classList.contains('c-red-txt')) c++;
        else if (pill.classList.contains('c-amb-txt')) h++;
        else if (pill.classList.contains('c-blu-txt')) m++;
        else                                            l++;
    });
    
    // Update stat counts
    const criticalCount = document.getElementById('critical-count');
    const highCount = document.getElementById('high-count');
    const mediumCount = document.getElementById('medium-count');
    const lowCount = document.getElementById('low-count');
    
    if (criticalCount) criticalCount.textContent = c;
    if (highCount) highCount.textContent = h;
    if (mediumCount) mediumCount.textContent = m;
    if (lowCount) lowCount.textContent = l;

    // Wire up task links
    document.querySelectorAll('.open-task-modal').forEach(a =>
        a.addEventListener('click', e => {
            e.preventDefault();
            gotoTask(a.dataset.projectId, a.dataset.taskId);
        })
    );
});
