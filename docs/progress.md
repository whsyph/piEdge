# Progress checkpoint — Pi4 only

## Confirmation

Deployment native DRM selesai pada 23 Oktober 2026. Operator kemudian melaporkan
playback sudah smooth dan meminta progress/commit khusus Pi4, tidak dicampur Pi5.

## Scope checkpoint ini

- Profil/source Pi4 direct DRM, native DPMS lease, splash, audio/mode/playlist,
  unit service, CMS dengan preview aman dan aset UI yang benar-benar terpasang.
- Tes regresi profil serta guard pemisahan target/payload.
- Dokumentasi pengujian, batas kemampuan dan rollback.
- Tidak menyertakan video/media operator, playlist, schedules, audio preferences,
  operation-mode record, network configuration, secrets, cache atau backup.
- Konfigurasi `candidate/config.json` hanya parameter teknis profil dan path
  kontrak; tidak berisi jadwal, daftar video, override atau credential.

## Verifikasi deployment terakhir sebelum checkpoint

Pengecekan sebelumnya pada 03:29 WIB: Pi4 pi-1 aktif, direct DRM + hardware decode,
A/V dilaporkan mendekati nol dan dropped-frame counter 10 -> 10 pada sampel sekitar
lima detik. Suhu 42,8 C, throttled=0x0, swap tidak terpakai, service gagal tidak ada.
Mode ON dan audio unmute. Ini bukti sampel, bukan burn-in semalam.

## Pemisahan Git

- Folder/branch Pi4: `caPIbarra-lite-pi4` / `capibarra-lite-pi4`.
- Branch Pi5 `capibarra-lite` tetap pada snapshot Pi5-nya; tidak di-merge/dipush
  oleh tugas commit Pi4 ini.
- Folder Pi5 yang memiliki perubahan packaging lokal tidak di-reset, di-checkout,
  di-stash atau ditimpa. Snapshot hash sumber dirty diperiksa sebelum/sesudah.
- Commit checkpoint ini lokal saja, sesuai permintaan commit. Push GitHub dan
  penggabungan branch merupakan langkah terpisah setelah diminta pengguna.

## Operasional

Pi4 memakai nama service historis `pi5-signage.service`; jangan menebak model
board dari nama service. Board target dan renderer eksplisit ada di profile.json.
Live HDMI capture sengaja tidak tersedia karena memicu underrun; CMS memberi
keterangan, bukan gambar stale. Jadwal/metadata operator tetap di perangkat.

Bukti rinci: 02-verification.md. Backup/rollback: 03-operations.md. Kode installer
adalah migrasi baseline yang dijaga hash, bukan klaim fresh-install pada semua Pi4.
