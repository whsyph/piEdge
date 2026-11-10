# Pi 5 signage 4K60

Pemutar signage satu layar untuk Raspberry Pi 5 1 GB. Menggunakan Raspberry Pi OS Lite 64-bit, labwc/Wayland dengan mpv hardware decode, dan Python standard library sebagai pengawas jadwal. Tidak memakai browser. Video disimpan lokal dan diputar berulang selama 24 jam.

Ini proyek baru yang mengambil kebutuhan dasar dari [piEdge](https://github.com/whsyph/piEdge), bukan migrasi CMS dua layar beserta API-nya. Pada Pi 5, jalur yang ditargetkan adalah video **HEVC/H.265 3840×2160 60 fps**; codec lain tidak dijanjikan lancar pada 4K60. Raspberry Pi menyatakan Pi 5 mempunyai decoder HEVC 4K60 dan output HDMI 4K60. Kemampuan aktual tetap harus diuji pada layar, kabel, file, dan versi OS yang digunakan.

## Konfigurasi bawaan

- Aktif 24 jam penuh (`"always_on": true`). Untuk membatasi jam tayang, hapus `always_on` (atau set `false`) dan atur `start`/`end` menurut waktu lokal Pi (`Asia/Jakarta` bila dikonfigurasi demikian).
- Satu video di playlist diulang oleh mpv sendiri (`--loop-file=inf`) tanpa jeda relaunch; perubahan playlist tetap dideteksi tiap ±5 detik.
- Satu layar di `HDMI-A-1` (port HDMI0, port dekat USB-C daya).
- Audio dimatikan; bisa diaktifkan lewat `config.json`.
- Playlist CMS yang ditugaskan ke `screen1` dibaca dari `public/playlists.json`; perubahan playlist diterapkan pada putaran video berikutnya.
- Jika mpv keluar atau gagal, pengawas mencoba file berikutnya dengan jeda. `systemd` menghidupkan kembali pengawas setelah crash/reboot.
- Saat boot atau restart manual service, splash screen caPIbarra tampil selama sekitar 5 detik sebelum mpv signage mengambil alih layar. Restart otomatis akibat crash dalam 2 menit terakhir melewati splash agar layar tidak berkedip berulang.
- Sebelum splash, service menunggu soket Wayland (maks. 60 detik); `labwc.service` menunggu layar HDMI terhubung dan mencatat pesan penantian ke journal tiap ±30 detik.

## Jadwal tayang (jendela)

Jam tayang ditulis sebagai **jendela**, bukan pasangan wake/sleep:

```json
{
  "timezone": "Asia/Jakarta",
  "windows": [
    {"days": ["Mon", "Tue", "Wed", "Thu", "Fri"], "start": "08:00", "end": "01:00"},
    {"days": ["Sat"], "start": "10:00", "end": "22:00"}
  ]
}
```

- `days` adalah **hari mulai** jendela. Jika `end` lebih kecil dari `start`, jendela berlanjut ke hari berikutnya (contoh: Jumat 08:00 → Sabtu 01:00 adalah satu jendela milik Jumat). `end: "24:00"` berarti sampai tengah malam; `00:00`–`24:00` berarti sehari penuh. `start` sama dengan `end` ditolak.
- Di luar semua jendela, layar **mati**. Hari yang tidak punya jendela mati seharian (log mencatat peringatan sekali). Untuk selalu menyala, pakai `"always_on": true`, yang tidak boleh digabung dengan `windows`.
- `timezone` adalah nama IANA; semua hari dan jam dihitung di zona itu. Jika dikosongkan, dipakai zona waktu Pi. Paket `tzdata` harus ada (bawaan Raspberry Pi OS).
- Sumber jadwal, urut prioritas: (1) `windows` di `schedules_file` CMS, (2) `windows` di `/etc/pi5-signage.json`, (3) aturan lama (`start`/`end`/`always_on` dan event wake/sleep CMS). Jika `schedules.json` berisi `windows` yang rusak atau tidak terbaca, jadwal valid terakhir tetap dipakai (bukan "izinkan"); bila belum ada, jatuh ke sumber berikutnya dan kesalahan dicatat di journal.
- Mode manual `on`/`off` (`operation_mode.json`) tetap menimpa semuanya.

## Persiapan Pi

Gunakan Raspberry Pi OS Lite **64-bit** yang masih didukung, HDMI 2.0 dan kabel yang mampu 4K60, catu daya resmi 27 W atau yang setara, serta pendinginan aktif untuk operasi 24 jam sehari. Atur zona waktu dan jam otomatis:

```bash
sudo timedatectl set-timezone Asia/Jakarta
timedatectl status
```

Jangan menjalankan service piEdge lama yang memakai layar yang sama secara bersamaan. Cek dulu:

```bash
systemctl list-units --type=service 'layar*' 'labwc*' 'cms-signage*'
```

Jika service pemutar lama aktif atau masih enabled, nonaktifkan dulu dengan `sudo systemctl disable --now <nama-service>`. Installer akan menolak pemasangan bila salah satu dari `layar1`, `layar2`, atau `layar-gabungan` masih aktif/enabled; ia tidak mengubah service lama secara otomatis.

## Fresh installation v1 (player only, local candidate)

Requires Python 3, Raspberry Pi OS **Bookworm 64-bit**, Pi 5 Model B, systemd,
and an existing `pi` account with UID 1000 (configure in Raspberry Pi Imager).
No CMS or password provisioning. From this reviewed local checkout:

```bash
python3 install-fresh.py --check
sudo python3 install-fresh.py
```

Preflight is read-only and rejects existing deployments/config/media and competing
display owners. Installation uses apt and creates `/opt/pi5-signage`,
`/etc/pi5-signage.json`, and `/var/lib/pi5-signage/videos`. The fresh config scans
local media without CMS playlist/schedule files. Playback is neither started nor
enabled, including after reboot. After adding readable media, explicitly run
`sudo systemctl start pi5-signage.service`; enable it separately only if wanted.
The existing renderer and legacy installer remain separate and unchanged.

`bootstrap.py` is a common **unprivileged** Python 3/git dispatcher. It fetches the
Pi 5 `capibarra-lite` or Pi 4 `capibarra-lite-pi4` branch into a new directory, shows
the commit, runs its fresh preflight, then uses interactive sudo only for install.
The downloadable bootstrap URL is **unavailable until publication**; both branches
must publish `install-fresh.py` first. After publication, local invocation is
`python3 bootstrap.py --repo-url https://github.com/whsyph/piEdge --check`
(omit `--check` to install; use a new `--dir` each time; tambahkan `--commit <SHA 40 hex>` untuk mengunci ke commit yang sudah kamu tinjau, bukan ujung branch). Bootstrap check downloads
a checkout but does not install. Review/trust the selected source before sudo.

No hardware installation/boot/playback acceptance is claimed. A failed install
can leave packages/files; it refuses reruns rather than overwriting that state.
Resolve failures manually. The older notes below describe the legacy flow, not
the fresh installer.

## Instalasi (legacy release flow)

`install.sh` hanya berjalan dari **paket rilis** (butuh `release.json` dan checksum), bukan dari checkout git mentah. Bangun paketnya di mesin dengan git, salin ke Pi, ekstrak, lalu jalankan dari folder hasil ekstrak:

```bash
python3 scripts/build-release.py pi5          # menghasilkan dist/capibarra-lite-pi5-<versi>.tar.gz
# di Pi, setelah menyalin dan mengekstrak tarball:
cd capibarra-lite-pi5-<versi>
sudo bash install.sh
```

Installer menyalin aplikasi ke `/opt/pi5-signage`, konfigurasi awal ke `/etc/pi5-signage.json`, membuat user sistem `pi5-signage`, dan membuat folder `/var/lib/pi5-signage/videos`. Instalasi pertama mengaktifkan service tetapi **tidak langsung memulai** hingga media sudah dimasukkan.

Contoh memasukkan media dan menjalankan:

```bash
sudo cp Odyssey4K60p.mp4 /var/lib/pi5-signage/videos/
sudo chmod 644 /var/lib/pi5-signage/videos/Odyssey4K60p.mp4
sudo systemctl start pi5-signage.service
sudo systemctl status pi5-signage.service
journalctl -u pi5-signage.service -f
```

Ubah port/audio di `/etc/pi5-signage.json`, lalu `sudo systemctl restart pi5-signage.service`. Dengan konfigurasi bawaan 24 jam, bila boot terjadi dan media tersedia, pengawas langsung memulai video.

## Pemeriksaan 4K60

```bash
cat /proc/device-tree/model
ip -br -4 addr
for c in /sys/class/drm/card*-HDMI-A-*/status; do echo "$c: $(cat "$c")"; done
kmsprint -m
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,avg_frame_rate -of default=noprint_wrappers=1 /var/lib/pi5-signage/videos/Odyssey4K60p.mp4
journalctl -u pi5-signage.service -b --no-pager
```

`ffprobe` tersedia dari paket `ffmpeg` bila ingin dipasang untuk diagnostik. Pastikan layar menegosiasikan 3840×2160 pada 60 Hz, file berisi HEVC 60 fps, dan log mpv tidak menunjukkan kegagalan decoder/DRM. Lakukan uji tayang penuh minimal 12 jam dengan file produksi sebelum dipakai tanpa pengawasan. Service memakai `tty1`; login lokal masih dapat dilakukan pada terminal virtual lain atau lewat SSH.

## Jaringan perangkat yang disebutkan

API piEdge pada perangkat mengembalikan `eth0 = 192.168.88.145` dan `wlan0 = 192.168.88.132` pada saat diperiksa. DHCP bisa mengubahnya. Akses SSH belum tersedia dari lingkungan pengembangan ini, jadi proyek ini belum dipasang ke Pi.

## Referensi

- [Spesifikasi decoder dan output Pi 5](https://www.raspberrypi.com/documentation/computers/processors.html)
- [Memutar audio dan video di Raspberry Pi OS Lite](https://www.raspberrypi.com/documentation/computers/os.html#play-audio-and-video-on-raspberry-pi-os-lite)
- [Dokumentasi mpv (opsi `--vo`, `--hwdec`, IPC)](https://mpv.io/manual/stable/)

## Renderer alternatif (`gpu-copy`)

Default pemutar memakai `vo=dmabuf-wayland` + `hwdec=drm`. Pada sebagian panel (terlihat di pi-4 dengan TV "Beyond TV") gambar HDMI beku meski mpv berjalan normal. Untuk perangkat seperti itu pilih renderer lain di `/etc/pi5-signage.json`:

```json
"renderer": "gpu-copy"
```

Ini tetap memakai decode hardware HEVC (`hwdec=drm-copy`), tetapi frame ditampilkan lewat GPU (`vo=gpu`, `--gpu-context=wayland`). Beban CPU sedikit lebih tinggi (±14% untuk 1080p24). 4K60 belum diverifikasi dengan renderer ini. Nilai tidak dikenal ditolak saat start, dan tanpa kunci `renderer` perilaku default tidak berubah.

## Menyesuaikan video dengan layar (`fit`)

Jika rasio layar berbeda dari rasio video (misalnya layar 1920×1200 16:10 dengan video 1920×1080 16:9), pilih perilakunya di `/etc/pi5-signage.json`:

```json
"fit": "cover"
```

| Nilai | Hasil | Catatan |
|---|---|---|
| `contain` (default) | Seluruh gambar terlihat, ada bidang hitam di tepi | Perilaku lama, tidak berubah |
| `cover` | Layar terisi penuh, proporsi terjaga | Bagian yang melebihi layar terpotong (16:9 → 16:10 memotong ±10% lebar) |
| `stretch` | Layar terisi penuh persis | Gambar tampak melar bila rasio berbeda |

Nilai lain ditolak saat player start. Ubah file lalu `sudo systemctl restart pi5-signage`.
