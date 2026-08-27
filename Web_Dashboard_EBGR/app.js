/* ==========================================================================
   E-BGR MONITORING DASHBOARD - app.js
   ========================================================================== */

const API_BASE      = window.location.origin;
const MQTT_WS       = 'wss://broker.emqx.io:8084/mqtt';
const TOPIC_CHECKIN = 'ebgr/tamu/checkin';
const TOPIC_CHECKOUT = 'ebgr/tamu/checkout';

let mqttClient  = null;
let currentRole = 'user';   // 'admin' | 'user'
let currentUser = '';

// ==================== INIT ====================

async function init() {
    // 1. Cek sesi — jika tidak login, kembalikan ke halaman login
    let authData;
    try {
        const res = await fetch('/api/auth-check', { cache: 'no-store' });
        if (!res.ok) {
            window.location.replace('/');
            return;
        }
        authData = await res.json();
        if (authData.status !== 'ok') {
            window.location.replace('/');
            return;
        }
    } catch (_) {
        // Server offline — tetap tampilkan, skip auth
        authData = { username: 'offline', role: 'user', is_admin: false };
    }

    currentRole = authData.role || 'user';
    currentUser = authData.username || '';
    const isAdmin = (currentRole === 'admin');

    // 2. Tampilkan info user di header
    const elUserName   = document.getElementById('user-name');
    const elUserBadge  = document.getElementById('user-badge');
    const elUserAvatar = document.getElementById('user-avatar');
    if (elUserName)   elUserName.textContent   = currentUser;
    if (elUserBadge)  {
        elUserBadge.textContent  = isAdmin ? 'Admin' : 'User';
        elUserBadge.className    = 'role-badge ' + (isAdmin ? 'badge-admin' : 'badge-user');
    }
    if (elUserAvatar) elUserAvatar.textContent = currentUser.charAt(0).toUpperCase();

    // 3. Tampilkan/sembunyikan elemen berdasarkan role
    document.querySelectorAll('[data-role="admin"]').forEach(el => {
        el.style.display = isAdmin ? '' : 'none';
    });
    document.querySelectorAll('[data-role="user-only"]').forEach(el => {
        el.style.display = isAdmin ? 'none' : '';
    });

    // 4. Untuk user biasa — hanya tampilkan halaman check-in
    if (!isAdmin) {
        showPage('checkin-user');
    } else {
        showPage('dashboard');
        fetchDatabaseLogs();
    }

    // 5. Mulai clock & MQTT
    startClock();
    initMqtt();
}

// ==================== LOGOUT ====================

async function doLogout() {
    try {
        await fetch('/api/logout', { method: 'POST', cache: 'no-store' });
    } catch (_) {}
    window.location.replace('/');
}

// ==================== SPA NAVIGATION ====================

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(p => {
        p.classList.add('hidden');
        p.classList.remove('active');
    });
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const page = document.getElementById('page-' + pageName);
    if (page) { page.classList.remove('hidden'); page.classList.add('active'); }

    const nav = document.getElementById('nav-' + pageName);
    if (nav) nav.classList.add('active');

    if (pageName === 'logs') fetchDatabaseLogs();
}

// ==================== CLOCK ====================

function startClock() {
    const update = () => {
        const t = new Date().toLocaleTimeString('id-ID') + ' WIB';
        document.querySelectorAll('.live-clock').forEach(el => el.textContent = t);
    };
    update();
    setInterval(update, 1000);
}

// ==================== MQTT ====================

function initMqtt() {
    const id = 'ebgr_web_' + Math.random().toString(16).slice(2, 8);
    mqttClient = mqtt.connect(MQTT_WS, { clientId: id, clean: true, connectTimeout: 4000 });

    mqttClient.on('connect', () => {
        setMqttStatus(true);
        mqttClient.subscribe([TOPIC_CHECKIN, TOPIC_CHECKOUT]);
        showToast('📡 MQTT Terhubung!');
    });
    mqttClient.on('message', (topic, msg) => {
        try { handleMqtt(topic, JSON.parse(msg.toString())); } catch (_) {}
    });
    mqttClient.on('offline', () => setMqttStatus(false));
    mqttClient.on('error',   () => setMqttStatus(false));
}

function setMqttStatus(ok) {
    const light = document.getElementById('mqtt-status-light');
    const text  = document.getElementById('mqtt-status-text');
    if (light) { ok ? light.classList.add('online') : light.classList.remove('online'); }
    if (text)  text.textContent = ok ? 'Terhubung (MQTT Cloud)' : 'Terputus (Retrying...)';
}

let activeGuests = new Set();
let totalIn  = 0;
let totalOut = 0;

function handleMqtt(topic, p) {
    const isIn = (topic === TOPIC_CHECKIN || p.event === 'check-in');
    const ts   = p.timestamp === 'CURRENT_TIMESTAMP' ? new Date().toLocaleTimeString('id-ID') : p.timestamp;

    if (isIn) { activeGuests.add(p.id_tamu); totalIn++;  }
    else       { activeGuests.delete(p.id_tamu); totalOut++; }

    safeSet('count-checkedin',  activeGuests.size);
    safeSet('count-total-in',   totalIn);
    safeSet('count-total-out',  totalOut);

    const ef = document.getElementById('empty-feed-msg');
    if (ef) ef.style.display = 'none';
    addFeedItem(p.nama, isIn ? 'Check-In' : 'Check-Out', ts, isIn);
    showToast(`${isIn ? '🟢' : '🟣'} ${p.nama} — ${isIn ? 'Check-In' : 'Check-Out'}`);
}

function addFeedItem(name, type, time, isIn) {
    const list = document.getElementById('feed-list');
    if (!list) return;
    const item = document.createElement('div');
    item.className = 'feed-item';
    item.innerHTML = `
        <div class="feed-avatar">${(name || 'T').charAt(0).toUpperCase()}</div>
        <div class="feed-content">
            <div class="feed-title">${name || 'Tamu'}</div>
            <div class="feed-time">${time} WIB</div>
        </div>
        <span class="badge ${isIn ? 'badge-in' : 'badge-out'}">${type}</span>`;
    list.prepend(item);
}

// ==================== TOAST ====================

function showToast(msg) {
    const c = document.getElementById('toast-container');
    if (!c) return;
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `<span>⚡</span> <span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

// ==================== LOGS (Admin) ====================

async function fetchDatabaseLogs() {
    const tableBody = document.getElementById('table-body');
    if (tableBody) tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:#64748b;">⏳ Memuat data...</td></tr>`;

    try {
        const res  = await fetch('/api/logs', { cache: 'no-store' });
        if (res.status === 403 || res.status === 401) {
            if (tableBody) tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:#ef4444;">🔒 Akses ditolak. Hanya Admin.</td></tr>`;
            return;
        }
        const data = await res.json();
        if (data.status !== 'success') throw new Error(data.message);

        let inCount = 0, outCount = 0;
        if (tableBody) tableBody.innerHTML = '';

        data.logs.forEach((log, i) => {
            const isIn = log.event === 'check-in' || log.event === 'Check-In';
            if (isIn) inCount++; else outCount++;

            if (!tableBody) return;
            const tr     = document.createElement('tr');
            const badge  = isIn ? 'badge-in' : 'badge-out';
            const label  = isIn ? 'Check-In' : 'Check-Out';
            const sColor = log.status_verifikasi === 'success' ? 'var(--success)' : 'var(--danger)';
            const previewBtn = log.has_photos
                ? `<button class="btn-preview" onclick="openFacePreview('${log.id_tamu}','${log.nama.replace(/'/g,"\\'")}')">🖼️ Lihat Wajah</button>`
                : `<button class="btn-preview" disabled title="Belum ada foto">📷 Belum Ada</button>`;

            tr.innerHTML = `
                <td style="color:var(--text-dim)">${i + 1}</td>
                <td><strong>${log.id_tamu || '-'}</strong></td>
                <td>${log.nama || 'Tamu'}</td>
                <td><span class="badge ${badge}">${label}</span></td>
                <td>${log.timestamp || '-'}</td>
                <td>Dlib ResNet-29</td>
                <td><span style="color:${sColor};font-weight:600">✓ ${log.status_verifikasi || 'success'}</span></td>
                <td>${previewBtn}</td>`;
            tableBody.appendChild(tr);
        });

        safeSet('log-count-in',    inCount);
        safeSet('log-count-out',   outCount);
        safeSet('log-count-total', data.logs.length);

        if (data.stats) safeSet('count-checkedin', data.stats['checked-in'] || 0);
        safeSet('count-total-in',  inCount);
        safeSet('count-total-out', outCount);

    } catch (err) {
        if (tableBody) tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:30px;color:#64748b;">⚠️ Gagal memuat data. Pastikan server.py berjalan.</td></tr>`;
    }
}

// ==================== FACE PREVIEW ====================

async function openFacePreview(id_tamu, nama) {
    const modal = document.getElementById('face-modal');
    const body  = document.getElementById('modal-body');
    const title = document.getElementById('modal-title');
    if (!modal) return;

    title.textContent = `👤 Preview Wajah: ${nama} (${id_tamu})`;
    body.innerHTML    = '<div class="modal-loading">⏳ Memuat foto...</div>';
    modal.classList.remove('hidden');

    try {
        const res  = await fetch(`/api/tamu-photos/${id_tamu}`, { cache: 'no-store' });
        const data = await res.json();
        if (data.status === 'success' && data.photos?.length) {
            body.innerHTML = `<div class="modal-photos">${
                data.photos.map((p, i) => `
                    <div class="photo-item">
                        <img src="${p.data}" alt="Foto ${i+1}">
                        <span class="photo-label">📸 Foto ${i + 1}</span>
                    </div>`).join('')
            }</div>`;
        } else {
            body.innerHTML = '<div class="modal-loading">📂 Tidak ada foto tersimpan.</div>';
        }
    } catch (_) {
        body.innerHTML = '<div class="modal-loading">⚠️ Gagal memuat foto.</div>';
    }
}

function closeModal() {
    const m = document.getElementById('face-modal');
    if (m) m.classList.add('hidden');
}

document.addEventListener('click', e => {
    const m = document.getElementById('face-modal');
    if (m && e.target === m) closeModal();
});

// ==================== CAMERA CONTROL ====================

async function callApi(endpoint, btn) {
    if (btn) btn.disabled = true;
    try {
        const res  = await fetch(API_BASE + endpoint, { method: 'POST' });
        const data = await res.json();
        showToast(data.status === 'success' ? `✅ ${data.message}` :
                  data.status === 'warning' ? `⚠️ ${data.message}` : `❌ ${data.message}`);
    } catch (_) {
        showToast('❌ Gagal terhubung ke server lokal!');
    } finally {
        if (btn) setTimeout(() => btn.disabled = false, 2500);
    }
}

// ==================== SEARCH ====================

const elSearch = document.getElementById('input-search');
if (elSearch) {
    elSearch.addEventListener('input', () => {
        const q = elSearch.value.toLowerCase();
        document.querySelectorAll('#table-body tr').forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
    });
}

// ==================== SIMULASI ====================

const btnSim = document.getElementById('btn-simulasi');
if (btnSim) {
    btnSim.addEventListener('click', () => {
        const names = ['Alfisyahrin', 'Budi Santoso', 'Siti Rahma', 'Rizal', 'Anisa Putri'];
        const p = {
            id_tamu:   'T0' + Math.floor(Math.random() * 90 + 10),
            nama:      names[Math.floor(Math.random() * names.length)],
            event:     Math.random() > 0.4 ? 'check-in' : 'check-out',
            timestamp: new Date().toLocaleTimeString('id-ID')
        };
        handleMqtt(p.event === 'check-in' ? TOPIC_CHECKIN : TOPIC_CHECKOUT, p);
    });
}

// ==================== UTILS ====================

function safeSet(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

// ==================== KICKOFF ====================
init();
