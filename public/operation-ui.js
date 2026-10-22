// Pi 5 operation-mode controls; API URL follows selected CMS device.
(() => {
  const mount = document.querySelector('#tab-control .output-mode-card');
  if (!mount) return;
  const panel = document.createElement('div');
  panel.className = 'output-mode-card';
  panel.innerHTML = '<div><h3>Mode Operasi</h3><p>Manual mengabaikan jadwal. Setelah reboot kembali Auto.</p></div><div class="output-mode-actions"><label for="operation-select">Mode:</label><select id="operation-select" class="form-select"><option value="auto">Auto Schedule</option><option value="on">Manual ON</option><option value="off">Manual OFF</option></select><button id="operation-apply" class="btn btn-primary" disabled>Terapkan</button></div><p id="operation-status" role="status" aria-live="polite">Memuat mode…</p>';
  mount.before(panel);
  const select = panel.querySelector('select'), button = panel.querySelector('button'), status = panel.querySelector('[role=status]');
  let busy = false, loadedUrl = '';
  async function refresh() {
    if (busy) return;
    const url = getApiUrl('/api/operation-mode');
    try {
      const response = await fetch(url, {cache:'no-store', signal:AbortSignal.timeout(5000)});
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Gagal membaca mode');
      if (url !== getApiUrl('/api/operation-mode')) return;
      if (document.activeElement !== select) select.value = data.mode;
      status.textContent = data.mode === 'auto' ? 'Aktif: Auto — mengikuti jadwal.' : 'Aktif: Manual ' + data.mode.toUpperCase() + ' — jadwal diabaikan. Kembalikan ke Auto setelah tes.';
      loadedUrl = url; button.disabled = false;
    } catch (e) { status.textContent = 'Mode tidak tersedia: ' + e.message; button.disabled = true; }
  }
  button.addEventListener('click', async () => {
    const url = getApiUrl('/api/operation-mode');
    if (url !== loadedUrl) { await refresh(); return; }
    if (select.value !== 'auto' && !confirm('Mode manual akan mengabaikan jadwal. Lanjutkan?')) return;
    busy = true; button.disabled = true; select.disabled = true;
    try {
      const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode:select.value}), signal:AbortSignal.timeout(5000)});
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Gagal menyimpan');
      status.textContent = 'Mode tersimpan; player menerapkan perubahan.';
    } catch (e) { status.textContent = 'Gagal: ' + e.message; }
    finally { busy = false; select.disabled = false; button.disabled = false; }
    await refresh();
  });
  refresh(); setInterval(refresh, 5000);
})();
