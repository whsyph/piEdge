# caPIbarra-lite — Pi4 Direct DRM

**Branch khusus Pi4: `capibarra-lite-pi4`. Jangan merge profil hardware ini ke
branch Pi5 `capibarra-lite`.** Folder kerja Pi4 juga terpisah dari folder Pi5.

Ini checkpoint deployment yang sudah berjalan pada Raspberry Pi 4 Model B,
bukan installer umum untuk perangkat kosong. Kode, unit, konfigurasi teknis,
CMS dan aset UI disalin dari deployment Pi4 yang diverifikasi. Data operator,
media, credential dan backup perangkat tidak disertakan.

## Profil Pi4

- mpv GPU context **DRM**, interop **drmprime-overlay**, hardware decode **DRM**.
- Hardware video plane **primary** dan drawing/OSD plane **overlay**.
- Konten yang diuji: **HEVC Main10, 3840×2160 ~60fps, AAC stereo**.
- Display yang diuji mengiklankan **1080p60**; sumber UHD diperkecil oleh hardware.
  Output HDMI 2160p60 belum dikualifikasi pada layar ini.
- labwc/Wayland tidak dijalankan untuk profil ini.
- Nama service tetap **`pi5-signage.service`** hanya sebagai kontrak kompatibilitas
  CMS/sudo yang sudah terpasang. Nama tersebut **bukan** pemilihan profil Pi5.

## Hasil yang terverifikasi

- Interval final: **61,010 detik wall / 61,044 detik video**, **0 tambahan dropped
  frame**, hardware decoding aktif dan A/V offset sampel mendekati nol.
- Ada tujuh drop startup sebelum interval; bukan klaim zero-drop sejak launch.
- ON/OFF/AUTO, sleep/wake native DPMS, mute/unmute, restart API/browser dan loop
  playlist diuji pada Pi4.
- Reboot nyata diuji: service aktif otomatis, override reset AUTO dan sleep sesuai
  jadwal; setelah itu ON dikembalikan untuk pengamatan operator.
- Operator mengonfirmasi playback sudah smooth setelah integrasi. Uji semalam
  penuh belum dilakukan; jangan menganggap checkpoint ini sertifikasi semua
  layar, konten, HDR, output UHD HDMI atau transisi gapless.

## Batas preview

Capture langsung melalui mpv terbukti memicu audio underrun/dropped frame.
Pada profil direct DRM, CMS menampilkan **keterangan preview tidak tersedia**,
bukan gambar lama yang diklaim live. Kontrol mode/audio/restart tetap tersedia.
Jalur preview Wayland dipertahankan di kode untuk kompatibilitas rollback.

## Isi source snapshot

```text
candidate/                 Payload source yang sama dengan Pi4 terpasang
  signage.py               Supervisor, jadwal, playlist, IPC dan direct DRM
  drm_power.py             Lease DRM/DPMS selama sleep
  drm_splash.py, splash.sh  Splash direct DRM yang terbatas durasinya
  pi5-signage.service      Unit khusus Pi4; nama lama dipertahankan
  config.json              Contoh konfigurasi teknis profil, bukan jadwal/state
  server.py                CMS Pi4 dengan guard preview aman
  public/                  Kode/aset UI saja; tanpa runtime JSON
manifest.json              Hash payload dan guard baseline perangkat
install.py                 Migrasi terjaga + rollback untuk baseline yang cocok
verify_live.py             Uji kontrol pada perangkat (mengubah mode sementara)
probe_final.py             Uji performa pada perangkat
preview-manifest.json      Guard revisi CMS pada deployment yang ada
profile.json               Identitas target Pi4 yang eksplisit
tests/                     Regresi profil dan isolasi target/payload
docs/                      Implementasi, bukti tes, progress dan rollback
```

## Verifikasi lokal

```bash
python -m unittest discover -s tests -v
node --check candidate/public/app.js
node --check candidate/public/operation-ui.js
git diff --check
```

Unit test menjalankan mock untuk batas hardware. Bukti pengujian fisik terpisah
ada di `docs/02-verification.md`; lulus unit test tidak menggantikan tes layar.
`git diff --check` menandai whitespace lama pada beberapa file yang diimpor.
Byte payload sengaja dipertahankan agar sama dengan deployment terverifikasi;
.gitattributes mencegah perubahan line ending otomatis. Cleanup format bukan
bagian checkpoint ini dan perlu regenerasi hash bila dilakukan kemudian.

## Deployment / rollback

**Jangan menjalankan installer Pi5 dari branch lain pada Pi4 ini.** `install.py`
memeriksa model Pi4 dan hash baseline sebelum menulis file atau mengubah service.
Ia sengaja menolak perangkat/model atau source yang tidak cocok, termasuk source
yang sudah dimigrasikan. File `candidate/public/` disimpan sebagai snapshot source
UI; installer migrasi mengasumsikan CMS/UI baseline sudah ada, bukan menyediakan
fresh-install universal. Splash PPM yang sudah dihasilkan di perangkat tidak
ditimpa atau dimasukkan sebagai data runtime ke Git.

Petunjuk operasional dan perintah rollback deployment saat ini:
`docs/03-operations.md`. Jangan mengganti playlist, schedules, audio preferences,
operation mode atau media saat deploy kode.

## Mengambil source yang benar dari GitHub

Untuk **Pi4**:

```bash
git clone --branch capibarra-lite-pi4 --single-branch https://github.com/whsyph/piEdge.git capibarra-lite-pi4
```

Untuk **Pi5**, gunakan folder dan branch berbeda:

```bash
git clone --branch capibarra-lite --single-branch https://github.com/whsyph/piEdge.git capibarra-lite-pi5
```

Perintah tersebut hanya mengambil source, **bukan melakukan instalasi**. Jangan
clone branch default lalu menebak targetnya. Installer Pi4 pada snapshot ini
menjaga model dan baseline source; ia bukan fresh-installer untuk Pi4 kosong.
Installer/fresh-install Pi5 juga belum diuji ulang oleh publikasi Pi4 ini.
Untuk perangkat baru, gunakan paket/installer khusus model yang telah diuji;
jangan melewati guard atau memakai paket board lain agar instalasi terpaksa jalan.

## Pemisahan versi

| Target | Branch | Runtime |
|---|---|---|
| **Pi4** | **`capibarra-lite-pi4`** | **Direct DRM hardware-plane; snapshot ini** |
| Pi5 | `capibarra-lite` | Profil Pi5 terpisah; tidak diubah oleh commit Pi4 |

Riwayat Git mempunyai ancestor bersama, tetapi tree dan payload pada branch ini
hanya profil Pi4. Penggabungan lintas board harus berupa port yang disengaja dan
diuji, bukan merge seluruh tree hardware. Worktree Pi5 yang memiliki perubahan
packaging lokal tidak disentuh.
