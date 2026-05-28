// ===== DataNexus Frontend =====
const API = '/api/v1';

// ===== Auth =====
const Auth = {
    getToken() { return localStorage.getItem('dn_token'); },
    getRefresh() { return localStorage.getItem('dn_refresh'); },
    getUser() { try { return JSON.parse(localStorage.getItem('dn_user')); } catch { return null; } },
    save(tokens, user) {
        localStorage.setItem('dn_token', tokens.access_token);
        localStorage.setItem('dn_refresh', tokens.refresh_token);
        if (user) localStorage.setItem('dn_user', JSON.stringify(user));
    },
    clear() { localStorage.removeItem('dn_token'); localStorage.removeItem('dn_refresh'); localStorage.removeItem('dn_user'); },
    ok() { return !!this.getToken(); },
    logout() { this.clear(); location.href = '/login'; }
};

// ===== API =====
async function api(path, opts = {}) {
    const h = opts.headers || {};
    if (Auth.getToken()) h['Authorization'] = `Bearer ${Auth.getToken()}`;
    if (!(opts.body instanceof FormData)) h['Content-Type'] = 'application/json';
    const res = await fetch(API + path, { ...opts, headers: h });
    if (res.status === 401) {
        const ok = await refreshToken();
        if (ok) { h['Authorization'] = `Bearer ${Auth.getToken()}`; const r2 = await fetch(API + path, { ...opts, headers: h }); if (!r2.ok) throw await errParse(r2); return r2.status === 204 ? null : r2.json(); }
        Auth.logout(); return;
    }
    if (!res.ok) throw await errParse(res);
    return res.status === 204 ? null : res.json();
}
async function refreshToken() {
    const rt = Auth.getRefresh(); if (!rt) return false;
    try { const r = await fetch(API + '/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: rt }) }); if (!r.ok) return false; Auth.save(await r.json()); return true; } catch { return false; }
}
async function errParse(r) { try { const d = await r.json(); return new Error(d.detail || JSON.stringify(d)); } catch { return new Error('HTTP ' + r.status); } }

// ===== Toast =====
function toast(msg, type = 'info') {
    let c = document.querySelector('.toast-container');
    if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); }
    const t = document.createElement('div'); t.className = `toast toast-${type}`; t.textContent = msg;
    c.appendChild(t); setTimeout(() => t.remove(), 4000);
}

// ===== Theme Toggle (Dark/Light) =====
function getTheme() { return localStorage.getItem('dn_theme') || 'light'; }
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('dn_theme', theme);
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');
    const label = document.getElementById('theme-label');
    if (sunIcon && moonIcon && label) {
        if (theme === 'dark') {
            sunIcon.style.display = 'none';
            moonIcon.style.display = '';
            label.textContent = 'Dark';
        } else {
            sunIcon.style.display = '';
            moonIcon.style.display = 'none';
            label.textContent = 'Light';
        }
    }
}
function toggleTheme() {
    const current = getTheme();
    applyTheme(current === 'light' ? 'dark' : 'light');
}

// ===== Router (proper URLs) =====
const pages = {};
function registerPage(n, fn) { pages[n] = fn; }

function navigate(page) {
    // Push to browser history with proper URL
    const url = '/' + (page === 'dashboard' ? 'dashboard' : page);
    if (location.pathname !== url) {
        history.pushState({ page }, '', url);
    }

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));

    // Update page header
    const titles = {
        dashboard: ['Dashboard', 'Overview of your data extraction pipeline'],
        files: ['OneDrive & Files', 'Connect, browse, and sync your files'],
        chat: ['AI Chat', 'Query your extracted data with natural language'],
        ppt: ['PPT Generator', 'AI-powered presentation generation from your data'],
        settings: ['Settings', 'Configure your platform'],
        admin: ['User Management', 'Manage users, roles, and access permissions'],
        teams: ['My Teams', 'Collaborate and share documents with your team'],
    };
    const t = titles[page] || [page, ''];
    document.getElementById('page-title').textContent = t[0];
    document.getElementById('page-sub').textContent = t[1];
    const hdr = document.getElementById('page-header-actions');
    if (hdr) hdr.innerHTML = '';

    // Stop any timers from previous page
    stopFilesAutoRefresh();

    // Render page
    if (pages[page]) pages[page]();
}

function _applyUserRole(user) {
    if (!user) return;
    // Always refresh localStorage so role is never stale
    localStorage.setItem('dn_user', JSON.stringify(user));

    // Show/hide admin nav item based on role
    const isAdminUser = ['admin', 'superadmin'].includes(user.role);
    document.querySelectorAll('.nav-admin-only').forEach(el => {
        el.style.display = isAdminUser ? '' : 'none';
    });
    const badge = document.getElementById('admin-role-badge');
    if (badge && isAdminUser) {
        badge.textContent = user.role === 'superadmin' ? 'SA' : 'ADM';
        badge.className = 'nav-badge nav-badge-' + (user.role === 'superadmin' ? 'super' : 'admin');
    }
}

async function initApp() {
    // Apply saved theme
    applyTheme(getTheme());

    // Intercept sidebar link clicks for SPA navigation
    document.querySelectorAll('.nav-item[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            navigate(link.dataset.page);
        });
    });

    // Handle browser back/forward
    window.addEventListener('popstate', (e) => {
        const page = getPageFromPath();
        if (pages[page]) navigate(page);
    });

    // Apply role from cached user immediately (fast path — no flicker)
    _applyUserRole(Auth.getUser());

    // Always fetch fresh user data from server so role is never stale
    try {
        const freshUser = await api('/auth/me');
        if (freshUser) _applyUserRole(freshUser);
    } catch { /* token expired → api() auto-refreshes or redirects to login */ }

    // Navigate to current URL
    const page = getPageFromPath();
    navigate(page);
}

function getPageFromPath() {
    const path = location.pathname.replace(/^\//, '').replace(/\/$/, '') || 'dashboard';
    if (!path || path === '') return 'dashboard';
    return pages[path] ? path : 'dashboard';
}

// ─── Role helpers (client-side) ───────────────────────────────────────────────
function userRole() { const u = Auth.getUser(); return (u && u.role) || 'viewer'; }
function isAdmin()  { return ['admin', 'superadmin'].includes(userRole()); }
function isSuperAdmin() { return userRole() === 'superadmin'; }
function canWrite()  { return ['analyst', 'admin', 'superadmin'].includes(userRole()); }
function roleBadgeHtml(role) {
    const map = {
        superadmin: ['role-badge role-superadmin', 'Superadmin'],
        admin:      ['role-badge role-admin',      'Admin'],
        analyst:    ['role-badge role-analyst',    'Analyst'],
        viewer:     ['role-badge role-viewer',     'Viewer'],
        user:       ['role-badge role-analyst',    'Analyst'],
    };
    const [cls, label] = map[role] || ['role-badge role-viewer', role];
    return `<span class="${cls}">${label}</span>`;
}

function getRoleDescription(role) {
    const map = {
        superadmin: 'Full system control — manage users, all data, system settings',
        admin:      'User management + full feature access',
        analyst:    'Full data access: upload files, AI chat, PPT/Excel generation',
        viewer:     'Read-only access: view files and reports',
        user:       'Full data access: upload files, AI chat, PPT/Excel generation',
    };
    return map[role] || 'Standard access';
}

// ===== Helpers =====
function esc(s) { if (!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function timeAgo(d) { const s = (Date.now() - new Date(d)) / 1000; if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s/60) + ' min ago'; if (s < 86400) return Math.floor(s/3600) + 'h ago'; return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
function fmtBytes(b) { if (!b) return '0 B'; const k = 1024, u = ['B','KB','MB','GB']; const i = Math.floor(Math.log(b)/Math.log(k)); return (b/Math.pow(k,i)).toFixed(1) + ' ' + u[i]; }
function fileIconClass(type) { const m = { pdf:'pdf', excel:'excel', xlsx:'excel', xls:'excel', csv:'csv', docx:'docx', doc:'docx', pptx:'pptx', ppt:'pptx', png:'image', jpg:'image', jpeg:'image', tiff:'image', bmp:'image', image:'image' }; return m[(type||'').toLowerCase()] || 'default'; }
function statusIcon(s) {
    if (s === 'completed' || s === 'processed') return '<span class="file-status-icon completed"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span>';
    if (s === 'processing') return '<span class="file-status-icon processing"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.22-8.56"/></svg></span>';
    if (s === 'failed') return '<span class="file-status-icon failed"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></span>';
    return '<span class="file-status-icon pending"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span>';
}
function statusBadge(s) {
    const m = { completed:'processed', processed:'processed', processing:'processing', pending:'pending', queued:'queued', failed:'failed' };
    const cls = m[s] || 'pending';
    return `<span class="badge badge-${cls}">${s}</span>`;
}

// ===== SVG Icons =====
const icons = {
    trend: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    cloud: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
};

// ===== Markdown-lite renderer =====
function renderMarkdown(text) {
    let html = esc(text);
    html = html.replace(/^####\s+(.+)$/gm, '<h5 class="md-h4">$1</h5>');
    html = html.replace(/^###\s+(.+)$/gm, '<h4 class="md-h3">$1</h4>');
    html = html.replace(/^##\s+(.+)$/gm, '<h3 class="md-h2">$1</h3>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/^[•]\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul class="md-list">$1</ul>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = '<p>' + html + '</p>';
    html = html.replace(/<p>\s*<\/p>/g, '');
    return html;
}

// =============================================
// ===== DASHBOARD =====
// =============================================
registerPage('dashboard', async () => {
    const body = document.getElementById('page-body');
    body.innerHTML = '<div style="text-align:center;padding:3rem;"><span class="spinner"></span></div>';
    try {
        const [filesRes, sessions, reports] = await Promise.all([
            api('/files?skip=0&limit=100'), api('/chat/sessions?skip=0&limit=100'), api('/reports?skip=0&limit=100')
        ]);
        const files = filesRes.items || [];
        const total = filesRes.total || files.length;
        const processed = files.filter(f => f.processing_status === 'completed').length;
        const pending = files.filter(f => ['pending','processing'].includes(f.processing_status)).length;
        const pctProcessed = total > 0 ? ((processed / total) * 100).toFixed(1) : 0;

        body.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-card-header">
                        <div class="stat-icon teal"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg></div>
                        <div class="stat-trend">${icons.trend}</div>
                    </div>
                    <div class="stat-value">${total.toLocaleString()}</div>
                    <div class="stat-label">Total Files</div>
                    <div class="stat-sub">+${files.filter(f => { const d = new Date(f.created_at); const t = new Date(); return d.toDateString() === t.toDateString(); }).length} today</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-header">
                        <div class="stat-icon green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
                        <div class="stat-trend">${icons.trend}</div>
                    </div>
                    <div class="stat-value">${processed.toLocaleString()}</div>
                    <div class="stat-label">Processed</div>
                    <div class="stat-sub">${pctProcessed}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-header">
                        <div class="stat-icon blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
                        <div class="stat-trend">${icons.trend}</div>
                    </div>
                    <div class="stat-value">${sessions.length.toLocaleString()}</div>
                    <div class="stat-label">AI Queries</div>
                    <div class="stat-sub">+${sessions.filter(s => { const d = new Date(s.created_at); const now = new Date(); const week = 7*24*60*60*1000; return (now - d) < week; }).length} this week</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-header">
                        <div class="stat-icon cyan">${icons.cloud}</div>
                        <div class="stat-trend">${icons.trend}</div>
                    </div>
                    <div class="stat-value">${reports.length}</div>
                    <div class="stat-label">Reports</div>
                    <div class="stat-sub">${reports.filter(r => r.generation_status === 'completed').length} completed</div>
                </div>
            </div>

            <div class="dashboard-grid">
                <div class="card">
                    <div class="card-header">Recent Files</div>
                    <div class="card-body">
                        ${files.length ? files.slice(0, 5).map(f => `
                            <div class="file-list-item">
                                <div class="file-icon ${fileIconClass(f.file_type)}">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                                </div>
                                <div class="file-info">
                                    <div class="name">${esc(f.filename)}</div>
                                    <div class="meta">${f.file_type} &middot; ${timeAgo(f.created_at)}</div>
                                </div>
                                ${statusIcon(f.processing_status)}
                            </div>
                        `).join('') : '<div class="empty-state"><p>No files uploaded yet</p></div>'}
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">Pipeline Status</div>
                    <div class="card-body">
                        <div class="pipeline-item">
                            <div class="pipeline-label"><span>Download</span><span class="pct">100%</span></div>
                            <div class="progress-bar"><div class="progress-fill" style="width:100%"></div></div>
                        </div>
                        <div class="pipeline-item">
                            <div class="pipeline-label"><span>Extraction</span><span class="pct">${total > 0 ? Math.round((processed/total)*100) : 0}%</span></div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${total > 0 ? Math.round((processed/total)*100) : 0}%"></div></div>
                        </div>
                        <div class="pipeline-item">
                            <div class="pipeline-label"><span>Embedding</span><span class="pct">${total > 0 ? Math.round((processed/total)*80) : 0}%</span></div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${total > 0 ? Math.round((processed/total)*80) : 0}%"></div></div>
                        </div>
                        <div class="pipeline-item">
                            <div class="pipeline-label"><span>Indexing</span><span class="pct">${total > 0 ? Math.round((processed/total)*60) : 0}%</span></div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${total > 0 ? Math.round((processed/total)*60) : 0}%"></div></div>
                        </div>
                        ${pending > 0 ? `<div class="pipeline-footer"><span class="spinner spinner-sm"></span> Processing ${pending} file${pending > 1 ? 's' : ''}...</div>` : ''}
                    </div>
                </div>
            </div>
        `;
    } catch (err) { body.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`; }
});

// =============================================
// ===== FILES (OneDrive & Files) =====
// =============================================
let currentBrowseFolderId = null;
let browseHistory = [];
let _filesScope = 'all';  // 'all' = own + team | 'mine' = own only

registerPage('files', async () => {
    const body = document.getElementById('page-body');
    const hdr = document.getElementById('page-header-actions');

    hdr.innerHTML = `
        <div style="display:flex;gap:0.5rem;">
            <button class="btn btn-outline btn-sm" onclick="processAllPending()" id="process-all-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
                Process All Pending
            </button>
            <button class="btn btn-outline btn-sm" onclick="connectOneDrive()">${icons.cloud} Connect OneDrive</button>
        </div>
    `;

    body.innerHTML = '<div style="text-align:center;padding:3rem;"><span class="spinner"></span></div>';

    try {
        let odStatus = { connected: false };
        try { odStatus = await api('/onedrive/status'); } catch {}
        const filesRes = await api(`/files?skip=0&limit=50&scope=${_filesScope}`);
        const files = filesRes.items || [];

        body.innerHTML = `
            <div class="onedrive-banner">
                <div class="onedrive-banner-icon">${icons.cloud}</div>
                <div class="onedrive-banner-info">
                    <h3>Microsoft OneDrive <span class="badge ${odStatus.connected ? 'badge-connected' : 'badge-disconnected'}">${odStatus.connected ? 'Connected' : 'Not Connected'}</span></h3>
                    <p>${odStatus.connected
                        ? (odStatus.selected_folder ? 'Selected folder: <strong>' + esc(odStatus.selected_folder) + '</strong>' : 'Connected — browse and select a folder to sync')
                        : 'Connect your Microsoft account to sync files'}</p>
                </div>
                ${odStatus.connected && odStatus.selected_folder ? `<button class="btn btn-primary btn-sm" onclick="doSync()" id="sync-btn"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg> Sync Now</button>` : ''}
            </div>

            ${odStatus.connected ? `
                <div class="card browse-card" style="margin-bottom:1.25rem;">
                    <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
                        <span>Browse OneDrive</span>
                        <span id="browse-path" style="font-size:0.78rem;color:var(--text-muted);"></span>
                    </div>
                    <div class="card-body" id="browse-body">
                        <div style="text-align:center;padding:1.5rem;"><span class="spinner"></span></div>
                    </div>
                </div>
            ` : ''}

            <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <h3>Drop files here or click to upload</h3>
                <p>PDF, Excel, CSV, DOCX, PPTX, Images</p>
                <input type="file" id="file-input" hidden accept=".pdf,.xlsx,.xls,.csv,.docx,.pptx,.png,.jpg,.jpeg,.tiff,.bmp" onchange="handleUpload(this)">
            </div>

            <div class="card">
                <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">
                    <div style="display:flex;align-items:center;gap:0.5rem;">
                        <span>Files</span>
                        <div class="files-scope-tabs">
                            <button class="scope-tab ${_filesScope === 'all' ? 'active' : ''}" onclick="setFilesScope('all')">All Files</button>
                            <button class="scope-tab ${_filesScope === 'mine' ? 'active' : ''}" onclick="setFilesScope('mine')">My Files</button>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.5rem;">
                        <input type="text" id="files-search" placeholder="Search files..." onkeyup="handleFilesSearch(this.value)" style="padding:0.35rem 0.75rem;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:0.78rem;background:var(--bg-input);color:var(--text-primary);width:200px;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" width="16" height="16" style="flex-shrink:0;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    </div>
                </div>
                <div class="card-body" id="files-table-body">
                    ${files.length ? renderFilesTable(files) : '<div class="empty-state"><h3>No files yet</h3><p>Upload files or sync from OneDrive</p></div>'}
                </div>
            </div>
        `;

        const zone = document.getElementById('upload-zone');
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--primary)'; });
        zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
        zone.addEventListener('drop', async e => { e.preventDefault(); zone.style.borderColor = ''; if (e.dataTransfer.files.length) await doUpload(e.dataTransfer.files[0]); });

        if (odStatus.connected) {
            currentBrowseFolderId = null;
            browseHistory = [];
            await loadBrowse();
        }

        if (files.some(f => ['pending','processing'].includes(f.processing_status))) {
            startFilesAutoRefresh();
        }
    } catch (err) { body.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`; }
});

async function loadBrowse(folderId) {
    const browseBody = document.getElementById('browse-body');
    if (!browseBody) return;
    browseBody.innerHTML = '<div style="text-align:center;padding:1.5rem;"><span class="spinner"></span> Loading...</div>';
    currentBrowseFolderId = folderId || null;

    const pathEl = document.getElementById('browse-path');
    if (pathEl) {
        const parts = ['<a href="#" onclick="browseBack(-1);return false;" style="color:var(--primary);">Root</a>'];
        browseHistory.forEach((h, i) => {
            parts.push(` / <a href="#" onclick="browseBack(${i});return false;" style="color:var(--primary);">${esc(h.name)}</a>`);
        });
        pathEl.innerHTML = parts.join('');
    }

    try {
        const params = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : '';
        const data = await api('/onedrive/browse' + params);
        const items = data.files || [];

        if (!items.length) {
            browseBody.innerHTML = '<div class="empty-state" style="padding:1.5rem;"><p>This folder is empty</p></div>';
            return;
        }

        const folders = items.filter(i => i.is_folder);
        const files = items.filter(i => !i.is_folder);
        let html = '';

        if (folders.length) {
            html += '<div class="folders-grid">';
            folders.forEach(f => {
                html += `
                    <div class="folder-card" onclick="openFolder('${esc(f.item_id)}', '${esc(f.name)}')" style="cursor:pointer;">
                        <div class="folder-card-header">
                            ${icons.folder}
                            <h4>${esc(f.name)}</h4>
                        </div>
                        <div style="display:flex;gap:0.5rem;margin-top:0.5rem;">
                            <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();selectFolderForSync('${esc(f.item_id)}','${esc(f.name)}')">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                                Select for Sync
                            </button>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        if (files.length) {
            html += '<div style="margin-top:0.75rem;">';
            files.forEach(f => {
                const ext = (f.name || '').split('.').pop().toLowerCase();
                html += `
                    <div class="file-list-item">
                        <div class="file-icon ${fileIconClass(ext)}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                        </div>
                        <div class="file-info">
                            <div class="name">${esc(f.name)}</div>
                            <div class="meta">${fmtBytes(f.size)}${f.last_modified ? ' &middot; ' + timeAgo(f.last_modified) : ''}</div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        if (currentBrowseFolderId) {
            const currentName = browseHistory.length ? browseHistory[browseHistory.length - 1].name : 'Current Folder';
            html += `
                <div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid var(--border);">
                    <button class="btn btn-primary btn-sm" onclick="selectFolderForSync('${esc(currentBrowseFolderId)}','${esc(currentName)}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                        Select "${esc(currentName)}" for Sync
                    </button>
                </div>
            `;
        }

        browseBody.innerHTML = html;
    } catch (err) {
        browseBody.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`;
    }
}

function openFolder(folderId, folderName) {
    browseHistory.push({ id: folderId, name: folderName });
    loadBrowse(folderId);
}

function browseBack(index) {
    if (index < 0) { browseHistory = []; loadBrowse(null); }
    else { const target = browseHistory[index]; browseHistory = browseHistory.slice(0, index + 1); loadBrowse(target.id); }
}

async function selectFolderForSync(folderId, folderName) {
    try {
        await api(`/onedrive/select-folder?folder_id=${encodeURIComponent(folderId)}&folder_name=${encodeURIComponent(folderName)}`, { method: 'POST' });
        toast(`Folder "${folderName}" selected for sync!`, 'success');
        navigate('files');
    } catch (e) { toast(e.message, 'error'); }
}

async function doSync() {
    const btn = document.getElementById('sync-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Syncing...'; }
    try {
        const res = await api('/onedrive/sync', { method: 'POST', body: '{}' });
        toast(res.message || `Synced ${res.files_synced} files`, 'success');
        navigate('files');
        setTimeout(() => startFilesAutoRefresh(), 1000);
    } catch (e) {
        toast(e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg> Sync Now'; }
    }
}

function renderFilesTable(files) {
    // Show owner column only when team files are present
    const hasTeamFiles = files.some(f => f.is_mine === false);
    const ownerCol = hasTeamFiles ? '<th>Owner</th>' : '';
    return `<table class="data-table">
        <thead><tr><th>Name</th><th>Type</th><th>Size</th>${ownerCol}<th>Source</th><th>Date</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${files.map(f => {
            const isMine = f.is_mine !== false;  // default true if field absent
            const ownerCell = hasTeamFiles
                ? `<td>${isMine
                    ? '<span class="file-owner-you">You</span>'
                    : `<span class="file-owner-team">${esc(f.owner_name || 'Team Member')}</span>`}</td>`
                : '';
            return `<tr data-file-id="${f.id}">
            <td><div class="file-name-cell"><div class="file-icon ${fileIconClass(f.file_type)}" style="width:28px;height:28px;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg></div>${esc(f.filename)}</div></td>
            <td>${f.file_type || '-'}</td>
            <td>${fmtBytes(f.file_size)}</td>
            ${ownerCell}
            <td><span class="badge ${f.source === 'onedrive' ? 'badge-connected' : 'badge-pending'}">${f.source || 'upload'}</span></td>
            <td>${timeAgo(f.created_at)}</td>
            <td>${statusBadge(f.processing_status)}</td>
            <td style="display:flex;gap:0.35rem;flex-wrap:wrap;">
                ${f.processing_status === 'completed' ? `<button class="btn btn-outline btn-sm" onclick="viewExtractedData(${f.id})">View Data</button>` : ''}
                ${isMine && (f.processing_status === 'pending' || f.processing_status === 'failed') ? `<button class="btn btn-outline btn-sm" onclick="reprocessFile(${f.id})">Reprocess</button>` : ''}
                ${isMine ? `<button class="btn btn-danger btn-sm" onclick="deleteFile(${f.id})">Delete</button>` : ''}
            </td>
        </tr>`;
        }).join('')}</tbody></table>`;
}

let _filesRefreshTimer = null;
function startFilesAutoRefresh() {
    stopFilesAutoRefresh();
    _filesRefreshTimer = setInterval(async () => {
        try {
            const res = await api(`/files?skip=0&limit=50&scope=${_filesScope}`);
            const files = res.items || [];
            const tbody = document.getElementById('files-table-body');
            if (tbody) {
                tbody.innerHTML = files.length ? renderFilesTable(files) : '<div class="empty-state"><h3>No files yet</h3><p>Upload files or sync from OneDrive</p></div>';
                if (!files.some(f => ['pending','processing'].includes(f.processing_status))) stopFilesAutoRefresh();
            } else { stopFilesAutoRefresh(); }
        } catch { stopFilesAutoRefresh(); }
    }, 5000);
}
function stopFilesAutoRefresh() { if (_filesRefreshTimer) { clearInterval(_filesRefreshTimer); _filesRefreshTimer = null; } }

async function setFilesScope(scope) {
    _filesScope = scope;
    // Update tab active state
    document.querySelectorAll('.scope-tab').forEach(t => t.classList.toggle('active', t.textContent.toLowerCase().includes(scope === 'all' ? 'all' : 'my')));
    // Reload files
    const q = (document.getElementById('files-search') || {}).value || '';
    const params = new URLSearchParams({ skip: 0, limit: 50, scope });
    if (q.trim()) params.set('search', q.trim());
    try {
        const res = await api('/files?' + params.toString());
        const files = res.items || [];
        const tbody = document.getElementById('files-table-body');
        if (tbody) tbody.innerHTML = files.length ? renderFilesTable(files) : `<div class="empty-state"><h3>No files found</h3><p>${scope === 'mine' ? 'You have no uploaded files' : 'No files yet'}</p></div>`;
    } catch {}
}

let _filesSearchTimer = null;
function handleFilesSearch(query) {
    clearTimeout(_filesSearchTimer);
    _filesSearchTimer = setTimeout(async () => {
        try {
            const q = query.trim();
            const params = new URLSearchParams({ skip: 0, limit: 50, scope: _filesScope });
            if (q) params.set('search', q);
            const res = await api('/files?' + params.toString());
            const files = res.items || [];
            const tbody = document.getElementById('files-table-body');
            if (tbody) {
                tbody.innerHTML = files.length ? renderFilesTable(files) : `<div class="empty-state"><h3>No files found</h3><p>${q ? 'No files matching "' + esc(q) + '"' : 'Upload files or sync from OneDrive'}</p></div>`;
            }
        } catch {}
    }, 300);
}

async function viewExtractedData(fileId) {
    try { const data = await api(`/files/${fileId}/extracted-data`); showExtractedDataModal(data); }
    catch (e) { toast(e.message, 'error'); }
}

function showExtractedDataModal(data) {
    document.getElementById('data-modal')?.remove();
    let extractedHtml = '';
    if (data.extracted_data && data.extracted_data.length) {
        extractedHtml = data.extracted_data.map(ed => `
            <div style="margin-bottom:1rem;padding:0.75rem;background:var(--bg-input);border-radius:var(--radius-sm);border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem;">
                    <strong style="font-size:0.82rem;text-transform:capitalize;">${esc(ed.data_type)}</strong>
                    ${ed.source_page ? `<span style="font-size:0.72rem;color:var(--text-muted);">Page ${ed.source_page}</span>` : ''}
                </div>
                ${ed.raw_text ? `<pre style="white-space:pre-wrap;font-size:0.78rem;max-height:200px;overflow-y:auto;color:var(--text-secondary);margin:0;">${esc(ed.raw_text)}</pre>` : ''}
                ${ed.structured_data ? `<details style="margin-top:0.5rem;"><summary style="font-size:0.78rem;color:var(--primary);cursor:pointer;">Structured Data (JSON)</summary><pre style="white-space:pre-wrap;font-size:0.72rem;max-height:200px;overflow-y:auto;color:var(--text-secondary);margin-top:0.25rem;">${esc(JSON.stringify(ed.structured_data, null, 2))}</pre></details>` : ''}
            </div>
        `).join('');
    } else { extractedHtml = '<p style="color:var(--text-muted);font-size:0.85rem;">No extracted data found.</p>'; }

    let chunksHtml = '';
    if (data.chunks && data.chunks.length) {
        chunksHtml = `<div style="margin-top:1rem;"><strong style="font-size:0.88rem;">Document Chunks (${data.total_chunks} total)</strong>
            <div style="margin-top:0.5rem;max-height:300px;overflow-y:auto;">
                ${data.chunks.map(c => `<div style="padding:0.5rem;margin-bottom:0.5rem;background:var(--bg-input);border-radius:var(--radius-xs);border:1px solid var(--border);">
                    <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.25rem;">Chunk #${c.chunk_index}${c.page_number ? ` — Page ${c.page_number}` : ''}</div>
                    <div style="font-size:0.78rem;color:var(--text-secondary);">${esc(c.content)}</div>
                </div>`).join('')}
            </div></div>`;
    }

    const modal = document.createElement('div');
    modal.id = 'data-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.4);';
    modal.innerHTML = `
        <div style="background:var(--bg-white);border-radius:var(--radius);max-width:700px;width:90%;max-height:85vh;overflow-y:auto;box-shadow:var(--shadow-md);padding:1.5rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
                <h3 style="font-size:1.1rem;font-weight:700;">Extracted Data — ${esc(data.filename)}</h3>
                <button onclick="document.getElementById('data-modal').remove()" style="background:none;border:none;font-size:1.3rem;cursor:pointer;color:var(--text-muted);">&times;</button>
            </div>
            <div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap;">
                <span class="badge badge-processed">Status: ${esc(data.processing_status)}</span>
                ${data.page_count ? `<span class="badge badge-processing">${data.page_count} pages</span>` : ''}
                ${data.word_count ? `<span class="badge badge-processing">${data.word_count} words</span>` : ''}
                <span class="badge badge-pending">${data.total_chunks} chunks</span>
            </div>
            ${extractedHtml}${chunksHtml}
        </div>`;
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    document.body.appendChild(modal);
}

async function deleteFile(fileId) {
    showConfirmModal({
        title: 'Delete File',
        icon: '🗑️',
        message: 'Are you sure you want to delete this file? This cannot be undone.',
        confirmText: 'Delete',
        confirmClass: 'btn-danger',
        onConfirm: async () => {
            try { await api('/files/' + fileId, { method: 'DELETE' }); toast('File deleted', 'success'); navigate('files'); }
            catch (e) { toast(e.message, 'error'); }
        },
    });
}

async function reprocessFile(id) {
    try { toast('Reprocessing...', 'info'); await api('/files/' + id + '/reprocess', { method: 'POST' }); toast('Processing started!', 'success'); startFilesAutoRefresh(); }
    catch (e) { toast(e.message, 'error'); }
}

async function processAllPending() {
    const btn = document.getElementById('process-all-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Processing...'; }
    try { const res = await api('/files/process-all-pending', { method: 'POST' }); toast(res.message || 'Processing started!', 'success'); startFilesAutoRefresh(); }
    catch (e) { toast(e.message, 'error'); }
    finally { if (btn) { btn.disabled = false; btn.textContent = 'Process All Pending'; } }
}

async function handleUpload(input) { if (input.files.length) await doUpload(input.files[0]); input.value = ''; }
async function doUpload(file) {
    const fd = new FormData(); fd.append('file', file);
    try { toast('Uploading...', 'info'); await api('/files/upload', { method: 'POST', body: fd }); toast('File uploaded!', 'success'); navigate('files'); setTimeout(() => startFilesAutoRefresh(), 1000); }
    catch (e) { toast(e.message, 'error'); }
}
async function connectOneDrive() {
    try {
        const d = await api('/onedrive/auth-url');
        const w = window.open(d.auth_url, 'onedrive_auth', 'width=600,height=700');
        const poll = setInterval(() => { try { if (w.closed) { clearInterval(poll); navigate('files'); } } catch { clearInterval(poll); navigate('files'); } }, 1000);
    } catch (e) { toast(e.message, 'error'); }
}

// =============================================
// ===== CHAT (with session history) =====
// =============================================
let chatSessionId = null;
let lastAiResponse = null;

registerPage('chat', async () => {
    const body = document.getElementById('page-body');
    chatSessionId = null;
    lastAiResponse = null;

    // Load previous sessions
    let sessions = [];
    try { sessions = await api('/chat/sessions?skip=0&limit=50'); } catch {}

    body.innerHTML = `
        <div class="chat-layout">
            <!-- Chat History Sidebar -->
            <div class="chat-sidebar">
                <button class="new-chat-btn" onclick="startNewChat()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    <span>New Chat</span>
                </button>
                <div class="chat-session-list" id="chat-session-list">
                    ${sessions.length ? sessions.map(s => `
                        <div class="chat-session-item ${chatSessionId === s.id ? 'active' : ''}" data-session-id="${s.id}" onclick="loadChatSession(${s.id})">
                            <div class="session-title">${esc(s.title)}</div>
                            <div class="session-meta">${timeAgo(s.created_at)}</div>
                        </div>
                    `).join('') : '<div class="empty-state" style="padding:1rem;"><p style="font-size:0.78rem;">No previous chats</p></div>'}
                </div>
            </div>

            <!-- Chat Main Area -->
            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    <div class="chat-welcome">
                        <h3>Ask about your data</h3>
                        <p>Query your extracted documents using natural language.<br>AI will search through your files and provide answers with source references.</p>
                    </div>
                </div>
                <div class="chat-suggestions" id="chat-suggestions">
                    <div class="suggestion-chip" onclick="sendSuggestion(this)">Summarize all documents</div>
                    <div class="suggestion-chip" onclick="sendSuggestion(this)">List all equipment from files</div>
                    <div class="suggestion-chip" onclick="sendSuggestion(this)">Show key specifications</div>
                    <div class="suggestion-chip" onclick="sendSuggestion(this)">Create a data summary report</div>
                </div>
                <div class="chat-input-area">
                    <input type="text" id="chat-input" placeholder="Ask about your data..." onkeydown="if(event.key==='Enter')sendChat()">
                    <button class="chat-send-btn" onclick="sendChat()">${icons.send}</button>
                </div>
            </div>
        </div>
    `;
});

function startNewChat() {
    chatSessionId = null;
    lastAiResponse = null;
    const msgs = document.getElementById('chat-messages');
    if (msgs) msgs.innerHTML = `<div class="chat-welcome"><h3>Ask about your data</h3><p>Query your extracted documents using natural language.</p></div>`;
    const sug = document.getElementById('chat-suggestions');
    if (!sug) {
        const container = document.querySelector('.chat-container');
        if (container) {
            const inputArea = container.querySelector('.chat-input-area');
            const sugDiv = document.createElement('div');
            sugDiv.className = 'chat-suggestions';
            sugDiv.id = 'chat-suggestions';
            sugDiv.innerHTML = `
                <div class="suggestion-chip" onclick="sendSuggestion(this)">Summarize all documents</div>
                <div class="suggestion-chip" onclick="sendSuggestion(this)">List all equipment from files</div>
                <div class="suggestion-chip" onclick="sendSuggestion(this)">Show key specifications</div>
                <div class="suggestion-chip" onclick="sendSuggestion(this)">Create a data summary report</div>
            `;
            container.insertBefore(sugDiv, inputArea);
        }
    }
    // Deselect all sessions in sidebar
    document.querySelectorAll('.chat-session-item').forEach(el => el.classList.remove('active'));
}

async function loadChatSession(sessionId) {
    chatSessionId = sessionId;
    lastAiResponse = null;
    const msgs = document.getElementById('chat-messages');
    const sug = document.getElementById('chat-suggestions');
    if (sug) sug.remove();
    msgs.innerHTML = '<div style="text-align:center;padding:2rem;"><span class="spinner"></span></div>';

    // Mark active in sidebar
    document.querySelectorAll('.chat-session-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.sessionId) === sessionId);
    });

    try {
        const history = await api(`/chat/history/${sessionId}`);
        msgs.innerHTML = '';
        (history.messages || []).forEach(msg => {
            if (msg.role === 'user') {
                msgs.innerHTML += `<div class="chat-message user"><div class="msg-avatar">U</div><div class="msg-bubble">${esc(msg.content)}</div></div>`;
            } else {
                let srcHtml = '';
                if (msg.sources_json?.sources?.length) {
                    srcHtml = `<div class="msg-sources">${msg.sources_json.sources.map(s => `<span class="msg-source-tag"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg> ${esc(s.filename)}</span>`).join('')}</div>`;
                }
                // Store last response for excel download
                lastAiResponse = { answer: msg.content, sources: msg.sources_json?.sources || [] };
                msgs.innerHTML += `<div class="chat-message assistant"><div class="msg-avatar">AI</div><div class="msg-bubble"><div class="md-content">${renderMarkdown(msg.content)}</div>${srcHtml}</div></div>`;
            }
        });
        msgs.scrollTop = msgs.scrollHeight;
    } catch (err) {
        msgs.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`;
    }
}

function sendSuggestion(el) { document.getElementById('chat-input').value = el.textContent; sendChat(); }

async function sendChat() {
    const input = document.getElementById('chat-input');
    const q = input.value.trim(); if (!q) return;
    input.value = '';
    const msgs = document.getElementById('chat-messages');
    const sug = document.getElementById('chat-suggestions');
    if (sug) sug.remove();
    if (msgs.querySelector('.chat-welcome')) msgs.innerHTML = '';

    msgs.innerHTML += `<div class="chat-message user"><div class="msg-avatar">U</div><div class="msg-bubble">${esc(q)}</div></div>`;
    msgs.innerHTML += `<div class="chat-message assistant" id="typing"><div class="msg-avatar">AI</div><div class="msg-bubble"><span class="spinner spinner-sm"></span> Thinking...</div></div>`;
    msgs.scrollTop = msgs.scrollHeight;

    try {
        const res = await api('/chat', { method: 'POST', body: JSON.stringify({ query: q, session_id: chatSessionId }) });
        document.getElementById('typing')?.remove();
        chatSessionId = res.session_id;
        lastAiResponse = res;

        let srcHtml = '';
        if (res.sources?.length) {
            srcHtml = `<div class="msg-sources">${res.sources.map(s => `<span class="msg-source-tag"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg> ${esc(s.filename)}</span>`).join('')}</div>`;
        }

        const actionsHtml = `<div class="msg-actions">
            <button class="btn btn-outline btn-sm" onclick="downloadAsExcel()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Download Excel
            </button>
            <button class="btn btn-outline btn-sm" onclick="openPptModal()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                Download PPT
            </button>
            <button class="btn btn-outline btn-sm" onclick="copyResponse()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
                Copy
            </button>
        </div>`;

        msgs.innerHTML += `<div class="chat-message assistant"><div class="msg-avatar">AI</div><div class="msg-bubble"><div class="md-content">${renderMarkdown(res.answer)}</div>${srcHtml}${actionsHtml}</div></div>`;
        msgs.scrollTop = msgs.scrollHeight;

        // Update session list in sidebar
        refreshChatSessions();

    } catch (err) {
        document.getElementById('typing')?.remove();
        msgs.innerHTML += `<div class="chat-message assistant"><div class="msg-avatar">AI</div><div class="msg-bubble" style="color:#dc2626;">Error: ${esc(err.message)}</div></div>`;
    }
}

async function refreshChatSessions() {
    try {
        const sessions = await api('/chat/sessions?skip=0&limit=50');
        const list = document.getElementById('chat-session-list');
        if (!list) return;
        list.innerHTML = sessions.map(s => `
            <div class="chat-session-item ${chatSessionId === s.id ? 'active' : ''}" data-session-id="${s.id}" onclick="loadChatSession(${s.id})">
                <div class="session-title">${esc(s.title)}</div>
                <div class="session-meta">${timeAgo(s.created_at)}</div>
            </div>
        `).join('');
    } catch {}
}

async function downloadAsExcel() {
    if (!lastAiResponse) { toast('No response to download', 'error'); return; }
    try {
        toast('Generating Excel...', 'info');
        const sourceIds = (lastAiResponse.sources || []).map(s => s.file_id).filter((v,i,a) => a.indexOf(v) === i);
        const h = { 'Authorization': `Bearer ${Auth.getToken()}`, 'Content-Type': 'application/json' };
        const res = await fetch(API + '/reports/generate-excel', {
            method: 'POST', headers: h,
            body: JSON.stringify({ content: lastAiResponse.answer, title: 'DataNexus Report', source_file_ids: sourceIds })
        });
        if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'DataNexus_Report.xlsx';
        document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
        toast('Excel downloaded!', 'success');
    } catch (err) { toast('Failed: ' + err.message, 'error'); }
}

function copyResponse() {
    if (!lastAiResponse) return;
    navigator.clipboard.writeText(lastAiResponse.answer).then(() => toast('Copied!', 'success')).catch(() => toast('Copy failed', 'error'));
}

let _chatPptTemplate = 'corporate';

async function openPptModal() {
    if (!lastAiResponse) { toast('No AI response to export', 'error'); return; }
    document.getElementById('ppt-modal-overlay')?.remove();

    // Load templates
    let templates = [];
    try { templates = await api('/reports/templates'); } catch {}
    if (!templates.length) {
        templates = [
            { id: 'corporate',   name: 'Corporate Blue',   preview_colors: ['#002f6c','#0072bd','#e8f1fb','#fff'] },
            { id: 'modern_dark', name: 'Modern Dark',      preview_colors: ['#12121e','#00d4c8','#8155ff','#1a1a2a'] },
            { id: 'dashboard',   name: 'Data Dashboard',   preview_colors: ['#14b8a6','#06b6d4','#f0fdf9','#f8fafc'] },
            { id: 'minimal',     name: 'Minimal Clean',    preview_colors: ['#f9fafb','#6366f1','#14b8a6','#fff'] },
        ];
    }
    _chatPptTemplate = templates[0]?.id || 'corporate';

    const tplCards = templates.map((t, i) => `
        <div class="tpl-card ${i === 0 ? 'selected' : ''}" data-tpl="${esc(t.id)}" onclick="selectChatPptTpl(this)">
            <div class="tpl-swatches-sm">
                ${(t.preview_colors || []).slice(0, 4).map(c =>
                    `<span class="tpl-swatch-sm" style="background:${esc(c)}"></span>`
                ).join('')}
            </div>
            <span>${esc(t.name)}</span>
        </div>
    `).join('');

    const overlay = document.createElement('div');
    overlay.id = 'ppt-modal-overlay';
    overlay.className = 'ppt-modal-overlay';
    overlay.innerHTML = `
        <div class="ppt-modal">
            <div class="ppt-modal-header">
                <h3>Generate Presentation</h3>
                <button class="ppt-modal-close" onclick="closePptModal()">&times;</button>
            </div>
            <div class="ppt-modal-body">
                <div class="form-group">
                    <label>Title</label>
                    <input type="text" id="ppt-modal-title" placeholder="My Presentation">
                </div>
                <div class="form-group">
                    <label>Choose Template</label>
                    <div class="template-grid-sm">${tplCards}</div>
                </div>
                <div class="form-group">
                    <label>Describe Your Presentation</label>
                    <textarea id="ppt-modal-prompt" rows="5" placeholder="Describe what you want in the presentation...">${esc(lastAiResponse.answer || '')}</textarea>
                </div>
            </div>
            <div class="ppt-modal-footer">
                <button class="btn btn-outline" onclick="closePptModal()">Cancel</button>
                <button class="btn btn-primary" id="ppt-modal-generate-btn" onclick="generatePptFromChat()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                    Generate
                </button>
            </div>
        </div>
    `;
    overlay.addEventListener('click', e => { if (e.target === overlay) closePptModal(); });
    document.body.appendChild(overlay);
    document.getElementById('ppt-modal-title')?.focus();
}

function closePptModal() {
    document.getElementById('ppt-modal-overlay')?.remove();
}

function selectChatPptTpl(el) {
    el.closest('.template-grid-sm').querySelectorAll('.tpl-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    _chatPptTemplate = el.dataset.tpl;
}

async function generatePptFromChat() {
    const title = document.getElementById('ppt-modal-title').value.trim() || 'AI Chat Report';
    const prompt = document.getElementById('ppt-modal-prompt').value.trim();
    if (!prompt) { toast('Please provide presentation content', 'error'); return; }

    const btn = document.getElementById('ppt-modal-generate-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Generating...'; }

    try {
        const res = await api('/reports/generate-ppt', {
            method: 'POST',
            body: JSON.stringify({ title, prompt, include_charts: true, template_id: _chatPptTemplate })
        });
        closePptModal();
        toast('Generating presentation in background...', 'success');

        // Poll for completion
        if (res.id) {
            _pollChatPpt(res.id);
        }
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> Generate'; }
    }
}

function _pollChatPpt(reportId) {
    const poll = setInterval(async () => {
        try {
            const report = await api(`/reports/${reportId}`);
            if (report.generation_status === 'completed') {
                clearInterval(poll);
                toast('Presentation ready! Downloading...', 'success');
                // Auto-download
                const a = document.createElement('a');
                a.href = `/api/v1/reports/${report.id}/download?token=${Auth.getToken()}`;
                a.download = `${report.title}.pptx`;
                document.body.appendChild(a); a.click(); a.remove();
            } else if (report.generation_status === 'failed') {
                clearInterval(poll);
                toast('PPT generation failed: ' + (report.error_message || 'Unknown error'), 'error');
            }
        } catch { clearInterval(poll); }
    }, 3000);
}

// =============================================
// ===== PPT GENERATOR =====
// =============================================
let selectedTemplate = 'corporate';
let _pptPollTimer = null;

registerPage('ppt', async () => {
    const body = document.getElementById('page-body');
    selectedTemplate = 'corporate';

    // Load templates from API
    let templates = [];
    try { templates = await api('/reports/templates'); } catch {}
    if (!templates.length) {
        templates = [
            { id: 'corporate',   name: 'Corporate Blue',   description: 'Professional navy blue', preview_colors: ['#002f6c','#0072bd','#e8f1fb','#fff'] },
            { id: 'modern_dark', name: 'Modern Dark',      description: 'Sleek dark with cyan',   preview_colors: ['#12121e','#00d4c8','#8155ff','#1a1a2a'] },
            { id: 'dashboard',   name: 'Data Dashboard',   description: 'Teal KPI-focused theme', preview_colors: ['#14b8a6','#06b6d4','#f0fdf9','#f8fafc'] },
            { id: 'minimal',     name: 'Minimal Clean',    description: 'Light indigo accents',   preview_colors: ['#f9fafb','#6366f1','#14b8a6','#fff'] },
        ];
    }

    const templateCards = templates.map((t, i) => `
        <div class="template-card ${i === 0 ? 'selected' : ''}" data-tpl="${esc(t.id)}" onclick="selectTemplate(this)">
            <div class="tpl-swatches">
                ${(t.preview_colors || []).slice(0, 4).map(c =>
                    `<span class="tpl-swatch" style="background:${esc(c)}"></span>`
                ).join('')}
            </div>
            <h4>${esc(t.name)}</h4>
            <p>${esc(t.description)}</p>
        </div>
    `).join('');

    body.innerHTML = `
        <div class="ppt-layout">
            <div class="ppt-left">
                <div class="card">
                    <div class="card-header">Choose a Template</div>
                    <div class="card-body">
                        <div class="template-grid">${templateCards}</div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">Describe Your Presentation</div>
                    <div class="card-body">
                        <div class="form-group">
                            <textarea id="ppt-prompt" rows="4" placeholder="e.g., Create a summary of all marine equipment data including categories, manufacturers, and specifications..."></textarea>
                        </div>
                        <div class="form-group">
                            <label>Title (optional)</label>
                            <input type="text" id="ppt-title" placeholder="My Presentation">
                        </div>
                        <button class="btn btn-primary-full btn-lg" onclick="generatePPT()" id="ppt-generate-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
                            Generate Presentation
                        </button>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Generated Reports</div>
                <div class="card-body">
                    <div class="ppt-preview" id="ppt-preview">
                        ${icons.monitor}
                        <p>Select a template and generate a presentation</p>
                    </div>
                    <div id="reports-list" style="margin-top:1rem;"></div>
                </div>
            </div>
        </div>
    `;
    await loadReportsList();
});

function selectTemplate(el) {
    document.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedTemplate = el.dataset.tpl;
}

async function generatePPT() {
    const prompt = document.getElementById('ppt-prompt').value.trim();
    const title = document.getElementById('ppt-title').value.trim() || 'My Presentation';
    if (!prompt) { toast('Please describe your presentation', 'error'); return; }

    const btn = document.getElementById('ppt-generate-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Generating...'; }

    try {
        const res = await api('/reports/generate-ppt', { method: 'POST', body: JSON.stringify({ title, prompt, include_charts: true, template_id: selectedTemplate }) });
        toast('Generating presentation in background...', 'success');
        document.getElementById('ppt-prompt').value = '';
        document.getElementById('ppt-title').value = '';

        // Show status in preview
        const preview = document.getElementById('ppt-preview');
        if (preview) {
            preview.innerHTML = `<span class="spinner"></span><p style="margin-top:0.75rem;">Generating "${esc(title)}"...<br><span style="font-size:0.78rem;color:var(--text-muted);">This may take 30-60 seconds</span></p>`;
        }

        // Poll for completion
        if (res.id) {
            startPPTPoll(res.id);
        }

        await loadReportsList();
    } catch (e) { toast(e.message, 'error'); }
    finally { if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> Generate Presentation'; } }
}

function startPPTPoll(reportId) {
    if (_pptPollTimer) clearInterval(_pptPollTimer);
    _pptPollTimer = setInterval(async () => {
        try {
            const report = await api(`/reports/${reportId}`);
            if (report.generation_status === 'completed') {
                clearInterval(_pptPollTimer); _pptPollTimer = null;
                toast('Presentation ready! Click Download.', 'success');
                const preview = document.getElementById('ppt-preview');
                if (preview) {
                    preview.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2" style="width:48px;height:48px;margin-bottom:0.75rem;"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        <p style="color:var(--primary);font-weight:600;">"${esc(report.title)}" is ready!</p>
                        <a href="/api/v1/reports/${report.id}/download?token=${Auth.getToken()}" class="btn btn-primary" style="margin-top:0.75rem;">Download PPTX</a>
                    `;
                }
                await loadReportsList();
            } else if (report.generation_status === 'failed') {
                clearInterval(_pptPollTimer); _pptPollTimer = null;
                toast('Generation failed: ' + (report.error_message || 'Unknown error'), 'error');
                const preview = document.getElementById('ppt-preview');
                if (preview) { preview.innerHTML = `<p style="color:#dc2626;">Failed: ${esc(report.error_message || 'Unknown error')}</p>`; }
                await loadReportsList();
            }
        } catch { clearInterval(_pptPollTimer); _pptPollTimer = null; }
    }, 3000);
}

async function loadReportsList() {
    const el = document.getElementById('reports-list');
    if (!el) return;
    try {
        const reports = await api('/reports?skip=0&limit=10');
        if (!reports.length) { el.innerHTML = '<div class="empty-state" style="padding:1rem;"><p style="font-size:0.82rem;">No reports generated yet</p></div>'; return; }
        el.innerHTML = reports.map(r => `
            <div class="file-list-item">
                <div class="file-icon pptx" style="width:32px;height:32px;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                </div>
                <div class="file-info">
                    <div class="name">${esc(r.title)}</div>
                    <div class="meta">${timeAgo(r.created_at)}</div>
                </div>
                ${r.generation_status === 'completed' && r.file_path
                    ? `<a href="/api/v1/reports/${r.id}/download?token=${Auth.getToken()}" class="btn btn-outline btn-sm">Download</a>`
                    : r.generation_status === 'failed'
                        ? `<span class="badge badge-failed" title="${esc(r.error_message || '')}">${r.generation_status}</span>`
                        : statusBadge(r.generation_status)}
            </div>
        `).join('');
    } catch {}
}

// =============================================
// ===== SETTINGS =====
// =============================================
registerPage('settings', () => {
    const body = document.getElementById('page-body');
    const user = Auth.getUser();
    body.innerHTML = `
        <div style="max-width:560px;">
            <div class="card" style="margin-bottom:1rem;">
                <div class="card-header">Profile</div>
                <div class="card-body">
                    <div class="form-group"><label>Full Name</label><input type="text" value="${esc(user?.full_name || '')}" disabled></div>
                    <div class="form-group"><label>Email</label><input type="email" value="${esc(user?.email || '')}" disabled></div>
                    <div class="form-group">
                        <label>Role &amp; Access Level</label>
                        <div style="display:flex;align-items:center;gap:0.6rem;margin-top:0.25rem;">
                            ${roleBadgeHtml(user?.role || 'viewer')}
                            <span style="font-size:0.8rem;color:var(--text-muted);">${getRoleDescription(user?.role)}</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card" style="margin-bottom:1rem;">
                <div class="card-header">Appearance</div>
                <div class="card-body">
                    <div class="form-group">
                        <label>Theme</label>
                        <select onchange="applyTheme(this.value)">
                            <option value="light" ${getTheme()==='light'?'selected':''}>Light</option>
                            <option value="dark" ${getTheme()==='dark'?'selected':''}>Dark</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="card" style="margin-bottom:1rem;">
                <div class="card-header">OneDrive Configuration</div>
                <div class="card-body">
                    <p style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:1rem;">Configure Microsoft OneDrive integration in your <code>.env</code> file.</p>
                    <div class="form-group"><label>MS_CLIENT_ID</label><input type="text" value="Configured in .env" disabled></div>
                    <div class="form-group"><label>MS_CLIENT_SECRET</label><input type="password" value="Configured in .env" disabled></div>
                </div>
            </div>
            <button class="btn btn-danger" onclick="Auth.logout()">Sign Out</button>
        </div>
    `;
});

// =============================================
// ===== ADMIN — User Management =====
// =============================================
let _adminState = { skip: 0, limit: 20, search: '', role: '', active: '' };

registerPage('admin', async () => {
    if (!isAdmin()) { navigate('dashboard'); toast('Access denied', 'error'); return; }
    const body = document.getElementById('page-body');
    body.innerHTML = '<div style="text-align:center;padding:3rem;"><span class="spinner"></span></div>';

    // Load stats + first page
    try {
        const [stats] = await Promise.all([api('/admin/stats')]);
        _adminState = { skip: 0, limit: 20, search: '', role: '', active: '' };
        renderAdminPage(body, stats);
        await loadAdminUsers();
    } catch (e) { body.innerHTML = `<div class="empty-state"><p style="color:#dc2626;">${esc(e.message)}</p></div>`; }
});

function renderAdminPage(body, stats) {
    const roleBD = stats.roles_breakdown || {};
    body.innerHTML = `
        <!-- Stats Row -->
        <div class="admin-stats-row">
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-blue">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.total_users}</div><div class="admin-stat-label">Total Users</div></div>
            </div>
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-green">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.active_users}</div><div class="admin-stat-label">Active</div></div>
            </div>
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-orange">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.inactive_users}</div><div class="admin-stat-label">Inactive</div></div>
            </div>
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-purple">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.total_files}</div><div class="admin-stat-label">Total Files</div></div>
            </div>
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-teal">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.total_reports}</div><div class="admin-stat-label">Reports</div></div>
            </div>
            <div class="admin-stat-card">
                <div class="admin-stat-icon admin-stat-red">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
                </div>
                <div><div class="admin-stat-num">${stats.total_chat_sessions}</div><div class="admin-stat-label">Chat Sessions</div></div>
            </div>
        </div>

        <!-- Roles breakdown chips -->
        <div class="admin-roles-row">
            ${Object.entries(roleBD).map(([r,c]) => `<span class="role-chip">${roleBadgeHtml(r)} <strong>${c}</strong></span>`).join('')}
        </div>

        <!-- Toolbar -->
        <div class="admin-toolbar">
            <div class="admin-search-group">
                <input type="text" id="admin-search" placeholder="Search by name or email..." class="admin-search-input" oninput="debouncedAdminSearch()" value="${esc(_adminState.search)}">
                <select id="admin-role-filter" class="admin-filter-select" onchange="adminFilterChange()">
                    <option value="">All Roles</option>
                    <option value="superadmin">Superadmin</option>
                    <option value="admin">Admin</option>
                    <option value="analyst">Analyst</option>
                    <option value="viewer">Viewer</option>
                </select>
                <select id="admin-active-filter" class="admin-filter-select" onchange="adminFilterChange()">
                    <option value="">All Status</option>
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                </select>
            </div>
            <button class="btn btn-primary" onclick="openCreateUserModal()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Create User
            </button>
        </div>

        <!-- User Table -->
        <div class="card" style="overflow:auto;">
            <table class="admin-user-table" id="admin-user-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Joined</th>
                        <th style="text-align:right;">Actions</th>
                    </tr>
                </thead>
                <tbody id="admin-user-tbody">
                    <tr><td colspan="5" style="text-align:center;padding:2rem;"><span class="spinner"></span></td></tr>
                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        <div class="admin-pagination" id="admin-pagination"></div>
    `;
}

async function loadAdminUsers() {
    const tbody = document.getElementById('admin-user-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;"><span class="spinner"></span></td></tr>';

    try {
        const params = new URLSearchParams({ skip: _adminState.skip, limit: _adminState.limit });
        if (_adminState.search) params.set('search', _adminState.search);
        if (_adminState.role) params.set('role', _adminState.role);
        if (_adminState.active !== '') params.set('active', _adminState.active);

        const data = await api('/admin/users?' + params.toString());
        renderAdminUserTable(data);
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="color:#dc2626;padding:1rem;">${esc(e.message)}</td></tr>`;
    }
}

function renderAdminUserTable(data) {
    const tbody = document.getElementById('admin-user-tbody');
    if (!tbody) return;
    const meId = Auth.getUser()?.id;

    if (!data.items || !data.items.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted);">No users found</td></tr>';
    } else {
        tbody.innerHTML = data.items.map(u => `
            <tr class="${u.is_active ? '' : 'admin-row-inactive'}">
                <td>
                    <div class="admin-user-cell">
                        <div class="admin-avatar" style="background:${avatarColor(u.full_name)}">
                            ${initials(u.full_name)}
                        </div>
                        <div>
                            <div class="admin-user-name">${esc(u.full_name)} ${u.id === meId ? '<span class="admin-you-badge">You</span>' : ''}</div>
                            <div class="admin-user-email">${esc(u.email)}</div>
                        </div>
                    </div>
                </td>
                <td>${roleBadgeHtml(u.role)}</td>
                <td>
                    <span class="admin-status-dot ${u.is_active ? 'active' : 'inactive'}"></span>
                    ${u.is_active ? 'Active' : 'Inactive'}
                </td>
                <td style="color:var(--text-muted);font-size:0.82rem;">${new Date(u.created_at).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}</td>
                <td>
                    <div class="admin-actions">
                        <button class="btn btn-outline btn-sm" onclick="openEditUserModal(${u.id},'${esc(u.full_name)}','${esc(u.email)}','${u.role}',${u.is_active})" title="Edit">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            Edit
                        </button>
                        ${u.id !== meId ? `
                        <button class="btn ${u.is_active ? 'btn-warning' : 'btn-success'} btn-sm" onclick="toggleUserActive(${u.id},'${esc(u.full_name)}')" title="${u.is_active ? 'Deactivate' : 'Activate'}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${u.is_active ? '<path d="M18.36 6.64a9 9 0 11-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>' : '<path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'}
                            </svg>
                            ${u.is_active ? 'Deactivate' : 'Activate'}
                        </button>` : ''}
                        ${isSuperAdmin() && u.id !== meId ? `
                        <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id},'${esc(u.full_name)}')" title="Delete">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `).join('');
    }

    // Pagination
    const pg = document.getElementById('admin-pagination');
    if (pg) {
        const totalPages = Math.ceil(data.total / _adminState.limit);
        const curPage = Math.floor(_adminState.skip / _adminState.limit) + 1;
        pg.innerHTML = data.total > _adminState.limit ? `
            <span style="font-size:0.82rem;color:var(--text-muted);">Showing ${_adminState.skip + 1}–${Math.min(_adminState.skip + _adminState.limit, data.total)} of ${data.total} users</span>
            <div class="admin-pg-btns">
                <button class="btn btn-outline btn-sm" onclick="adminChangePage(-1)" ${curPage <= 1 ? 'disabled' : ''}>Previous</button>
                <span style="padding:0 0.5rem;font-size:0.85rem;">Page ${curPage} / ${totalPages}</span>
                <button class="btn btn-outline btn-sm" onclick="adminChangePage(1)" ${!data.has_more ? 'disabled' : ''}>Next</button>
            </div>
        ` : `<span style="font-size:0.82rem;color:var(--text-muted);">${data.total} user${data.total !== 1 ? 's' : ''}</span>`;
    }
}

function adminChangePage(dir) {
    _adminState.skip = Math.max(0, _adminState.skip + dir * _adminState.limit);
    loadAdminUsers();
}

let _adminSearchTimer = null;
function debouncedAdminSearch() {
    clearTimeout(_adminSearchTimer);
    _adminSearchTimer = setTimeout(() => {
        _adminState.search = document.getElementById('admin-search')?.value || '';
        _adminState.skip = 0;
        loadAdminUsers();
    }, 350);
}

function adminFilterChange() {
    _adminState.role   = document.getElementById('admin-role-filter')?.value || '';
    _adminState.active = document.getElementById('admin-active-filter')?.value || '';
    _adminState.skip = 0;
    loadAdminUsers();
}

// ─── Create User Modal ─────────────────────────────────────────────────────────
function openCreateUserModal() {
    const meRole = userRole();
    const roleOptions = meRole === 'superadmin'
        ? ['superadmin','admin','analyst','viewer']
        : ['analyst','viewer'];

    showModal('create-user-modal', `
        <div class="modal-header">
            <h3>Create New User</h3>
            <button class="modal-close" onclick="closeModal('create-user-modal')">&times;</button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label>Full Name <span class="req">*</span></label>
                <input type="text" id="cu-name" placeholder="Jane Doe" class="form-control">
            </div>
            <div class="form-group">
                <label>Email Address <span class="req">*</span></label>
                <input type="email" id="cu-email" placeholder="jane@company.com" class="form-control">
            </div>
            <div class="form-group">
                <label>Password <span class="req">*</span></label>
                <input type="password" id="cu-password" placeholder="Min. 8 characters" class="form-control">
            </div>
            <div class="form-group">
                <label>Role <span class="req">*</span></label>
                <select id="cu-role" class="form-control">
                    ${roleOptions.map(r => `<option value="${r}" ${r==='analyst'?'selected':''}>${r.charAt(0).toUpperCase()+r.slice(1)}</option>`).join('')}
                </select>
                <div class="form-hint">
                    <strong>Analyst</strong>: Full data access (upload, chat, reports)<br>
                    <strong>Viewer</strong>: Read-only access (view files &amp; reports only)<br>
                    ${meRole === 'superadmin' ? '<strong>Admin</strong>: Manage users + all features<br><strong>Superadmin</strong>: Full system control' : ''}
                </div>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal('create-user-modal')">Cancel</button>
            <button class="btn btn-primary" id="cu-submit" onclick="submitCreateUser()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Create User
            </button>
        </div>
    `);
}

async function submitCreateUser() {
    const name = document.getElementById('cu-name')?.value.trim();
    const email = document.getElementById('cu-email')?.value.trim();
    const password = document.getElementById('cu-password')?.value;
    const role = document.getElementById('cu-role')?.value;

    if (!name || !email || !password) { toast('All fields are required', 'error'); return; }
    if (password.length < 8) { toast('Password must be at least 8 characters', 'error'); return; }

    const btn = document.getElementById('cu-submit');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Creating...'; }

    try {
        const user = await api('/admin/users', { method: 'POST', body: JSON.stringify({ full_name: name, email, password, role }) });
        closeModal('create-user-modal');
        toast(`User "${user.full_name}" created successfully`, 'success');
        _adminState.skip = 0;
        await loadAdminUsers();
    } catch (e) {
        toast(e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = 'Create User'; }
    }
}

// ─── Edit User Modal ───────────────────────────────────────────────────────────
function openEditUserModal(id, name, email, role, isActive) {
    const meRole = userRole();
    const canEditRole = meRole === 'superadmin' || (meRole === 'admin' && !['admin','superadmin'].includes(role));
    const roleOptions = meRole === 'superadmin'
        ? ['superadmin','admin','analyst','viewer']
        : ['analyst','viewer'];

    showModal('edit-user-modal', `
        <div class="modal-header">
            <h3>Edit User</h3>
            <button class="modal-close" onclick="closeModal('edit-user-modal')">&times;</button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" id="eu-name" value="${esc(name)}" class="form-control">
            </div>
            <div class="form-group">
                <label>Email Address</label>
                <input type="email" id="eu-email" value="${esc(email)}" class="form-control">
            </div>
            <div class="form-group">
                <label>Role</label>
                ${canEditRole ? `
                    <select id="eu-role" class="form-control">
                        ${roleOptions.map(r => `<option value="${r}" ${r===role?'selected':''}>${r.charAt(0).toUpperCase()+r.slice(1)}</option>`).join('')}
                    </select>` : `
                    <input type="text" value="${role.charAt(0).toUpperCase()+role.slice(1)}" disabled class="form-control">
                    <div class="form-hint">You cannot change this user's role.</div>`}
            </div>
            <div class="form-group">
                <label>Status</label>
                <select id="eu-active" class="form-control">
                    <option value="true" ${isActive ? 'selected' : ''}>Active</option>
                    <option value="false" ${!isActive ? 'selected' : ''}>Inactive</option>
                </select>
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal('edit-user-modal')">Cancel</button>
            <button class="btn btn-primary" id="eu-submit" onclick="submitEditUser(${id},'${esc(role)}',${canEditRole})">
                Save Changes
            </button>
        </div>
    `);
}

async function submitEditUser(id, originalRole, canEditRole) {
    const name  = document.getElementById('eu-name')?.value.trim();
    const email = document.getElementById('eu-email')?.value.trim();
    const role  = canEditRole ? document.getElementById('eu-role')?.value : originalRole;
    const active = document.getElementById('eu-active')?.value === 'true';

    if (!name || !email) { toast('Name and email are required', 'error'); return; }

    const btn = document.getElementById('eu-submit');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-sm"></span> Saving...'; }

    try {
        await api(`/admin/users/${id}`, { method: 'PUT', body: JSON.stringify({ full_name: name, email, role, is_active: active }) });
        closeModal('edit-user-modal');
        toast('User updated successfully', 'success');
        await loadAdminUsers();
    } catch (e) {
        toast(e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = 'Save Changes'; }
    }
}

// ─── Toggle Active ─────────────────────────────────────────────────────────────
function toggleUserActive(id, name) {
    showConfirmModal({
        title: 'Change User Status',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#f59e0b"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
        message: `Are you sure you want to toggle the active status for <strong>${esc(name)}</strong>?<br><span style="font-size:0.82rem;color:var(--text-muted);margin-top:0.4rem;display:block;">Inactive users cannot log in until reactivated.</span>`,
        confirmText: 'Yes, Toggle Status',
        confirmClass: 'btn-warning',
        onConfirm: async () => {
            try {
                const u = await api(`/admin/users/${id}/toggle-active`, { method: 'PATCH' });
                toast(`${name} is now ${u.is_active ? 'active' : 'inactive'}`, 'success');
                await loadAdminUsers();
            } catch (e) { toast(e.message, 'error'); }
        }
    });
}

// ─── Delete User ───────────────────────────────────────────────────────────────
function deleteUser(id, name) {
    showConfirmModal({
        title: 'Delete User',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#ef4444"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>`,
        message: `You are about to permanently delete <strong>${esc(name)}</strong> and <strong>all their data</strong> including files, reports, and chat history.<br><span style="font-size:0.82rem;color:#ef4444;margin-top:0.5rem;display:block;font-weight:600;">⚠ This action cannot be undone.</span>`,
        confirmText: 'Delete Permanently',
        confirmClass: 'btn-danger',
        onConfirm: async () => {
            try {
                await api(`/admin/users/${id}`, { method: 'DELETE' });
                toast(`"${name}" has been deleted`, 'success');
                await loadAdminUsers();
            } catch (e) { toast(e.message, 'error'); }
        }
    });
}

// ─── Modal helpers ─────────────────────────────────────────────────────────────
function showModal(id, html) {
    let overlay = document.getElementById('modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'modal-overlay';
        overlay.className = 'modal-overlay';
        document.body.appendChild(overlay);
    }
    overlay.onclick = (e) => { if (e.target === overlay) closeModal(id); };
    overlay.innerHTML = `<div class="modal" id="${id}">${html}</div>`;
    overlay.style.display = 'flex';
    requestAnimationFrame(() => overlay.querySelector('.modal')?.classList.add('modal-in'));
}

function closeModal(id) {
    const overlay = document.getElementById('modal-overlay');
    if (overlay) { overlay.style.display = 'none'; overlay.innerHTML = ''; }
}

// ─── Confirm modal (replaces browser confirm()) ────────────────────────────────
function showConfirmModal({ title, icon, message, confirmText = 'Confirm', confirmClass = 'btn-primary', onConfirm }) {
    const id = 'confirm-modal';
    showModal(id, `
        <div class="modal-header" style="border-bottom:none;padding-bottom:0.5rem;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
                <span class="confirm-modal-icon">${icon || ''}</span>
                <h3 style="font-size:1rem;font-weight:700;">${esc(title)}</h3>
            </div>
            <button class="modal-close" onclick="closeModal('${id}')">&times;</button>
        </div>
        <div class="modal-body" style="padding-top:0.5rem;">
            <p class="confirm-modal-msg">${message}</p>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal('${id}')">Cancel</button>
            <button class="btn ${confirmClass}" id="confirm-modal-ok">${confirmText}</button>
        </div>
    `);

    // Wire confirm button after render
    requestAnimationFrame(() => {
        const okBtn = document.getElementById('confirm-modal-ok');
        if (okBtn) {
            okBtn.onclick = async () => {
                okBtn.disabled = true;
                okBtn.innerHTML = '<span class="spinner spinner-sm"></span>';
                closeModal(id);
                await onConfirm();
            };
        }
    });
}

// ─── Avatar helpers ────────────────────────────────────────────────────────────
function initials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase();
}
function avatarColor(name) {
    const colors = ['#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444','#06b6d4'];
    let h = 0; for (const c of (name || '')) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
    return colors[Math.abs(h) % colors.length];
}

// =============================================
// ===== TEAMS =====
// =============================================
let _activeTeamId = null;

registerPage('teams', async () => {
    const body = document.getElementById('page-body');
    const hdr  = document.getElementById('page-header-actions');

    hdr.innerHTML = canWrite() ? `
        <button class="btn btn-primary btn-sm" onclick="openCreateTeamModal()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Create Team
        </button>` : '';

    body.innerHTML = '<div style="text-align:center;padding:3rem;"><span class="spinner"></span></div>';
    await loadTeamsPage(body);
});

async function loadTeamsPage(body) {
    body = body || document.getElementById('page-body');
    try {
        const teams = await api('/teams');
        if (!teams || teams.length === 0) {
            body.innerHTML = `
                <div class="teams-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="56" height="56" style="color:var(--text-muted);margin-bottom:1rem;"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                    <h3>No teams yet</h3>
                    <p>Create a team to share documents with your colleagues.</p>
                    ${canWrite() ? `<button class="btn btn-primary" onclick="openCreateTeamModal()" style="margin-top:1rem;">Create Your First Team</button>` : ''}
                </div>`;
            return;
        }

        body.innerHTML = `<div class="teams-grid" id="teams-grid">${teams.map(renderTeamCard).join('')}</div>`;
    } catch (err) {
        body.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`;
    }
}

function renderTeamCard(team) {
    const isOwner = team.your_role === 'owner';
    const memberWord = team.member_count === 1 ? 'member' : 'members';
    const avatarColor1 = avatarColor(team.name);
    return `
        <div class="team-card" id="team-card-${team.id}">
            <div class="team-card-header">
                <div class="team-avatar" style="background:${avatarColor1};">${initials(team.name)}</div>
                <div class="team-card-info">
                    <div class="team-name">${esc(team.name)}</div>
                    <div class="team-meta">${team.member_count} ${memberWord} &middot; ${isOwner ? '<span class="team-role-owner">Owner</span>' : '<span class="team-role-member">Member</span>'}</div>
                </div>
            </div>
            ${team.description ? `<p class="team-desc">${esc(team.description)}</p>` : ''}
            <div class="team-card-actions">
                <button class="btn btn-outline btn-sm" onclick="openTeamDetail(${team.id})">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
                    Manage Members
                </button>
                ${isOwner ? `
                    <button class="btn btn-outline btn-sm" onclick="openEditTeamModal(${team.id},'${esc(team.name)}','${esc(team.description||'')}')">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteTeam(${team.id},'${esc(team.name)}')">Delete</button>
                ` : `
                    <button class="btn btn-outline btn-sm" onclick="leaveTeam(${team.id},'${esc(team.name)}')">Leave</button>
                `}
            </div>
        </div>`;
}

// ── Team Detail Modal ─────────────────────────────────────────────────────────
async function openTeamDetail(teamId) {
    _activeTeamId = teamId;
    showModal('team-detail-modal', `
        <div class="modal-header">
            <h3>Team Members</h3>
            <button class="modal-close" onclick="closeModal('team-detail-modal')">&times;</button>
        </div>
        <div class="modal-body" id="team-detail-body">
            <div style="text-align:center;padding:2rem;"><span class="spinner"></span></div>
        </div>`);
    await loadTeamDetail(teamId);
}

async function loadTeamDetail(teamId) {
    const body = document.getElementById('team-detail-body');
    if (!body) return;
    try {
        const team = await api(`/teams/${teamId}`);
        const isOwner = team.your_role === 'owner';
        body.innerHTML = `
            <div style="margin-bottom:1rem;">
                <div style="font-size:1rem;font-weight:700;">${esc(team.name)}</div>
                ${team.description ? `<div style="font-size:0.82rem;color:var(--text-muted);margin-top:0.25rem;">${esc(team.description)}</div>` : ''}
            </div>
            ${isOwner ? `
                <div class="team-add-member-row">
                    <input type="email" id="add-member-email" placeholder="Email address to invite..." class="form-control" style="flex:1;">
                    <button class="btn btn-primary btn-sm" onclick="addTeamMember(${teamId})">Add Member</button>
                </div>` : ''}
            <div style="font-size:0.78rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:0.5rem;">
                ${team.member_count} Member${team.member_count !== 1 ? 's' : ''}
            </div>
            <div class="team-members-list">
                ${team.members.map(m => renderMemberRow(m, isOwner, team.members)).join('')}
            </div>`;
    } catch (err) {
        body.innerHTML = `<div class="alert alert-error" style="display:block">${esc(err.message)}</div>`;
    }
}

function renderMemberRow(m, isOwner, allMembers) {
    const currentUser = Auth.getUser();
    const isMe = currentUser && m.user_id === currentUser.id;
    const canRemove = isOwner && !isMe && m.role !== 'owner';
    return `
        <div class="team-member-row">
            <div class="team-member-avatar" style="background:${avatarColor(m.full_name)};">${initials(m.full_name)}</div>
            <div class="team-member-info">
                <div class="team-member-name">${esc(m.full_name)} ${isMe ? '<span class="file-owner-you">You</span>' : ''}</div>
                <div class="team-member-email">${esc(m.email)}</div>
            </div>
            <span class="team-member-role ${m.role === 'owner' ? 'role-owner' : 'role-member'}">${m.role}</span>
            ${canRemove ? `<button class="btn btn-danger btn-sm" onclick="removeTeamMember(${_activeTeamId},${m.user_id},'${esc(m.full_name)}')">Remove</button>` : ''}
        </div>`;
}

async function addTeamMember(teamId) {
    const input = document.getElementById('add-member-email');
    const email = (input?.value || '').trim();
    if (!email) { toast('Enter an email address', 'error'); return; }
    try {
        await api(`/teams/${teamId}/members`, {
            method: 'POST',
            body: JSON.stringify({ email }),
        });
        toast(`Member added!`, 'success');
        if (input) input.value = '';
        await loadTeamDetail(teamId);
        await refreshTeamCard(teamId);
    } catch (e) { toast(e.message, 'error'); }
}

async function removeTeamMember(teamId, userId, name) {
    showConfirmModal({
        title: 'Remove Member',
        icon: '👤',
        message: `Remove <strong>${esc(name)}</strong> from this team?`,
        confirmText: 'Remove',
        confirmClass: 'btn-danger',
        onConfirm: async () => {
            try {
                await api(`/teams/${teamId}/members/${userId}`, { method: 'DELETE' });
                toast(`${name} removed from team`, 'success');
                await loadTeamDetail(teamId);
                await refreshTeamCard(teamId);
            } catch (e) { toast(e.message, 'error'); }
        },
    });
}

// ── Create Team Modal ──────────────────────────────────────────────────────────
function openCreateTeamModal() {
    showModal('create-team-modal', `
        <div class="modal-header">
            <h3>Create New Team</h3>
            <button class="modal-close" onclick="closeModal('create-team-modal')">&times;</button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label>Team Name <span style="color:var(--danger)">*</span></label>
                <input type="text" id="new-team-name" class="form-control" placeholder="e.g. Analytics Team" maxlength="100">
            </div>
            <div class="form-group">
                <label>Description <span style="font-size:0.75rem;color:var(--text-muted);">(optional)</span></label>
                <input type="text" id="new-team-desc" class="form-control" placeholder="What does this team work on?">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal('create-team-modal')">Cancel</button>
            <button class="btn btn-primary" onclick="submitCreateTeam()">Create Team</button>
        </div>`);
    requestAnimationFrame(() => document.getElementById('new-team-name')?.focus());
}

async function submitCreateTeam() {
    const name = (document.getElementById('new-team-name')?.value || '').trim();
    const desc = (document.getElementById('new-team-desc')?.value || '').trim();
    if (!name) { toast('Team name is required', 'error'); return; }
    try {
        await api('/teams', {
            method: 'POST',
            body: JSON.stringify({ name, description: desc || null }),
        });
        closeModal('create-team-modal');
        toast(`Team "${name}" created!`, 'success');
        await loadTeamsPage();
    } catch (e) { toast(e.message, 'error'); }
}

// ── Edit Team Modal ────────────────────────────────────────────────────────────
function openEditTeamModal(teamId, currentName, currentDesc) {
    showModal('edit-team-modal', `
        <div class="modal-header">
            <h3>Edit Team</h3>
            <button class="modal-close" onclick="closeModal('edit-team-modal')">&times;</button>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label>Team Name</label>
                <input type="text" id="edit-team-name" class="form-control" value="${esc(currentName)}" maxlength="100">
            </div>
            <div class="form-group">
                <label>Description</label>
                <input type="text" id="edit-team-desc" class="form-control" value="${esc(currentDesc)}">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal('edit-team-modal')">Cancel</button>
            <button class="btn btn-primary" onclick="submitEditTeam(${teamId})">Save Changes</button>
        </div>`);
}

async function submitEditTeam(teamId) {
    const name = (document.getElementById('edit-team-name')?.value || '').trim();
    const desc = (document.getElementById('edit-team-desc')?.value || '').trim();
    if (!name) { toast('Team name cannot be empty', 'error'); return; }
    try {
        await api(`/teams/${teamId}`, {
            method: 'PUT',
            body: JSON.stringify({ name, description: desc || null }),
        });
        closeModal('edit-team-modal');
        toast('Team updated!', 'success');
        await loadTeamsPage();
    } catch (e) { toast(e.message, 'error'); }
}

// ── Delete / Leave ─────────────────────────────────────────────────────────────
async function deleteTeam(teamId, name) {
    showConfirmModal({
        title: 'Delete Team',
        icon: '⚠️',
        message: `Delete team <strong>${esc(name)}</strong>? All members will lose access. This cannot be undone.`,
        confirmText: 'Delete Team',
        confirmClass: 'btn-danger',
        onConfirm: async () => {
            try {
                await api(`/teams/${teamId}`, { method: 'DELETE' });
                toast(`Team "${name}" deleted`, 'success');
                await loadTeamsPage();
            } catch (e) { toast(e.message, 'error'); }
        },
    });
}

async function leaveTeam(teamId, name) {
    showConfirmModal({
        title: 'Leave Team',
        icon: '🚪',
        message: `Leave team <strong>${esc(name)}</strong>? You will no longer see their documents.`,
        confirmText: 'Leave Team',
        confirmClass: 'btn-warning',
        onConfirm: async () => {
            try {
                await api(`/teams/${teamId}/leave`, { method: 'POST' });
                toast(`Left team "${name}"`, 'success');
                await loadTeamsPage();
            } catch (e) { toast(e.message, 'error'); }
        },
    });
}

async function refreshTeamCard(teamId) {
    try {
        const teams = await api('/teams');
        const team = teams.find(t => t.id === teamId);
        const card = document.getElementById(`team-card-${teamId}`);
        if (team && card) card.outerHTML = renderTeamCard(team);
    } catch {}
}

// ===== Login Page Init =====
function initLoginPage() {
    if (Auth.ok()) { location.href = '/'; return; }
    const form = document.getElementById('auth-form');
    const alert = document.getElementById('auth-alert');
    const tabs = document.querySelectorAll('.login-tabs button');
    const nameGroup = document.getElementById('name-group');
    const submitBtn = document.getElementById('auth-submit');
    let mode = 'login';

    tabs.forEach(tab => tab.addEventListener('click', () => {
        mode = tab.dataset.mode;
        tabs.forEach(t => t.classList.toggle('active', t === tab));
        nameGroup.style.display = mode === 'register' ? 'block' : 'none';
        submitBtn.textContent = mode === 'register' ? 'Create Account' : 'Sign In';
        alert.style.display = 'none';
    }));

    form.addEventListener('submit', async e => {
        e.preventDefault(); alert.style.display = 'none';
        submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner spinner-sm"></span> Please wait...';
        try {
            if (mode === 'register') {
                await api('/auth/register', { method: 'POST', body: JSON.stringify({ email: document.getElementById('auth-email').value, password: document.getElementById('auth-password').value, full_name: document.getElementById('auth-name').value }) });
            }
            const tokens = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email: document.getElementById('auth-email').value, password: document.getElementById('auth-password').value }) });
            Auth.save(tokens);
            const user = await api('/auth/me');
            localStorage.setItem('dn_user', JSON.stringify(user));
            location.href = '/';
        } catch (err) { alert.textContent = err.message; alert.style.display = 'block'; }
        finally { submitBtn.disabled = false; submitBtn.textContent = mode === 'register' ? 'Create Account' : 'Sign In'; }
    });
}
