// Museum Signage CMS - Frontend Controller

const i18n = {
    id: {
        brand_name: "caPiBarra",
        brand_sub: "Raspberry Pi Video CMS",
        nav_overview: "📊 Grid Ringkasan",
        nav_control: "📺 Layar Kontrol",
        nav_library: "📁 Pustaka Media",
        nav_settings: "⚙️ Pengaturan Pi",
        nav_about: "ℹ️ Tentang Aplikasi",
        active_device: "Perangkat Aktif:",
        connecting: "Menghubungkan...",
        status_offline_text: "Mencari Perangkat...",
        select_device: "Pilih Perangkat:",
        btn_refresh: "🔄 Segarkan",
        all_screens: "Semua Perangkat Layar",
        all_screens_sub: "Status real-time dari seluruh Raspberry Pi di museum",
        active_control: "Kontrol Layar Aktif",
        active_control_sub: "Kelola pemutaran video secara real-time pada monitor HDMI",
        auto_preview: "Preview Otomatis (5d)",
        screen1_title: "Layar 1 (HDMI-A-1)",
        screen2_title: "Layar 2 (HDMI-A-2)",
        btn_screenshot: "📸 Ambil Preview",
        no_media: "Daftar putar kosong / Berhenti",
        audio_control_header: "Kontrol Audio",
        systemd_service_header: "Layanan Systemd",
        upload_title: "Unggah Video Baru",
        drop_zone: "Tarik & lepas file video di sini, atau klik untuk memilih",
        supported_formats: "Format yang didukung: MP4, MKV, AVI, MOV",
        target_screen_label: "Tujuan Layar:",
        target_screen_1: "Layar 1 (HDMI-1)",
        target_screen_2: "Layar 2 (HDMI-2)",
        playlist_title: "Daftar Putar Video",
        btn_save_order: "💾 Simpan Urutan",
        playlist_sub: "Gunakan tombol 🔼 dan 🔽 untuk mengatur urutan putar video",
        diagnostic_title: "Status Diagnostik",
        cpu_temp_label: "Temperatur CPU",
        cpu_percent_label: "Penggunaan CPU",
        ram_label: "RAM Terpakai",
        disk_label: "Ruang Disk",
        device_model: "Model: Raspberry Pi 4 Model B",
        manage_pi: "Kelola Daftar Perangkat Pi",
        new_device_name_label: "Nama Perangkat:",
        new_device_ip_label: "Alamat IP / Domain:",
        new_device_port_label: "Port:",
        btn_add_device: "➕ Tambah Perangkat",
        registered_devices_title: "Daftar Perangkat Terdaftar",
        th_name: "Nama",
        th_ip: "Alamat IP",
        th_port: "Port",
        th_action: "Aksi",
        about_header: "Tentang Aplikasi",
        about_sub: "Informasi detail mengenai perangkat lunak kontrol pemutar video piEdge",
        about_desc_1: "<strong>piEdge CMS Signage</strong> adalah sistem manajemen konten (CMS) signage multimedia berbasis web yang dikembangkan khusus untuk mengelola pemutaran video secara mandiri maupun terpusat pada Raspberry Pi 4.",
        about_desc_2: "Software ini mengintegrasikan server web multi-thread berdaya rendah dengan antarmuka pemrograman video MPV melalui soket IPC Unix, memungkinkan kontrol pemutaran video berkinerja tinggi langsung to port hardware HDMI (HDMI-A-1 dan HDMI-A-2) secara mulus, efisien, dan tanpa hambatan.",
        
        opt_hdmi: "HDMI Output",
        opt_jack: "3.5mm Jack Output",
        opt_stereo: "Stereo",
        opt_left: "Channel L (Kiri)",
        opt_right: "Channel R (Kanan)",
        
        btn_start: "Start",
        btn_restart: "Restart",
        btn_stop: "Stop",
        
        uptime_label: "Uptime",
        status_online: "Online",
        status_offline: "Offline",
        connection_lost: "Koneksi Terputus",
        status_playing: "Memutar",
        status_active_no_mpv: "Aktif (Tanpa MPV)",
        status_service_inactive: "Layanan Tidak Aktif",
        status_stopped: "Berhenti",
        status_unreachable: "Tidak Terjangkau",
        empty_folder: "Folder media kosong. Silakan unggah file video.",
        badge_muted: "🔇 Senyap",
        badge_sound: "🔊 Bersuara",
        opt_muted: "🔇 Senyap",
        opt_audio_on: "🔊 Audio Hidup",
        
        toast_device_offline_preview: "Perangkat offline, tidak bisa mengambil preview",
        toast_capturing_screenshot: "Mengambil tangkapan layar baru untuk Layar {screen}...",
        toast_command_sent: "Perintah berhasil dikirim",
        toast_refreshing: "Menyegarkan data...",
        toast_autopreview_on: "Auto preview diaktifkan (5d)",
        toast_autopreview_off: "Auto preview dimatikan",

        library_header: "Pustaka Media & Pengelola Playlist",
        library_sub_desc: "Unggah video baru dan tentukan urutan daftar putar pada tiap layar",
        playlist_tab_1: "Layar 1 Playlist",
        playlist_tab_2: "Layar 2 Playlist",
        settings_header: "Sistem & Konfigurasi Perangkat",
        settings_sub: "Kelola alamat IP Raspberry Pi dan lihat diagnosis performa",
        placeholder_device_name: "mis. Layar Lobby",
        placeholder_device_ip: "mis. 192.168.88.47",
        about_director: "Project Director",
        about_designer: "Lead Designer",
        about_uiux: "UI/UX",
        about_dev_team: "Tim Pengembang",

        confirm_delete_video: "Apakah Anda yakin ingin menghapus \"{filename}\" dari Layar {screen}?",
        confirm_delete_device: "Hapus perangkat \"{name}\" dari daftar kontrol?",
        toast_upload_success: "File berhasil diunggah!",
        toast_upload_fail: "Gagal mengunggah file!",
        toast_upload_error: "Koneksi gagal saat mengunggah file",
        toast_upload_too_large: "File terlalu besar (maks 500MB)!",
        toast_command_fail: "Gagal: {error}",
        toast_single_output: "Single Output activated!",
        toast_dual_output: "Dual Output activated!",
        output_mode: "Output:",
        toast_command_error: "Error mengirim perintah kontrol",
        toast_playlist_saved: "Urutan playlist berhasil disimpan!",
        toast_playlist_save_fail: "Gagal menyimpan: {error}",
        toast_playlist_error: "Error menghubungi server untuk playlist",
        toast_device_added: "Perangkat \"{name}\" ditambahkan",
        toast_device_deleted: "Perangkat dihapus",
        toast_audio_muted: "Audio Layar {screen} Dimatikan",
        toast_audio_unmuted: "Audio Layar {screen} Dihidupkan",
        toast_audio_channel_changed: "Channel Audio Layar {screen} diubah ke {channel}",
        toast_clip_muted: "Audio klip \"{filename}\" Dimatikan",
        toast_clip_unmuted: "Audio klip \"{filename}\" Dihidupkan",
        nav_config: "🔧 Konfigurasi",
        config_header: "Konfigurasi Sistem & Tampilan",
        config_sub: "Sesuaikan tema warna preset, bahasa antarmuka, dan jalur koneksi jaringan",
        theme_select_label: "Preset Warna (Skin):",
        lang_select_label: "Bahasa Antarmuka (Language):",
        ui_settings_title: "🎨 Tampilan & Bahasa",
        network_settings_title: "🌐 Jalur Jaringan",
        network_select_label: "Pilih Antarmuka Aktif:",
        opt_eth: "Ethernet (ETH)",
        opt_wlan: "Wi-Fi (WLAN)",
        btn_save_network: "💾 Terapkan Jaringan",
        toast_network_saved: "Jalur jaringan berhasil diubah ke {interface}!",
        confirm_change_network: "PERINGATAN: Mengubah jalur jaringan akan mematikan antarmuka yang tidak terpilih. Jika Anda terhubung menggunakan antarmuka tersebut, koneksi Anda ke CMS ini akan terputus! Apakah Anda yakin ingin melanjutkan?",
        nav_schedule: "📅 Penjadwalan",
        schedule_header: "Jadwal Operasional",
        schedule_sub: "Atur jam hidup/mati otomatis dan jadwal pergantian playlist layar",
        btn_add_schedule: "➕ Tambah Jadwal",
        tz_select_label: "Timezone (GMT Offset):",
        th_time: "Waktu",
        th_days: "Hari",
        th_type: "Aksi",
        th_target: "Target",
        th_status: "Status",
        th_action: "Hapus",
        modal_schedule_title: "Tambah Jadwal Baru",
        sch_type: "Tipe Jadwal:",
        sch_type_power: "Power (Sleep/Wake Layar)",
        sch_type_playlist: "Putar Playlist Video",
        sch_power_action: "Aksi Power:",
        sch_act_sleep: "Standby / Matikan TV (Sleep)",
        sch_act_wake: "Nyalakan TV (Wake)",
        sch_screen_target: "Layar Target:",
        sch_playlist_name: "Nama Playlist:",
        sch_time: "Waktu (HH:MM):",
        sch_days: "Hari Pelaksanaan:",
        btn_cancel: "Batal",
        btn_save: "Simpan Jadwal",
        select_playlist_label: "Pilih Playlist:",
        toast_conflict: "Konflik: Jadwal sudah ada di waktu tersebut!",
        confirm_delete_schedule: "Hapus jadwal ini?",
        btn_shutdown: "🔌 Shutdown Pi",
        confirm_shutdown: "PERINGATAN: Apakah Anda yakin ingin mematikan (Shutdown) Raspberry Pi ini? Pi akan mati dan Anda harus mencabut-colok kabel daya atau menekan tombol fisik secara manual untuk menyalakannya kembali!",
        nav_playlists: "📋 Pengelola Playlist",
        media_files_list_title: "Daftar Berkas Aset Video",
        media_files_list_sub: "Semua video yang tersimpan di Raspberry Pi. Video-video ini dapat dimasukkan ke playlist mana saja.",
        playlist_list_title: "Daftar Playlist",
        playlist_compose_sub: "Pilih video di bawah untuk dimasukkan ke playlist, dan gunakan 🔼 / 🔽 untuk mengatur urutan putar.",
        assigned_playlist_header: "Playlist Aktif",
        toast_playlist_assigned: "Playlist {playlist} berhasil dipasang ke Layar {screen}!",
        confirm_delete_playlist: "Apakah Anda yakin ingin menghapus playlist \"{playlistName}\"?",
        confirm_delete_video_global: "Apakah Anda yakin ingin menghapus \"{filename}\"? Berkas ini akan dihapus permanen dari sistem dan dari semua playlist."
    },
    en: {
        brand_name: "caPiBarra",
        brand_sub: "Raspberry Pi Video CMS",
        nav_overview: "📊 Overview Grid",
        nav_control: "📺 Control Screen",
        nav_library: "📁 Media Library",
        nav_settings: "⚙️ Pi Settings",
        nav_about: "ℹ️ About App",
        active_device: "Connecting...",
        connecting: "Connecting...",
        status_offline_text: "Searching Device...",
        select_device: "Select Device:",
        btn_refresh: "🔄 Refresh",
        all_screens: "All Screen Devices",
        all_screens_sub: "Real-time status of all Raspberry Pi units in the museum",
        active_control: "Active Screen Control",
        active_control_sub: "Manage real-time video playback on HDMI monitors",
        auto_preview: "Auto Preview (5s)",
        screen1_title: "Screen 1 (HDMI-A-1)",
        screen2_title: "Screen 2 (HDMI-A-2)",
        btn_screenshot: "📸 Get Preview",
        no_media: "Playlist empty / Stopped",
        audio_control_header: "Audio Control",
        systemd_service_header: "Systemd Service",
        upload_title: "Upload New Video",
        drop_zone: "Drag & drop video files here, or click to browse",
        supported_formats: "Supported formats: MP4, MKV, AVI, MOV",
        target_screen_label: "Target Screen:",
        target_screen_1: "Screen 1 (HDMI-1)",
        target_screen_2: "Screen 2 (HDMI-2)",
        playlist_title: "Video Playlist",
        btn_save_order: "💾 Save Order",
        playlist_sub: "Use 🔼 and 🔽 buttons to reorder video playback",
        diagnostic_title: "Diagnostic Status",
        cpu_temp_label: "CPU Temperature",
        cpu_percent_label: "CPU Usage",
        ram_label: "RAM Used",
        disk_label: "Disk Space",
        device_model: "Model: Raspberry Pi 4 Model B",
        manage_pi: "Manage Pi Device List",
        new_device_name_label: "Device Name:",
        new_device_ip_label: "IP Address / Domain:",
        new_device_port_label: "Port:",
        btn_add_device: "➕ Add Device",
        registered_devices_title: "Registered Device List",
        th_name: "Name",
        th_ip: "IP Address",
        th_port: "Port",
        th_action: "Action",
        about_header: "About Application",
        about_sub: "Detailed information about the piEdge video player control software",
        about_desc_1: "<strong>piEdge CMS Signage</strong> is a web-based multimedia signage content management system (CMS) specifically developed to manage video playback independently or centrally on Raspberry Pi 4.",
        about_desc_2: "This software integrates a low-power multi-threaded web server with the MPV video programming interface via Unix IPC sockets, enabling high-performance video playback control directly to the hardware HDMI ports (HDMI-A-1 and HDMI-A-2) seamlessly, efficiently, and without lag.",
        
        opt_hdmi: "HDMI Output",
        opt_jack: "3.5mm Jack Output",
        opt_stereo: "Stereo",
        opt_left: "Channel L (Left)",
        opt_right: "Channel R (Right)",
        
        btn_start: "Start",
        btn_restart: "Restart",
        btn_stop: "Stop",
        
        uptime_label: "Uptime",
        status_online: "Online",
        status_offline: "Offline",
        connection_lost: "Connection Lost",
        status_playing: "Playing",
        status_active_no_mpv: "Active (No MPV)",
        status_service_inactive: "Service Inactive",
        status_stopped: "Stopped",
        status_unreachable: "Unreachable",
        empty_folder: "Media folder is empty. Please upload video files.",
        badge_muted: "🔇 Muted",
        badge_sound: "🔊 Sound",
        opt_muted: "🔇 Muted",
        opt_audio_on: "🔊 Audio ON",
        
        toast_device_offline_preview: "Device offline, cannot capture preview",
        toast_capturing_screenshot: "Capturing new screenshot for Screen {screen}...",
        toast_command_sent: "Command successfully sent",
        toast_refreshing: "Refreshing data...",
        toast_autopreview_on: "Auto preview enabled (5s)",
        toast_autopreview_off: "Auto preview disabled",
 
        library_header: "Media Library & Playlist Manager",
        library_sub_desc: "Upload new videos and configure playlist ordering for each screen",
        playlist_tab_1: "Screen 1 Playlist",
        playlist_tab_2: "Screen 2 Playlist",
        settings_header: "System & Device Configuration",
        settings_sub: "Manage Raspberry Pi IP addresses and view performance diagnostics",
        placeholder_device_name: "e.g., Lobby Screen",
        placeholder_device_ip: "e.g., 192.168.88.47",
        about_director: "Project Director",
        about_designer: "Lead Designer",
        about_uiux: "UI/UX",
        about_dev_team: "Development Team",
 
        confirm_delete_video: "Are you sure you want to delete \"{filename}\" from Screen {screen}?",
        confirm_delete_device: "Remove device \"{name}\" from control list?",
        toast_upload_success: "File uploaded successfully!",
        toast_upload_fail: "Failed to upload file!",
        toast_upload_error: "Connection failed during file upload",
        toast_upload_too_large: "File too large (max 500MB)!",
        toast_command_fail: "Failed: {error}",
        toast_single_output: "Single Output activated!",
        toast_dual_output: "Dual Output activated!",
        output_mode: "Output:",
        toast_command_error: "Error sending control command",
        toast_playlist_saved: "Playlist order saved successfully!",
        toast_playlist_save_fail: "Failed to save: {error}",
        toast_playlist_error: "Error contacting server for playlist",
        toast_device_added: "Device \"{name}\" added",
        toast_device_deleted: "Device removed",
        toast_audio_muted: "Screen {screen} Audio Muted",
        toast_audio_unmuted: "Screen {screen} Audio Enabled",
        toast_audio_route_changed: "Screen {screen} audio output routed to {route}",
        toast_audio_channel_changed: "Screen {screen} audio channel changed to {channel}",
        toast_clip_muted: "Clip \"{filename}\" audio muted",
        toast_clip_unmuted: "Clip \"{filename}\" audio enabled",
        nav_config: "🔧 Configuration",
        config_header: "System & UI Configuration",
        config_sub: "Customize color theme presets, interface language, and network connection path",
        theme_select_label: "Color Preset (Skin):",
        lang_select_label: "Interface Language:",
        ui_settings_title: "🎨 Presentation & Language",
        network_settings_title: "🌐 Network Interface",
        network_select_label: "Select Active Interface:",
        opt_eth: "Ethernet (ETH)",
        opt_wlan: "Wi-Fi (WLAN)",
        btn_save_network: "💾 Apply Network",
        toast_network_saved: "Network path successfully changed to {interface}!",
        confirm_change_network: "WARNING: Changing the network path will disable the unselected interface. If you are connected using that interface, your connection to this CMS will be lost! Are you sure you want to proceed?",
        nav_schedule: "📅 Scheduling",
        schedule_header: "Operational Schedule",
        schedule_sub: "Configure automatic power on/off and screen playlist changes",
        btn_add_schedule: "➕ Add Schedule",
        tz_select_label: "Timezone (GMT Offset):",
        th_time: "Time",
        th_days: "Days",
        th_type: "Action",
        th_target: "Target",
        th_status: "Status",
        th_action: "Delete",
        modal_schedule_title: "Add New Schedule",
        sch_type: "Schedule Type:",
        sch_type_power: "Power (Sleep/Wake Screen)",
        sch_type_playlist: "Play Video Playlist",
        sch_power_action: "Power Action:",
        sch_act_sleep: "Standby / Turn Off TV (Sleep)",
        sch_act_wake: "Turn On TV (Wake)",
        sch_screen_target: "Target Screen:",
        sch_playlist_name: "Playlist Name:",
        sch_time: "Time (HH:MM):",
        sch_days: "Execution Days:",
        btn_cancel: "Cancel",
        btn_save: "Save Schedule",
        select_playlist_label: "Select Playlist:",
        toast_conflict: "Conflict: A schedule already exists at this time!",
        confirm_delete_schedule: "Delete this schedule?",
        btn_shutdown: "🔌 Shutdown Pi",
        confirm_shutdown: "WARNING: Are you sure you want to shutdown this Raspberry Pi? It will power off, and you must manually reconnect power to turn it back on!",
        nav_playlists: "📋 Playlist Manager",
        media_files_list_title: "Video Asset Files List",
        media_files_list_sub: "All videos saved on the Raspberry Pi. These videos can be added to any playlist.",
        playlist_list_title: "Playlist List",
        playlist_compose_sub: "Select videos below to include in the playlist, and use 🔼 / 🔽 to adjust their playback order.",
        assigned_playlist_header: "Active Playlist",
        toast_playlist_assigned: "Playlist {playlist} successfully assigned to Screen {screen}!",
        confirm_delete_playlist: "Are you sure you want to delete playlist \"{playlistName}\"?",
        confirm_delete_video_global: "Are you sure you want to delete \"{filename}\"? This file will be permanently deleted from the system and all playlists."
    }
};

let currentLang = localStorage.getItem('piEdge_lang') || 'id';
let currentTheme = localStorage.getItem('piEdge_theme') || 'modern';

window.changeTheme = function(theme) {
    currentTheme = theme;
    localStorage.setItem('piEdge_theme', theme);
    applyTheme(theme);
    refreshAllData();
};

window.changeLanguage = function(lang) {
    currentLang = lang;
    localStorage.setItem('piEdge_lang', lang);
    applyLanguage(lang);
    refreshAllData();
};

function applyTheme(theme) {
    document.body.className = `theme-${theme}`;
}

function applyLanguage(lang) {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (i18n[lang] && i18n[lang][key]) {
            if (el.tagName === 'INPUT') {
                if (el.placeholder) {
                    el.placeholder = i18n[lang][key];
                }
            } else if (el.tagName === 'OPTION') {
                el.textContent = i18n[lang][key];
            } else {
                el.innerHTML = i18n[lang][key];
            }
        }
    });
}

function t(key, defaultValue = "") {
    if (i18n[currentLang] && i18n[currentLang][key]) {
        return i18n[currentLang][key];
    }
    return defaultValue || key;
}

let devices = [];
let activeDeviceId = '';
let serverIps = [];
let activeLibraryScreen = 1;
let statusInterval = null;
let screenshotInterval = null;
let overviewInterval = null;
let autoPreview = false; // Preview auto-polling flag (disabled by default)
let audioConfig = {};
let statusFailCount = 0;

// Cache DOM Elements
const deviceSwitcher = document.getElementById('device-switcher');
const globalStatusDot = document.getElementById('global-status-dot');
const globalStatusText = document.getElementById('global-status-text');
const activeDeviceName = document.getElementById('active-device-name');
const activeDeviceIp = document.getElementById('active-device-ip');
const toastEl = document.getElementById('toast');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    // Apply theme and language configs
    applyTheme(currentTheme);
    applyLanguage(currentLang);
    
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect) themeSelect.value = currentTheme;
    const langSelect = document.getElementById('lang-select');
    if (langSelect) langSelect.value = currentLang;

    setupTabNavigation();
    setupUploadZone();
    setupSettingsForm();
    
    // Bind device switcher change event ONCE (FIX: prevent listener accumulation)
    deviceSwitcher.addEventListener('change', (e) => {
        selectDevice(e.target.value);
    });
    
    document.getElementById('btn-refresh').addEventListener('click', () => {
        showToast(t('toast_refreshing', 'Menyegarkan data...'));
        refreshAllData();
    });

    // Setup Auto-Preview Toggle
    const previewToggle = document.getElementById('preview-toggle');
    if (previewToggle) {
        previewToggle.addEventListener('change', (e) => {
            autoPreview = e.target.checked;
            if (autoPreview) {
                showToast(t('toast_autopreview_on', 'Auto preview diaktifkan (5s)'));
                refreshScreenshots();
                if (screenshotInterval) clearInterval(screenshotInterval);
                screenshotInterval = setInterval(refreshScreenshots, 5000);
            } else {
                showToast(t('toast_autopreview_off', 'Auto preview dimatikan'));
                if (screenshotInterval) {
                    clearInterval(screenshotInterval);
                    screenshotInterval = null;
                }
            }
        });
    }

    // Initial load: fetch server IPs first, then load devices
    (async () => {
        await fetchServerInfo();
        await loadDevices();
        if (devices.length > 0) {
            // Default to local IP if available, or first device
            const defaultDev = devices.find(d => d.id === 'pi-1-local') || devices[0];
            selectDevice(defaultDev.id);
        }
        startPollers();
    })();
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
            } else if (targetTab === 'config') {
                fetchNetworkConfig();
            } else if (targetTab === 'playlists') {
                fetchPlaylistsAndSchedules().then(() => {
                    renderPlaylistsUI();
                });
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

    // Filter out deleted server-defined devices
    const deletedIds = JSON.parse(localStorage.getItem('museum_signage_deleted_devices') || '[]');
    devices = devices.filter(d => !deletedIds.includes(d.id));

    // Merge with localStorage overrides
    const localOverride = localStorage.getItem('museum_signage_devices');
    if (localOverride) {
        try {
            const parsed = JSON.parse(localOverride);
            // Merge: keep local overrides, add new ones
            parsed.forEach(ld => {
                if (deletedIds.includes(ld.id)) return; // skip deleted
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
        globalStatusText.textContent = t('connecting', 'Connecting...');
        
        // Immediate fetch
        refreshAllData();
    }
}

function getActiveDevice() {
    return devices.find(d => d.id === activeDeviceId);
}

// Resolve API URL based on active device
async function fetchServerInfo() {
    try {
        const res = await fetch('/api/server-info');
        if (res.ok) {
            const data = await res.json();
            serverIps = data.ips || [];
        }
    } catch (e) {
        console.warn("Could not fetch server info");
    }
}

function getApiUrl(endpoint) {
    const dev = getActiveDevice();
    if (!dev) return endpoint;

    const hostname = window.location.hostname;
    // If dev.ip is one of this server's IPs, use relative path to prevent CORS issues
    if (dev.ip === hostname || dev.ip === '127.0.0.1' || dev.ip === 'localhost' || serverIps.includes(dev.ip)) {
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
    fetchNetworkConfig();
}

// Fetch active device details
async function fetchActiveDeviceStatus() {
    const dev = getActiveDevice();
    if (!dev) return;

    try {
        const url = getApiUrl('/api/status');
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        if (!res.ok) throw new Error("Server error");
        
        const data = await res.json();
        window.lastFetchedStatus = data;
        
        // Update status header
        statusFailCount = 0;
        globalStatusDot.className = "dot online";
        globalStatusText.textContent = `${t('status_online', 'Online')} - ${data.system.uptime}`;
        
        // Update screen components
        audioConfig = data.audio || {};
        
        // Set output mode from server
        const mode = data.mode || 'dual';
        const modeSelect = document.getElementById('output-mode-select');
        if (modeSelect) modeSelect.value = mode;
        const s2Card = document.getElementById('s2-card');
        if (s2Card) s2Card.style.display = mode === 'single' ? 'none' : '';
        
        updateScreenControlUI(1, data.screen1, audioConfig.screen1);
        updateScreenControlUI(2, data.screen2, audioConfig.screen2);
        
        // Update diagnostics tab
        updateDiagnosticsUI(data.system);
        
        // Update Media Library UI using all_files
        const allFiles = (data.screen1 && data.screen1.all_files) || [];
        const playlist1 = (data.screen1 && data.screen1.playlist) || [];
        const playlist2 = (data.screen2 && data.screen2.playlist) || [];
        updateMediaLibraryUI(allFiles, playlist1, playlist2);

        // Update Playlist Composition UI if in playlist tab
        const activeTab = document.querySelector('.nav-btn.active')?.getAttribute('data-tab');
        if (activeTab === 'playlists') {
            syncPlaylistCompositionUI(allFiles);
        }

        // Fetch playlists/schedules to sync assignments (throttled: max once per 30s)
        if (!window._lastQuietFetch || Date.now() - window._lastQuietFetch > 30000) {
            window._lastQuietFetch = Date.now();
            fetchPlaylistsAndSchedulesQuietly();
        }

    } catch (e) {
        statusFailCount++;
        console.error(`Gagal kontak ke device active status (attempt ${statusFailCount}):`, e);
        
        if (statusFailCount < 3) {
            globalStatusDot.className = "dot connecting";
            globalStatusText.textContent = `${t('status_online', 'Online')} - ${t('connecting', 'Connecting...')}`;
        } else {
            globalStatusDot.className = "dot offline";
            globalStatusText.textContent = `${t('status_offline', 'Offline')} (${t('connection_lost', 'Connection Lost')})`;
            
            // Mark screens as offline
            document.getElementById('s1-status-badge').className = "badge badge-error";
            document.getElementById('s1-status-badge').textContent = t('status_offline', 'Offline');
            document.getElementById('s2-status-badge').className = "badge badge-error";
            document.getElementById('s2-status-badge').textContent = t('status_offline', 'Offline');
        }
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
    const channelSelect = document.getElementById(`s${screenNum}-select-audio-channel`);

    if (audioData) {
        const isMuted = audioData.global_mute;
        muteBtn.textContent = isMuted ? t('opt_muted', '🔇 Muted') : t('opt_audio_on', '🔊 Audio ON');
        muteBtn.className = isMuted ? "btn btn-sm btn-secondary" : "btn btn-sm btn-primary";
        if (document.activeElement !== routeSelect) {
            routeSelect.value = audioData.output_device || "hdmi";
        }
        if (document.activeElement !== channelSelect) {
            channelSelect.value = audioData.channel_mode || "stereo";
        }
    }


    // Service active status
    if (data.service_active) {
        statusBadge.className = "badge badge-success";
        statusBadge.textContent = data.mpv_connected ? t('status_playing', 'Playing') : t('status_active_no_mpv', 'Active (No MPV)');
    } else {
        statusBadge.className = "badge badge-error";
        statusBadge.textContent = t('status_service_inactive', 'Service Inactive');
    }

    // Play/Pause button symbol
    playBtn.textContent = data.paused ? "▶️" : "⏸️";
    playBtn.dataset.paused = data.paused;

    // Playing title
    titleEl.textContent = data.playing_file !== "None" ? data.playing_file : t('no_media', 'Daftar putar kosong / Berhenti');

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
        showToast(t('toast_device_offline_preview', 'Perangkat offline, tidak bisa mengambil preview'), true);
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
    
    showToast(t('toast_capturing_screenshot', 'Mengambil tangkapan layar baru untuk Layar {screen}...').replace('{screen}', screen));
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
            showToast(t('toast_command_sent', 'Perintah berhasil dikirim'));
            fetchActiveDeviceStatus();
        } else {
            showToast(t('toast_command_fail', 'Gagal: {error}').replace('{error}', data.error), true);
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Error mengirim perintah kontrol'), true);
    }
}

function togglePlay(screen) {
    const playBtn = document.getElementById(`s${screen}-btn-play`);
    const isPaused = playBtn.dataset.paused === 'true';
    controlDevice(screen, isPaused ? 'play' : 'pause');
}

async function toggleOutputMode(mode) {
    try {
        const url = getApiUrl('/api/output_mode');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, single_screen: 1 })
        });
        const data = await res.json();
        if (data.success) {
            const s2Card = document.getElementById('s2-card');
            if (mode === 'single') {
                if (s2Card) s2Card.style.display = 'none';
                showToast(t('toast_single_output', 'Single Output activated!'));
            } else {
                if (s2Card) s2Card.style.display = '';
                showToast(t('toast_dual_output', 'Dual Output activated!'));
            }
            setTimeout(() => fetchActiveDeviceStatus(), 3000);
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Error sending control command'), true);
    }
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

// --- Media Library ---
function updateMediaLibraryUI(allFiles, playlist1, playlist2) {
    const listEl = document.getElementById('media-library-items');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (!allFiles || allFiles.length === 0) {
        listEl.innerHTML = `<li class="playlist-item text-muted" data-i18n="empty_folder">${t('empty_folder', 'Folder media kosong. Silakan unggah file video.')}</li>`;
        return;
    }

    // Helper map to find sizes of files that are in either screen1 or screen2's playlist info
    const sizes = {};
    if (playlist1) playlist1.forEach(f => { if(f.size_mb) sizes[f.name] = f.size_mb; });
    if (playlist2) playlist2.forEach(f => { if(f.size_mb) sizes[f.name] = f.size_mb; });

    allFiles.forEach((fname) => {
        const sizeMb = sizes[fname] || '';
        const s1Settings = (audioConfig.screen1 && audioConfig.screen1.clip_settings) || {};
        const isClipMuted = s1Settings[fname] ? s1Settings[fname].mute : false;
        
        const muteBadgeClass = isClipMuted ? 'badge badge-error' : 'badge badge-success';
        const muteBadgeText = isClipMuted ? t('badge_muted', '🔇 Muted') : t('badge_sound', '🔊 Sound');

        const li = document.createElement('li');
        li.className = 'playlist-item';
        li.dataset.filename = fname;
        
        li.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; max-width: 75%;">
                <div class="item-info" style="max-width: 100%;">
                    <div class="item-header-row" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span class="item-name" style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600;" title="${fname}">${fname}</span>
                        <span class="${muteBadgeClass}" onclick="toggleClipMuteGlobal('${fname}')" style="cursor: pointer; font-size: 10px; padding: 2px 6px;" title="${t('opt_audio_on', 'Klik untuk ubah status suara')}">${muteBadgeText}</span>
                    </div>
                    <span class="item-size" style="font-size: 11px; color: var(--text-muted);">${sizeMb ? sizeMb + ' MB' : ''}</span>
                </div>
            </div>
            <div class="item-actions">
                <button class="btn btn-sm btn-danger" onclick="deleteVideoFileGlobal('${fname}')" title="Hapus Permanen">🗑️</button>
            </div>
        `;
        listEl.appendChild(li);
    });
}

// Delete media asset globally
async function deleteVideoFileGlobal(filename) {
    const msg = t('confirm_delete_video_global', 'Apakah Anda yakin ingin menghapus "{filename}"? Berkas ini akan dihapus permanen dari sistem dan dari semua playlist.')
        .replace('{filename}', filename);
    if (!confirm(msg)) {
        return;
    }

    try {
        const url = getApiUrl('/api/delete');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename
            })
        });

        const data = await res.json();
        if (data.success) {
            showToast(t('toast_video_deleted', 'Video berhasil dihapus'));
            fetchPlaylistsAndSchedules().then(() => {
                fetchActiveDeviceStatus();
            });
        } else {
            showToast(t('toast_command_fail', 'Gagal: {error}').replace('{error}', data.error), true);
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Error saat menghapus video'), true);
    }
}

// Toggle clip audio globally
async function toggleClipMuteGlobal(filename) {
    const s1Settings = (audioConfig.screen1 && audioConfig.screen1.clip_settings) || {};
    const currentMute = s1Settings[filename] ? s1Settings[filename].mute : false;
    const newMute = !currentMute;
    
    try {
        const url = getApiUrl('/api/audio/clip');
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: 1,
                filename: filename,
                mute: newMute
            })
        });
        
        await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: 2,
                filename: filename,
                mute: newMute
            })
        });
        
        const msg = newMute ?
            t('toast_clip_muted', 'Audio klip "{filename}" Dimatikan').replace('{filename}', filename) :
            t('toast_clip_unmuted', 'Audio klip "{filename}" Dihidupkan').replace('{filename}', filename);
        showToast(msg);
        fetchActiveDeviceStatus();
    } catch (e) {
        showToast(t('toast_command_error', 'Gagal mengubah status audio klip'), true);
    }
}

// File Upload Handler
function setupUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const progressWrapper = document.getElementById('upload-progress-wrapper');
    const progressBar = document.getElementById('upload-progress');
    const uploadFilename = document.getElementById('upload-filename');
    const uploadPercent = document.getElementById('upload-percent');

    if (!dropZone) return;

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
        const MAX_SIZE = 500 * 1024 * 1024; // 500MB
        if (file.size > MAX_SIZE) {
            showToast(t('toast_upload_too_large', 'File terlalu besar (maks 500MB)!'), true);
            return;
        }

        const url = getApiUrl(`/api/upload`);
        
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', file);

        progressWrapper.classList.remove('hidden');
        uploadFilename.textContent = file.name;
        progressBar.style.width = '0%';
        uploadPercent.textContent = '0%';

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = `${pct}%`;
                uploadPercent.textContent = pct < 100 ? `${pct}%` : `${pct}% - Memproses...`;
            }
        });

        xhr.addEventListener('load', () => {
            try {
                const resp = JSON.parse(xhr.responseText);
                if (xhr.status === 200 && resp.success) {
                    showToast(t('toast_upload_success', 'File berhasil diunggah!'));
                    setTimeout(() => progressWrapper.classList.add('hidden'), 1000);
                    fetchPlaylistsAndSchedules().then(() => fetchActiveDeviceStatus());
                } else {
                    showToast(resp.error || t('toast_upload_fail', 'Gagal mengunggah file!'), true);
                    setTimeout(() => progressWrapper.classList.add('hidden'), 2000);
                }
            } catch(e) {
                showToast(t('toast_upload_fail', 'Gagal mengunggah file!'), true);
                setTimeout(() => progressWrapper.classList.add('hidden'), 2000);
            }
        });

        xhr.addEventListener('error', () => {
            showToast(t('toast_upload_error', 'Koneksi gagal saat mengunggah file'), true);
            progressWrapper.classList.add('hidden');
        });

        xhr.timeout = 600000; // 10 minutes
        xhr.addEventListener('timeout', () => {
            showToast(t('toast_upload_error', 'Upload timeout'), true);
            progressWrapper.classList.add('hidden');
        });

        xhr.open('POST', url, true);
        xhr.send(formData);
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
        showToast(t('toast_device_added', 'Perangkat "{name}" ditambahkan').replace('{name}', name));
        
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

    const msg = t('confirm_delete_device', 'Hapus perangkat "{name}" dari daftar kontrol?').replace('{name}', device.name);
    if (!confirm(msg)) {
        return;
    }

    // Add to deleted IDs list
    const deletedIds = JSON.parse(localStorage.getItem('museum_signage_deleted_devices') || '[]');
    if (!deletedIds.includes(id)) {
        deletedIds.push(id);
        localStorage.setItem('museum_signage_deleted_devices', JSON.stringify(deletedIds));
    }

    devices = devices.filter(d => d.id !== id);
    localStorage.setItem('museum_signage_devices', JSON.stringify(devices));
    showToast(t('toast_device_deleted', 'Perangkat dihapus'));
    
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
    const routeSelect = document.getElementById(`s${screen}-select-audio-route`);
    const outputDevice = routeSelect ? routeSelect.value : 'hdmi';
    const channelSelect = document.getElementById(`s${screen}-select-audio-channel`);
    const channelMode = channelSelect ? channelSelect.value : 'stereo';
    
    try {
        const url = getApiUrl('/api/audio/global');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                global_mute: !currentMute,
                output_device: outputDevice,
                channel_mode: channelMode
            })
        });
        const data = await res.json();
        if (data.success) {
            const msg = !currentMute ? 
                t('toast_audio_muted', 'Audio Layar {screen} Dimatikan').replace('{screen}', screen) :
                t('toast_audio_unmuted', 'Audio Layar {screen} Dihidupkan').replace('{screen}', screen);
            showToast(msg);
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Gagal mengubah status audio'), true);
    }
}

async function changeAudioRoute(screen) {
    const screenKey = `screen${screen}`;
    const currentMute = audioConfig[screenKey] ? audioConfig[screenKey].global_mute : true;
    const routeSelect = document.getElementById(`s${screen}-select-audio-route`);
    const newRoute = routeSelect.value;
    const channelSelect = document.getElementById(`s${screen}-select-audio-channel`);
    const channelMode = channelSelect ? channelSelect.value : 'stereo';
    
    try {
        const url = getApiUrl('/api/audio/global');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                global_mute: currentMute,
                output_device: newRoute,
                channel_mode: channelMode
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(t('toast_audio_route_changed', 'Output Audio Layar {screen} dialihkan ke {route}')
                .replace('{screen}', screen)
                .replace('{route}', newRoute.toUpperCase()));
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Gagal mengubah rute audio'), true);
    }
}

async function changeAudioChannel(screen) {
    const screenKey = `screen${screen}`;
    const currentMute = audioConfig[screenKey] ? audioConfig[screenKey].global_mute : true;
    const routeSelect = document.getElementById(`s${screen}-select-audio-route`);
    const outputDevice = routeSelect ? routeSelect.value : 'hdmi';
    const channelSelect = document.getElementById(`s${screen}-select-audio-channel`);
    const newChannel = channelSelect.value;
    
    try {
        const url = getApiUrl('/api/audio/global');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                global_mute: currentMute,
                output_device: outputDevice,
                channel_mode: newChannel
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(t('toast_audio_channel_changed', 'Channel Audio Layar {screen} diubah ke {channel}')
                .replace('{screen}', screen)
                .replace('{channel}', newChannel.toUpperCase()));
            fetchActiveDeviceStatus();
        }
    } catch (e) {
        showToast(t('toast_command_error', 'Gagal mengubah channel audio'), true);
    }
}

// --- Scheduling & Multiple Playlists Logic ---
let schedulesData = { timezone_offset: 7, events: [] };
let playlistsData = { playlists: { "Default": [] }, assignments: { "screen1": "Default", "screen2": "Default" } };
let currentSelectedPlaylist = "Default";

async function fetchPlaylistsAndSchedules() {
    try {
        const pRes = await fetch(getApiUrl('/api/playlists/list'));
        if (pRes.ok) {
            playlistsData = await pRes.json();
            if (!playlistsData.playlists) playlistsData.playlists = { "Default": [] };
            if (!playlistsData.assignments) playlistsData.assignments = { "screen1": "Default", "screen2": "Default" };
            updateControlScreenPlaylistDropdowns();
            renderPlaylistsUI();
        }
        
        const sRes = await fetch(getApiUrl('/api/schedule/config'));
        if (sRes.ok) {
            schedulesData = await sRes.json();
            const tzSelect = document.getElementById('tz-select');
            if (tzSelect && document.activeElement !== tzSelect) {
                tzSelect.value = schedulesData.timezone_offset || 7;
            }
            updateScheduleUI();
            updateSchedulePlaylistOptions();
        }
    } catch(e) {
        console.error("Error fetching playlists/schedules", e);
    }
}

// Quiet version to prevent visual spam
async function fetchPlaylistsAndSchedulesQuietly() {
    try {
        const pRes = await fetch(getApiUrl('/api/playlists/list'));
        if (pRes.ok) {
            playlistsData = await pRes.json();
            if (!playlistsData.playlists) playlistsData.playlists = { "Default": [] };
            if (!playlistsData.assignments) playlistsData.assignments = { "screen1": "Default", "screen2": "Default" };
            updateControlScreenPlaylistDropdowns();
        }
        
        const sRes = await fetch(getApiUrl('/api/schedule/config'));
        if (sRes.ok) {
            schedulesData = await sRes.json();
        }
    } catch(e) {
        // Quiet fail
    }
}

// Intercept original loadDevices to include this fetch on load
const originalLoadDevices = loadDevices;
loadDevices = async function() {
    await originalLoadDevices();
    fetchPlaylistsAndSchedules();
}

function updateSchedulePlaylistOptions() {
    const selModal = document.getElementById('sch-playlist-name');
    if (!selModal) return;
    selModal.innerHTML = '';
    
    const playlists = playlistsData.playlists || {};
    Object.keys(playlists).forEach(pName => {
        const opt = document.createElement('option');
        opt.value = pName;
        opt.textContent = pName;
        selModal.appendChild(opt);
    });
}

function updateControlScreenPlaylistDropdowns() {
    const s1Select = document.getElementById('s1-select-assigned-playlist');
    const s2Select = document.getElementById('s2-select-assigned-playlist');
    if (!s1Select || !s2Select) return;

    const s1Active = (playlistsData.assignments && playlistsData.assignments.screen1) || 'Default';
    const s2Active = (playlistsData.assignments && playlistsData.assignments.screen2) || 'Default';

    [s1Select, s2Select].forEach((selectEl) => {
        selectEl.innerHTML = '';
        const playlists = playlistsData.playlists || {};
        Object.keys(playlists).forEach(pName => {
            const opt = document.createElement('option');
            opt.value = pName;
            opt.textContent = pName;
            selectEl.appendChild(opt);
        });
    });

    s1Select.value = s1Active;
    s2Select.value = s2Active;
}

async function saveAllPlaylists() {
    try {
        const url = getApiUrl('/api/playlists/save_all');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(playlistsData)
        });
        const data = await res.json();
        if (data.success) {
            renderPlaylistsUI();
            updateSchedulePlaylistOptions();
            updateControlScreenPlaylistDropdowns();
        } else {
            showToast("Gagal menyimpan playlist", true);
        }
    } catch (e) {
        showToast("Error saving playlists", true);
    }
}

// Playlist manager views rendering
function renderPlaylistsUI() {
    const listEl = document.getElementById('global-playlist-names-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    const playlists = playlistsData.playlists || {};
    
    // Ensure Default playlist always exists
    if (!playlists["Default"]) {
        playlists["Default"] = [];
    }

    Object.keys(playlists).forEach(pName => {
        const li = document.createElement('li');
        li.className = `playlist-item ${currentSelectedPlaylist === pName ? 'active' : ''}`;

        li.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                selectPlaylist(pName);
            }
        });

        const nameSpan = document.createElement('span');
        nameSpan.textContent = pName;
        nameSpan.style.fontWeight = '500';
        li.appendChild(nameSpan);

        if (pName !== 'Default') {
            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-danger';
            delBtn.style.padding = '4px 8px';
            delBtn.textContent = '🗑️';
            delBtn.title = t('confirm_delete_playlist', 'Hapus playlist ini').replace('{playlistName}', pName);
            delBtn.addEventListener('click', () => {
                deletePlaylist(pName);
            });
            li.appendChild(delBtn);
        }

        listEl.appendChild(li);
    });

    const headerTitle = document.getElementById('selected-playlist-title-header');
    if (headerTitle) {
        headerTitle.textContent = `Playlist: ${currentSelectedPlaylist}`;
    }

    let allFiles = (window.lastFetchedStatus && window.lastFetchedStatus.screen1 && window.lastFetchedStatus.screen1.all_files) || [];
    // If no data fetched yet, try to fetch it
    if (allFiles.length === 0 && !window._initialPlaylistFetchDone) {
        window._initialPlaylistFetchDone = true;
        fetchActiveDeviceStatus().then(() => {
            const freshFiles = (window.lastFetchedStatus && window.lastFetchedStatus.screen1 && window.lastFetchedStatus.screen1.all_files) || [];
            syncPlaylistCompositionUI(freshFiles);
        });
        return;
    }
    syncPlaylistCompositionUI(allFiles);
}

function selectPlaylist(pName) {
    currentSelectedPlaylist = pName;
    renderPlaylistsUI();
}

function deletePlaylist(pName) {
    const msg = t('confirm_delete_playlist', 'Apakah Anda yakin ingin menghapus playlist "{playlistName}"?')
        .replace('{playlistName}', pName);
    if (!confirm(msg)) return;

    if (playlistsData.playlists && playlistsData.playlists[pName]) {
        delete playlistsData.playlists[pName];
        
        if (playlistsData.assignments) {
            if (playlistsData.assignments.screen1 === pName) playlistsData.assignments.screen1 = 'Default';
            if (playlistsData.assignments.screen2 === pName) playlistsData.assignments.screen2 = 'Default';
        }

        if (currentSelectedPlaylist === pName) {
            currentSelectedPlaylist = 'Default';
        }

        saveAllPlaylists();
    }
}

function createNewPlaylistFromInput() {
    const inputEl = document.getElementById('new-playlist-name-input');
    if (!inputEl) return;
    const name = inputEl.value.trim();
    if (!name) {
        alert("Nama playlist tidak boleh kosong!");
        return;
    }

    if (!playlistsData.playlists) playlistsData.playlists = {};
    if (playlistsData.playlists[name]) {
        alert("Playlist dengan nama tersebut sudah ada!");
        return;
    }

    playlistsData.playlists[name] = [];
    currentSelectedPlaylist = name;
    inputEl.value = '';
    
    saveAllPlaylists();
}

function syncPlaylistCompositionUI(allFiles) {
    const listEl = document.getElementById('playlist-composition-items');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (!allFiles || allFiles.length === 0) {
        listEl.innerHTML = `<li class="playlist-item text-muted">${t('empty_folder', 'Folder media kosong. Silakan unggah file video.')}</li>`;
        return;
    }

    const playlists = playlistsData.playlists || {};
    const currentPlaylistFiles = playlists[currentSelectedPlaylist] || [];

    let orderedFiles = [];
    currentPlaylistFiles.forEach(fname => {
        const found = allFiles.find(f => f === fname);
        if (found) orderedFiles.push(found);
    });
    allFiles.forEach(f => {
        if (!currentPlaylistFiles.includes(f)) {
            orderedFiles.push(f);
        }
    });

    orderedFiles.forEach((fname, index) => {
        const isSelected = currentPlaylistFiles.includes(fname);
        
        const li = document.createElement('li');
        li.className = 'playlist-item';
        li.dataset.filename = fname;
        
        li.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; max-width: 65%;">
                <input type="checkbox" class="playlist-checkbox" ${isSelected ? 'checked' : ''} style="cursor:pointer;" title="Sertakan ke playlist ini">
                <div class="item-info" style="max-width: 100%;">
                    <span class="item-name" style="font-weight: 500; font-size: 14px;" title="${fname}">${fname}</span>
                </div>
            </div>
            <div class="item-actions">
                <button class="btn btn-sm btn-secondary" onclick="movePlaylistCompItem(${index}, -1)" ${index === 0 ? 'disabled' : ''}>🔼</button>
                <button class="btn btn-sm btn-secondary" onclick="movePlaylistCompItem(${index}, 1)" ${index === orderedFiles.length - 1 ? 'disabled' : ''}>🔽</button>
            </div>
        `;

        // FIX: Immediately sync checkbox state to playlistsData
        // so polling re-renders don't lose user's unsaved changes
        const checkbox = li.querySelector('.playlist-checkbox');
        checkbox.addEventListener('change', function() {
            if (!playlistsData.playlists) playlistsData.playlists = {};
            const pl = playlistsData.playlists[currentSelectedPlaylist] || [];
            if (this.checked) {
                if (!pl.includes(fname)) pl.push(fname);
            } else {
                playlistsData.playlists[currentSelectedPlaylist] = pl.filter(f => f !== fname);
            }
        });

        listEl.appendChild(li);
    });
}

function movePlaylistCompItem(index, direction) {
    const listEl = document.getElementById('playlist-composition-items');
    if (!listEl) return;
    const items = Array.from(listEl.children);
    
    if (direction === -1 && index > 0) {
        listEl.insertBefore(items[index], items[index - 1]);
    } else if (direction === 1 && index < items.length - 1) {
        listEl.insertBefore(items[index + 1], items[index]);
    }
    
    // Save current DOM order to playlistsData BEFORE re-render
    const currentItems = Array.from(listEl.children).map(li => li.dataset.filename).filter(Boolean);
    if (currentItems.length > 0 && playlistsData.playlists) {
        playlistsData.playlists[currentSelectedPlaylist] = currentItems;
    }
    
    // Re-render to update stale onclick indices
    let allFiles = (window.lastFetchedStatus && window.lastFetchedStatus.screen1 && window.lastFetchedStatus.screen1.all_files) || [];
    syncPlaylistCompositionUI(allFiles);
}

function refreshPlaylistCompOrderButtons() {
    const listEl = document.getElementById('playlist-composition-items');
    if (!listEl) return;
    const items = Array.from(listEl.children);
    items.forEach((item, index) => {
        const upBtn = item.querySelector('.item-actions button:nth-child(1)');
        const downBtn = item.querySelector('.item-actions button:nth-child(2)');
        if (upBtn) upBtn.disabled = (index === 0);
        if (downBtn) downBtn.disabled = (index === items.length - 1);
    });
}

function savePlaylistComposition() {
    const listEl = document.getElementById('playlist-composition-items');
    if (!listEl) return;
    const items = Array.from(listEl.children);
    
    const filenames = items
        .filter(li => {
            const cb = li.querySelector('.playlist-checkbox');
            return cb ? cb.checked : false;
        })
        .map(li => li.dataset.filename).filter(Boolean);

    if (!playlistsData.playlists) playlistsData.playlists = {};
    playlistsData.playlists[currentSelectedPlaylist] = filenames;
    
    saveAllPlaylists();
    showToast(t('toast_playlist_saved', 'Playlist berhasil disimpan!'));
}

async function assignPlaylistToScreen(screen, playlistName) {
    try {
        const url = getApiUrl('/api/playlists/assign');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screen: screen,
                playlist_name: playlistName
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(t('toast_playlist_assigned', 'Playlist {playlist} berhasil dipasang ke Layar {screen}!')
                .replace('{playlist}', playlistName)
                .replace('{screen}', screen));
            
            if (!playlistsData.assignments) playlistsData.assignments = {};
            playlistsData.assignments[`screen${screen}`] = playlistName;
            
            fetchActiveDeviceStatus();
        } else {
            showToast("Gagal memasang playlist", true);
        }
    } catch (e) {
        showToast("Error saat menghubungi server", true);
    }
}

// Scheduling UI
function updateScheduleUI() {
    const tbody = document.getElementById('schedule-table-body');
    if(!tbody) return;
    tbody.innerHTML = '';
    
    if(!schedulesData.events || schedulesData.events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">Belum ada jadwal operasional.</td></tr>`;
        return;
    }
    
    schedulesData.events.forEach(ev => {
        const tr = document.createElement('tr');
        const days = ev.days.join(', ');
        const actionStr = ev.type === 'power' ? `Power ${ev.action.toUpperCase()}` : `Load Playlist`;
        const targetStr = ev.type === 'power' ? 'All System' : `Screen ${ev.screen} (${ev.playlist_name})`;
        const statusClass = ev.enabled ? 'badge-success' : 'badge-error';
        const statusText = ev.enabled ? 'Active' : 'Disabled';
        
        tr.innerHTML = `
            <td><strong>${ev.time}</strong></td>
            <td style="font-size: 11px;">${days}</td>
            <td><span class="badge" style="background: rgba(255,255,255,0.1); border: 1px solid var(--border-color);">${actionStr}</span></td>
            <td>${targetStr}</td>
            <td><span class="badge ${statusClass}" style="cursor:pointer;" onclick="toggleScheduleStatus('${ev.id}')">${statusText}</span></td>
            <td><button class="btn btn-sm btn-danger" onclick="deleteSchedule('${ev.id}')">Hapus</button></td>
        `;
        tbody.appendChild(tr);
    });
}

window.saveTimezone = async function() {
    schedulesData.timezone_offset = parseInt(document.getElementById('tz-select').value);
    await saveSchedulesData();
    showToast("Timezone berhasil disimpan");
}

window.openScheduleModal = function() {
    document.getElementById('schedule-modal').classList.remove('hidden');
    toggleScheduleForm();
    // Refresh modal dropdown just in case
    updateSchedulePlaylistOptions();
}

window.closeScheduleModal = function() {
    document.getElementById('schedule-modal').classList.add('hidden');
}

window.toggleScheduleForm = function() {
    const type = document.getElementById('sch-type').value;
    if(type === 'power') {
        document.getElementById('sch-power-fields').classList.remove('hidden');
        document.getElementById('sch-playlist-fields').classList.add('hidden');
    } else {
        document.getElementById('sch-power-fields').classList.add('hidden');
        document.getElementById('sch-playlist-fields').classList.remove('hidden');
    }
}

window.saveNewSchedule = async function() {
    const type = document.getElementById('sch-type').value;
    const time = document.getElementById('sch-time').value;
    if(!time) { alert("Pilih waktu eksekusi"); return; }
    
    const dayCheckboxes = document.querySelectorAll('#sch-days input:checked');
    const days = Array.from(dayCheckboxes).map(cb => cb.value);
    if(days.length === 0) { alert("Pilih minimal 1 hari pelaksanaan"); return; }
    
    // Conflict Check
    const isConflict = schedulesData.events.some(ev => ev.time === time && ev.days.some(d => days.includes(d)));
    if(isConflict) {
        if(!confirm(t('toast_conflict', "Konflik: Jadwal sudah ada di waktu tersebut! Lanjutkan?"))) return;
    }
    
    const newEvent = {
        id: "sch-" + Date.now(),
        type: type,
        time: time,
        days: days,
        enabled: true
    };
    
    if(type === 'power') {
        newEvent.action = document.getElementById('sch-power-action').value;
    } else {
        newEvent.screen = parseInt(document.getElementById('sch-screen').value);
        newEvent.playlist_name = document.getElementById('sch-playlist-name').value;
    }
    
    if(!schedulesData.events) schedulesData.events = [];
    schedulesData.events.push(newEvent);
    
    await saveSchedulesData();
    closeScheduleModal();
}

window.deleteSchedule = async function(id) {
    if(!confirm(t('confirm_delete_schedule', 'Hapus jadwal ini?'))) return;
    schedulesData.events = schedulesData.events.filter(e => e.id !== id);
    await saveSchedulesData();
}

window.toggleScheduleStatus = async function(id) {
    const ev = schedulesData.events.find(e => e.id === id);
    if(ev) {
        ev.enabled = !ev.enabled;
        await saveSchedulesData();
    }
}

async function saveSchedulesData() {
    try {
        const res = await fetch(getApiUrl('/api/schedule/save'), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(schedulesData)
        });
        if(res.ok) {
            updateScheduleUI();
        } else {
            showToast("Gagal menyimpan jadwal", true);
        }
    } catch(e) {
        showToast("Error menghubungi server", true);
    }
}

window.shutdownSystem = async function() {
    if(!confirm(t('confirm_shutdown', 'WARNING: Shutdown Pi?'))) return;
    
    try {
        const res = await fetch(getApiUrl('/api/system/shutdown'), { method: 'POST' });
        if(res.ok) {
            showToast("Perintah Shutdown berhasil dikirim. Alat akan mati dalam 1 detik.");
        } else {
            showToast("Gagal mengirim perintah shutdown", true);
        }
    } catch (e) {
        showToast("Error jaringan saat mengirim shutdown", true);
    }
}

async function fetchNetworkConfig() {
    const activeTab = document.querySelector('.nav-btn.active').getAttribute('data-tab');
    if (activeTab !== 'config') return;

    try {
        const url = getApiUrl('/api/network/config');
        const res = await fetch(url);
        if (res.ok) {
            const data = await res.json();
            
            const netSelect = document.getElementById('network-select');
            if (netSelect && document.activeElement !== netSelect) {
                netSelect.value = data.selected || "eth";
            }
            
            const ethStatusEl = document.getElementById('net-eth-status');
            const wlanStatusEl = document.getElementById('net-wlan-status');
            
            if (ethStatusEl && data.interfaces.eth) {
                const ethInfo = data.interfaces.eth.map(i => `${i.name}: ${i.ip} (${i.status.toUpperCase()})`).join('<br>');
                ethStatusEl.innerHTML = ethInfo || 'None';
            }
            if (wlanStatusEl && data.interfaces.wlan) {
                const wlanInfo = data.interfaces.wlan.map(i => `${i.name}: ${i.ip} (${i.status.toUpperCase()})`).join('<br>');
                wlanStatusEl.innerHTML = wlanInfo || 'None';
            }
        }
    } catch (e) {
        console.error("Error fetching network config", e);
    }
}

window.fetchNetworkConfig = fetchNetworkConfig;

window.saveNetworkConfig = async function() {
    const netSelect = document.getElementById('network-select');
    if (!netSelect) return;
    const selected = netSelect.value;
    
    const msg = t('confirm_change_network', 'PERINGATAN: Mengubah jalur jaringan akan mematikan antarmuka yang tidak terpilih. Jika Anda terhubung menggunakan antarmuka tersebut, koneksi Anda ke CMS ini akan terputus! Apakah Anda yakin ingin melanjutkan?');
    if (!confirm(msg)) {
        return;
    }
    
    try {
        const url = getApiUrl('/api/network/save');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ selected })
        });
        
        const data = await res.json();
        if (data.success) {
            showToast(t('toast_network_saved', 'Jalur jaringan berhasil diubah ke {interface}!').replace('{interface}', selected.toUpperCase()));
            setTimeout(fetchNetworkConfig, 1000);
        } else {
            showToast("Gagal menyimpan jalur jaringan", true);
        }
    } catch (e) {
        showToast("Error saat menghubungi server", true);
    }
};

// Bind remaining inline onclick functions to window for global availability
window.deleteVideoFile = deleteVideoFileGlobal;
window.movePlaylistItem = movePlaylistCompItem;
window.toggleClipMute = toggleClipMuteGlobal;
window.changeAudioChannel = changeAudioChannel;
window.changeAudioRoute = changeAudioRoute;
window.toggleGlobalMute = toggleGlobalMute;
window.togglePlay = togglePlay;
window.controlDevice = controlDevice;
window.refreshSingleScreenshot = refreshSingleScreenshot;

window.deleteRegisteredDevice = deleteRegisteredDevice;
window.createNewPlaylistFromInput = createNewPlaylistFromInput;
window.savePlaylistComposition = savePlaylistComposition;
window.deletePlaylist = deletePlaylist;
window.selectPlaylist = selectPlaylist;
window.movePlaylistCompItem = movePlaylistCompItem;
window.toggleClipMuteGlobal = toggleClipMuteGlobal;
window.deleteVideoFileGlobal = deleteVideoFileGlobal;
window.assignPlaylistToScreen = assignPlaylistToScreen;


