// Operation mode controls follow the selected CMS device, never change schedules.
(() => {
  const mount = document.querySelector('#operation-mode-mount');
  if (!mount) return;
  mount.innerHTML = '<h3>Mode Operasi</h3><p>Manual mengabaikan jadwal. Setelah reboot kembali Auto.</p><div class="operation-mode-actions"><label for="operation-select">Mode:</label><select id="operation-select" class="form-select"><option value="auto">Auto Schedule</option><option value="on">Manual ON</option><option value="off">Manual OFF</option></select><button id="operation-apply" class="btn btn-primary" disabled>Terapkan</button></div><p id="operation-status" role="status" aria-live="polite">Memuat mode…</p>';
  const select = mount.querySelector('select'), button = mount.querySelector('button'), status = mount.querySelector('[role=status]');
  let busy = false, loadedUrl = '', dirty = false;
  select.addEventListener('change', () => { dirty = true; });
  async function refresh() {
    if (busy) return;
    const url = getApiUrl('/api/operation-mode');
    try {
      const response = await fetch(url, {cache:'no-store', signal:AbortSignal.timeout(5000)});
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Gagal membaca mode');
      if (url !== getApiUrl('/api/operation-mode')) return;
      if (!dirty || loadedUrl !== url) { select.value = data.mode; dirty = false; }
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
      dirty = false;
      status.textContent = 'Mode tersimpan; player menerapkan perubahan.';
    } catch (e) { status.textContent = 'Gagal: ' + e.message; }
    finally { busy = false; select.disabled = false; button.disabled = false; }
    await refresh();
  });
  refresh(); setInterval(refresh, 5000);
})();
