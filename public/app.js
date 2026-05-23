// Museum Signage CMS - Frontend Controller

let devices = [];
let activeDeviceId = '';
let activeLibraryScreen = 1;
let statusInterval = null;
let screenshotInterval = null;
let overviewInterval = null;
let autoPreview = false; // Preview auto-polling flag (disabled by default)
let audioConfig = {};

// Cache DOM Elements
const deviceSwitcher = document.getElementById('device-switcher');
const globalStatusDot = document.getElementById('global-status-dot');
const globalStatusText = document.getElementById('global-status-text');
const activeDeviceName = document.getElementById('active-device-name');
const activeDeviceIp = document.getElementById('active-device-ip');
const toastEl = document.getElementById('toast');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    setupTabNavigation();
    setupUploadZone();
    setupSettingsForm();
    
    document.getElementById('btn-refresh').addEventListener('click', () => {
        showToast("Menyegarkan data...");
        refreshAllData();
    });

    // Setup Auto-Preview Toggle
    const previewToggle = document.getElementById('preview-toggle');
    if (previewToggle) {
        previewToggle.addEventListener('change', (e) => {
            autoPreview = e.target.checked;
            if (autoPreview) {
                showToast("Auto preview diaktifkan (5s)");
                refreshScreenshots();
                if (screenshotInterval) clearInterval(screenshotInterval);
                screenshotInterval = setInterval(refreshScreenshots, 5000);
            } else {
                showToast("Auto preview dimatikan");
                if (screenshotInterval) {
                    clearInterval(screenshotInterval);
                    screenshotInterval = null;
                }
            }
        });
    }

    // Initial load
    loadDevices().then(() => {
        if (devices.length > 0) {
            // Default to local IP if available, or first device
            const defaultDev = devices.find(d => d.id === 'pi-1-local') || devices[0];
            selectDevice(defaultDev.id);
        }
        startPollers();
    });
});

// Tab Switcher Logic
function setupTabNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const panels = document.querySelectorAll('.tab-panel');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            navButtons.forEach(b => b.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(`tab-${targetTab}`).classList.add('active');

            // Trigger immediate refresh when entering overview or settings
            if (targetTab === 'overview') {
                updateOverviewGrid();
            } else if (targetTab === 'control') {
                refreshScreenshots();
                if (autoPreview) {
                    if (screenshotInterval) clearInterval(screenshotInterval);
                    screenshotInterval = setInterval(refreshScreenshots, 5000);
                }
            } else {
                // Stop screenshot polling if leaving control tab
                if (screenshotInterval) {
                    clearInterval(screenshotInterval);
                    screenshotInterval = null;
                }
            }
        });
    });
}

// Fetch list of devices
async function loadDevices() {
    try {
        // Try fetching devices.json from server
        const res = await fetch('devices.json');
        if (res.ok) {
            const serverDevices = await res.json();
            devices = serverDevices;
        }
    } catch (e) {
        console.warn("Gagal memuat devices.json dari server, memakai fallback local storage", e);
    }

    // Merge with localStorage overrides
    const localOverride = localStorage.getItem('museum_signage_devices');
    if (localOverride) {
        try {
            const parsed = JSON.parse(localOverride);
            // Merge: keep local overrides, add new ones
            parsed.forEach(ld => {
                const idx = devices.findIndex(d => d.id === ld.id);
                if (idx !== -1) {
                    devices[idx] = ld;
                } else {
                    devices.push(ld);
                }
            });
        } catch (err) {
            console.error("Gagal parsing local storage devices", err);
        }
    } else {
        localStorage.setItem('museum_signage_devices', JSON.stringify(devices));
    }

    renderDeviceSwitcher();
    renderDeviceTable();
}

function renderDeviceSwitcher() {
    deviceSwitcher.innerHTML = '';
    devices.forEach(dev => {
        const opt = document.createElement('option');
        opt.value = dev.id;
        opt.textContent = `${dev.name} (${dev.ip})`;
        deviceSwitcher.appendChild(opt);
    });

    deviceSwitcher.addEventListener('change', (e) => {
        selectDevice(e.target.value);
    });
}

// Select active device to control
function selectDevice(id) {
    activeDeviceId = id;
    deviceSwitcher.value = id;
    const device = getActiveDevice();
    
    if (device) {
        activeDeviceName.textContent = device.name;
        activeDeviceIp.textContent = `${device.ip}:${device.port}`;
        
        globalStatusDot.className = "dot offline";
        globalStatusText.textContent = "Connecting...";
        
        // Immediate fetch
        refreshAllData();
    }
}

function getActiveDevice() {
    return devices.find(d => d.id === activeDeviceId);
}

// Resolve API URL based on active device
function getApiUrl(endpoint) {
    const dev = getActiveDevice();
    if (!dev) return endpoint;

    const hostname = window.location.hostname;
    // If we are controlling the current host locally, use relative path to prevent CORS issues
    if (dev.ip === hostname || dev.ip === '127.0.0.1' || dev.ip === 'localhost') {
        return endpoint;
    }
    return `http://${dev.ip}:${dev.port}${endpoint}`;
}

// Toast Notifications
function showToast(message, isError = false) {
    toastEl.textContent = message;
    toastEl.className = `toast ${isError ? 'btn-danger' : ''}`;
    toastEl.classList.remove('hidden');
    
    setTimeout(() => {
        toastEl.classList.add('hidden');
    }, 3000);
}

// Polling setup
function startPollers() {
    // Poll active device status (services, playing state, metrics)
    if (statusInterval) clearInterval(statusInterval);
    statusInterval = setInterval(fetchActiveDeviceStatus, 2500);

    // Poll overview grid status for all devices
    if (overviewInterval) clearInterval(overviewInterval);
    overviewInterval = setInterval(updateOverviewGrid, 6000);
}

function refreshAllData() {
    fetchActiveDeviceStatus();
    refreshScreenshots(); // Fetch screenshots once on manual/device refresh
    updateOverviewGrid();
}

// Fetch active device details
async function fetchActiveDeviceStatus() {
    const dev = getActiveDevice();
    if (!dev) return;

    try {
        const url = getApiUrl('/api/status');
        const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
        if (!res.ok) throw new Error("Server error");
        
        const data = await res.json();
        
        // Update status header
        globalStatusDot.className = "dot online";
        globalStatusText.textContent = `Online - ${data.system.uptime}`;
        
        // Update screen components
        audioConfig = data.audio || {};
        updateScreenControlUI(1, data.screen1, audioConfig.screen1);
        updateScreenControlUI(2, data.screen2, audioConfig.screen2);
        
        // Update diagnostics tab
        updateDiagnosticsUI(data.system);
        
        // If library tab is visible, update playlist
        updateLibraryPlaylistUI(activeLibraryScreen === 1 ? data.screen1.playlist : data.screen2.playlist);

    } catch (e) {
        console.error("Gagal kontak ke device active status:", e);
        globalStatusDot.className = "dot offline";
        globalStatusText.textContent = "Offline (Connection Lost)";
        
        // Mark screens as offline
        document.getElementById('s1-status-badge').className = "badge badge-error";
        document.getElementById('s1-status-badge').textContent = "Offline";
        document.getElementById('s2-status-badge').className = "badge badge-error";
        document.getElementById('s2-status-badge').textContent = "Offline";
    }
}

// Update playback details for Screen card
function updateScreenControlUI(screenNum, data, audioData) {
    const statusBadge = document.getElementById(`s${screenNum}-status-badge`);
    const titleEl = document.getElementById(`s${screenNum}-playing-title`);
    const progressFill = document.getElementById(`s${screenNum}-progress`);
    const timeCurrEl = document.getElementById(`s${screenNum}-time-curr`);
    const timeDurEl = document.getElementById(`s${screenNum}-time-dur`);
    const playBtn = document.getElementById(`s${screenNum}-btn-play`);
    const muteBtn = document.getElementById(`s${screenNum}-btn-mute`);
    const routeSelect = document.getElementById(`s${screenNum}-select-audio-route`);

    if (audioData) {
        const isMuted = audioData.global_mute;
        muteBtn.textContent = isMuted ? "🔇 Muted" : "🔊 Audio ON";
        muteBtn.className = isMuted ? "btn btn-sm btn-secondary" : "btn btn-sm btn-primary";
        if (document.activeElement !== routeSelect) {
            routeSelect.value = audioData.output_device || "hdmi";
        }
    }


    // Service active status
    if (data.service_active) {
        statusBadge.className = "badge badge-success";
        statusBadge.textContent = data.mpv_connected ? "Playing" : "Active (No MPV)";
    } else {
        statusBadge.className = "badge badge-error";
        statusBadge.textContent = "Service Inactive";
    }

    // Play/Pause button symbol
    playBtn.textContent = data.paused ? "▶️" : "⏸️";
    playBtn.dataset.paused = data.paused;

    // Playing title
    titleEl.textContent = data.playing_file !== "None" ? data.playing_file : "Daftar putar kosong / Berhenti";

    // Progress Bar & Time
    if (data.duration > 0) {
        const pct = (data.time_pos / data.duration) * 100;
        progressFill.style.width = `${pct}%`;
        timeCurrEl.textContent = formatTime(data.time_pos);
        timeDurEl.textContent = formatTime(data.duration);
    } else {
        progressFill.style.width = '0%';
        timeCurrEl.textContent = "00:00";
        timeDurEl.textContent = "00:00";
    }
}

// Update diagnostics values
function updateDiagnosticsUI(sys) {
    document.getElementById('diag-temp').textContent = `${sys.cpu_temp}°C`;
    const tempBar = document.getElementById('diag-temp-bar');
    tempBar.style.width = `${Math.min(sys.cpu_temp, 100)}%`;
    // color code temperature
    tempBar.style.backgroundColor = sys.cpu_temp > 65 ? 'var(--danger)' : sys.cpu_temp > 50 ? 'var(--warning)' : 'var(--success)';

    document.getElementById('diag-cpu').textContent = `${sys.cpu_percent}%`;
    document.getElementById('diag-cpu-bar').style.width = `${sys.cpu_percent}%`;

    document.getElementById('diag-ram').textContent = `${sys.ram.used_mb} / ${sys.ram.total_mb} MB (${sys.ram.percent}%)`;
    document.getElementById('diag-ram-bar').style.width = `${sys.ram.percent}%`;

    document.getElementById('diag-disk').textContent = `${sys.disk.used_gb} / ${sys.disk.total_gb} GB (${sys.disk.percent}%)`;
    document.getElementById('diag-disk-bar').style.width = `${sys.disk.percent}%`;

    document.getElementById('diag-uptime').textContent = sys.uptime;
}

// Refresh Screen Screenshots Once
function refreshScreenshots() {
    const activeTab = document.querySelector('.nav-btn.active').getAttribute('data-tab');
    if (activeTab !== 'control') return; 

    const dev = getActiveDevice();
    if (!dev || globalStatusDot.classList.contains('offline')) return;

    const s1Img = document.getElementById('s1-preview');
    const s2Img = document.getElementById('s2-preview');
    
    const cacheBuster = `t=${Date.now()}`;
    s1Img.src = getApiUrl(`/api/screenshot?screen=1&${cacheBuster}`);
    s2Img.src = getApiUrl(`/api/screenshot?screen=2&${cacheBuster}`);
}

// Manual Refresh for a single screen preview
function refreshSingleScreenshot(screen) {
    const dev = getActiveDevice();
    if (!dev || globalStatusDot.classList.contains('offline')) {
        showToast("Perangkat offline, tidak bisa mengambil preview", true);
        return;
    }

    const sImg = document.getElementById(`s${screen}-preview`);
    const cacheBuster = `t=${Date.now()}`;
    
    // Set a loading indicator or class if desired
    sImg.style.opacity = '0.7';
    sImg.src = getApiUrl(`/api/screenshot?screen=${screen}&${cacheBuster}`);
    
    sImg.onload = () => {
        sImg.style.opacity = '1';
    };
    
    showToast(`Mengambil tangkapan layar baru untuk Layar ${screen}...`);
}

// Send Remote control actions
async function controlDevice(screen, action) {
    try {
        const url = getApiUrl('/api/control');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ screen, action })
        });
        
        const data = await res.json();
        if (data.success) {
            showToast(`${action.replace('_', ' ')} berhasil dikirim`);
            fetchActiveDeviceStatus();
        } else {
            showToast(`Gagal: ${data.error}`, true);
        }
    } catch (e) {
        showToast("Error mengirim perintah kontrol", true);
    }
}

function togglePlay(screen) {
    const playBtn = document.getElementById(`s${screen}-btn-play`);
    const isPaused = playBtn.dataset.paused === 'true';
    controlDevice(screen, isPaused ? 'play' : 'pause');
}

// --- Overview Grid Handler ---
async function updateOverviewGrid() {
    const activeTab = document.querySelector('.nav-btn.active').getAttribute('data-tab');
    if (activeTab !== 'overview') return;

    const grid = document.getElementById('devices-grid');
    if (!grid) return;
    
    // Query each device in parallel
    const promises = devices.map(async (device) => {
        const url = `http://${device.ip}:${device.port}/api/status`;
        try {
            const res = await fetch(url, { signal: AbortSignal.timeout(1800) });
            if (!res.ok) throw new Error();
            const data = await res.json();
            return { device, online: true, data };
        } catch (e) {
            return { device, online: false };
        }
    });

    const results = await Promise.all(promises);
    grid.innerHTML = '';

    results.forEach(res => {
        const card = document.createElement('div');
        card.className = 'grid-card';
        card.onclick = () => selectDevice(res.device.id);

        const statusClass = res.online ? 'online' : 'offline';
        const statusText = res.online ? 'Online' : 'Offline';
        
        let screen1Name = '-';
        let screen2Name = '-';
        let cpuText = '-';
        let tempText = '-';

        if (res.online && res.data) {
            screen1Name = res.data.screen1.playing_file !== 'None' ? res.data.screen1.playing_file : 'Berhenti';
            screen2Name = res.data.screen2.playing_file !== 'None' ? res.data.screen2.playing_file : 'Berhenti';
            cpuText = `${res.data.system.cpu_percent}% CPU`;
            tempText = `${res.data.system.cpu_temp}°C`;
        }

        card.innerHTML = `
            <div class="grid-card-header">
                <h3>${res.device.name}</h3>
                <span class="badge badge-${res.online ? 'success' : 'error'}">${statusText}</span>
            </div>
            <div class="grid-card-status">
                <div class="screen-row ${res.online && res.data.screen1.service_active ? 'active' : ''}">
                    <span>Layar 1:</span>
                    <span>${screen1Name}</span>
                </div>
                <div class="screen-row ${res.online && res.data.screen2.service_active ? 'active' : ''}">
                    <span>Layar 2:</span>
                    <span>${screen2Name}</span>
                </div>
            </div>
            <div class="grid-card-footer">
                <span>${res.device.ip}</span>
                <span>${res.online ? `${cpuText} | ${tempText}` : 'Tidak Terjangkau'}</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

// --- Media Library & Playlist Manager ---
function switchLibraryScreen(screen) {
    activeLibraryScreen = screen;
    document.getElementById('btn-sub-s1').className = `btn btn-secondary ${screen === 1 ? 'active' : ''}`;
    document.getElementById('btn-sub-s2').className = `btn btn-secondary ${screen === 2 ? 'active' : ''}`;
    
    // Refresh status to draw current screen's playlist
    fetchActiveDeviceStatus();
}

function updateLibraryPlaylistUI(playlist) {
    const listEl = document.getElementById('playlist-list-items');
    listEl.innerHTML = '';

    if (!playlist || playlist.length === 0) {
        listEl.innerHTML = '<li class="playlist-item text-muted">Folder media kosong. Silakan unggah file video.</li>';
        return;
    }

    const screenKey = `screen${activeLibraryScreen}`;
    const clipSettings = (audioConfig[screenKey] && audioConfig[screenKey].clip_settings) || {};

    playlist.forEach((item, index) => {
        const li = document.createElement('li');
        li.className = 'playlist-item';
        li.dataset.filename = item.name;
        
        const isClipMuted = clipSettings[item.name] ? clipSettings[item.name].mute : false;
        const muteBadgeClass = isClipMuted ? 'badge badge-error' : 'badge badge-success';
        const muteBadgeText = isClipMuted ? '🔇 Muted' : '🔊 Sound';

        li.innerHTML = `
            <div class="item-info">
                <div class="item-header-row" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <span class="item-name" style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600;">${item.name}</span>
                    <span class="${muteBadgeClass}" onclick="toggleClipMute('${item.name}')" style="cursor: pointer; font-size: 10px; padding: 2px 6px;" title="Klik untuk ubah status suara">${muteBadgeText}</span>
                </div>
                <span class="item-size" style="font-size: 11px; color: var(--text-muted);">${item.size_mb} MB</span>
            </div>
            <div class="item-actions">
                <button class="btn btn-sm btn-secondary" onclick="movePlaylistItem(${index}, -1)" ${index === 0 ? 'disabled' : ''}>🔼</button>
                <button class="btn btn-sm btn-secondary" onclick="movePlaylistItem(${index}, 1)" ${index === playlist.length - 1 ? 'disabled' : ''}>🔽</button>
                <button class="btn btn-sm btn-danger" onclick="deleteVideoFile('${item.name}')">🗑️</button>
            </div>
        `;
        listEl.appendChild(li);
    });
}

// Move item up/down in the UI list
function movePlaylistItem(index, direction) {
    const listEl = document.getElementById('playlist-list-items');
    const items = Array.from(listEl.children);
    
    if (direction === -1 && index > 0) {
        listEl.insertBefore(items[index], items[index - 1]);
    } else if (direction === 1 && index < items.length - 1) {
        listEl.insertBefore(items[index + 1], items[index]);
    }
    
    // Re-enable/disable buttons accordingly
    setTimeout(refreshOrderButtons, 50);
}

function refreshOrderButtons() {
    const listEl = document.getElementById('playlist-list-items');
    const items = Array.from(listEl.children);
    items.forEach((item, index) => {
        const upBtn = item.querySelector('.item-actions button:nth-child(1)');
        const downBtn = item.querySelector('.item-actions button:nth-child(2)');
        if (upBtn) upBtn.disabled = (index === 0);
        if (downBtn) downBtn.disabled = (index === items.length - 1);
    });
}

// Post ordered list to server
async function savePlaylistOrder() {
    const listEl = document.getElementById('playlist-list-items');
    const items = Array.from(listEl.children);
    const filenames = items.map(li => li.dataset.filename).filter(Boolean);

    if (filenames.length === 0) return;

    try {
        const url = getApiUrl('/api/playlist/save');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: activeLibraryScreen,
                playlist: filenames
            })
        });

        const data = await res.json();
        if (data.success) {
            showToast("Urutan playlist berhasil disimpan!");
            fetchActiveDeviceStatus();
        } else {
            showToast(`Gagal menyimpan: ${data.error}`, true);
        }
    } catch (e) {
        showToast("Error menghubungi server untuk playlist", true);
    }
}

// File Upload Handler
function setupUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const targetScreenSelect = document.getElementById('upload-target-screen');
    const progressWrapper = document.getElementById('upload-progress-wrapper');
    const progressBar = document.getElementById('upload-progress');
    const uploadFilename = document.getElementById('upload-filename');
    const uploadPercent = document.getElementById('upload-percent');

    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    function handleFileUpload(file) {
        const targetScreen = targetScreenSelect.value;
        const url = getApiUrl(`/api/upload?screen=${targetScreen}`);
        
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', file);

        // Progress Handler
        progressWrapper.classList.remove('hidden');
        uploadFilename.textContent = file.name;
        progressBar.style.width = '0%';
        uploadPercent.textContent = '0%';

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = `${pct}%`;
                uploadPercent.textContent = `${pct}%`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                showToast("File berhasil diunggah!");
                setTimeout(() => progressWrapper.classList.add('hidden'), 1000);
                fetchActiveDeviceStatus();
            } else {
                showToast("Gagal mengunggah file!", true);
                setTimeout(() => progressWrapper.classList.add('hidden'), 2000);
            }
        });

        xhr.addEventListener('error', () => {
            showToast("Koneksi gagal saat mengunggah file", true);
            progressWrapper.classList.add('hidden');
        });

        xhr.open('POST', url, true);
        // Do not set Content-Type header; XMLHttpRequest does it automatically with boundary for FormData
        xhr.send(formData);
    }
}

// Delete media asset
async function deleteVideoFile(filename) {
    if (!confirm(`Apakah Anda yakin ingin menghapus "${filename}" dari Layar ${activeLibraryScreen}?`)) {
        return;
    }

    try {
        const url = getApiUrl('/api/delete');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: activeLibraryScreen,
                filename: filename
            })
        });

        const data = await res.json();
        if (data.success) {
            showToast("Video berhasil dihapus");
            fetchActiveDeviceStatus();
        } else {
            showToast(`Gagal: ${data.error}`, true);
        }
    } catch (e) {
        showToast("Error saat menghapus video", true);
    }
}


// --- Settings: Device Management ---
function setupSettingsForm() {
    const form = document.getElementById('form-add-device');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const name = document.getElementById('new-device-name').value;
        const ip = document.getElementById('new-device-ip').value;
        const port = parseInt(document.getElementById('new-device-port').value);
        
        // Generate random ID
        const id = `pi-custom-${Date.now()}`;
        const newDevice = { id, name, ip, port };

        devices.push(newDevice);
        localStorage.setItem('museum_signage_devices', JSON.stringify(devices));
        
        form.reset();
        showToast(`Perangkat "${name}" ditambahkan`);
        
        loadDevices(); // Refresh list and dropdown
    });
}

function renderDeviceTable() {
    const tbody = document.getElementById('device-table-body');
    tbody.innerHTML = '';

    devices.forEach(dev => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${dev.name}</strong></td>
            <td><code>${dev.ip}</code></td>
            <td>${dev.port}</td>
            <td>
                <button class="btn btn-sm btn-danger" onclick="deleteRegisteredDevice('${dev.id}')">Hapus</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function deleteRegisteredDevice(id) {
    const device = devices.find(d => d.id === id);
    if (!device) return;

    if (!confirm(`Hapus perangkat "${device.name}" dari daftar kontrol?`)) {
        return;
    }

    devices = devices.filter(d => d.id !== id);
    localStorage.setItem('museum_signage_devices', JSON.stringify(devices));
    showToast("Perangkat dihapus");
    
    // If active device was deleted, switch to first remaining
    if (activeDeviceId === id && devices.length > 0) {
        selectDevice(devices[0].id);
    }
    
    loadDevices();
}


// --- Helper Functions ---
function formatTime(seconds) {
    if (isNaN(seconds) || seconds === null) return "00:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// --- Audio Control Helper APIs ---
async function toggleGlobalMute(screen) {
    const screenKey = `screen${screen}`;
    const currentMute = audioConfig[screenKey] ? audioConfig[screenKey].global_mute : true;
    const outputDevice = audioConfig[screenKey] ? audioConfig[screenKey].output_device : 'hdmi';
    
    try {
        const url = getApiUrl('/api/audio/global');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                global_mute: !currentMute,
                output_device: outputDevice
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Audio Layar ${screen} ${!currentMute ? 'Dimatikan' : 'Dihidupkan'}`);
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast("Gagal mengubah status audio", true);
    }
}

async function changeAudioRoute(screen) {
    const screenKey = `screen${screen}`;
    const currentMute = audioConfig[screenKey] ? audioConfig[screenKey].global_mute : true;
    const routeSelect = document.getElementById(`s${screen}-select-audio-route`);
    const newRoute = routeSelect.value;
    
    try {
        const url = getApiUrl('/api/audio/global');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                global_mute: currentMute,
                output_device: newRoute
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Output Audio Layar ${screen} dialihkan ke ${newRoute.toUpperCase()}`);
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast("Gagal mengubah rute audio", true);
    }
}

async function toggleClipMute(filename) {
    const screenKey = `screen${activeLibraryScreen}`;
    const clipSettings = (audioConfig[screenKey] && audioConfig[screenKey].clip_settings) || {};
    const currentMute = clipSettings[filename] ? clipSettings[filename].mute : false;
    
    try {
        const url = getApiUrl('/api/audio/clip');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: activeLibraryScreen,
                filename: filename,
                mute: !currentMute
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Audio klip "${filename}" ${!currentMute ? 'Dimatikan' : 'Dihidupkan'}`);
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast("Gagal mengubah status audio klip", true);
    }
}
