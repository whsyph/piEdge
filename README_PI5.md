# piEdge — Raspberry Pi 5 4K signage profile

Profil ini menambahkan player untuk Raspberry Pi 5 tanpa mengubah deployment Raspberry Pi 4 yang lama.

## Target

- Raspberry Pi 5, RAM 1 GB, Raspberry Pi OS Bookworm 64-bit.
- Wayland/labwc.
- Satu atau dua output HDMI sesuai `public/output_mode.json`.
- Playlist lokal diputar berulang selama signage aktif.
- Video 4K60 paling aman dalam HEVC/H.265, 8-bit atau 10-bit, dengan audio AAC/Opus yang kompatibel.

RAM 1 GB cukup untuk backend Python ringan dan mpv karena video tidak dimuat seluruhnya ke RAM. Hindari menjalankan browser desktop berat atau transcoding di Pi.

## Instalasi di Pi

```bash
cd /tmp
# salin/clone repository ke Pi, lalu:
cd piEdge
sudo bash install_pi5.sh
```

Service yang digunakan:

```bash
sudo systemctl enable --now labwc.service
sudo systemctl enable --now cms-signage.service pi5-signage.service
journalctl -u pi5-signage -f
```

Player menggunakan `--hwdec=auto-safe` dan `--vo=dmabuf-wayland`. Profil lama `v4l2m2m` tidak dipakai pada profil Pi 5 ini.

## Mode output

Buat `public/output_mode.json` bila belum ada:

```json
{"mode": "single"}
```

Gunakan `dual` untuk dua layar. Pada mode dual, layar 1 memakai output 0 dan layar 2 output 1. Atur resolusi/posisi window melalui aturan labwc yang sesuai dengan layout fisik layar.

## Uji file video sebelum deploy

```bash
./validate_media.sh video.mp4
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate,pix_fmt \
  -of default=noprint_wrappers=1 video.mp4
```

Untuk signage 12 jam, gunakan file lokal dan playlist yang sudah tervalidasi. Jika video berisi codec atau profil yang tidak didukung hardware, mpv dapat jatuh ke software decode; pantau `journalctl`, suhu, dan dropped frames sebelum produksi.

## Menentukan IP LAN/Wi-Fi di Pi

Belum bisa dipastikan dari dua alamat saja. Setelah login ke Pi, jalankan:

```bash
ip -br addr
ip route get 1.1.1.1
```

Umumnya LAN adalah `eth0`/`end0`, Wi-Fi adalah `wlan0`. IP yang dipilih untuk CMS adalah IP interface yang ingin dipakai mengakses perangkat.

## Keamanan dan konfigurasi CMS

Sejak revisi "cms-hardening", CMS tidak lagi terbuka untuk siapa saja di jaringan.

**Token akses.** Saat pertama kali jalan, server membuat token acak di `/home/pi/museum_signage/.cms_token` (mode `0600`). Baca dengan `cat /home/pi/museum_signage/.cms_token`, lalu masukkan di dialog "Token akses diperlukan" saat membuka UI. Token disimpan di browser (per perangkat). Hapus file itu dan restart `cms-signage` untuk membuat token baru. Akses API dari skrip: `curl -H "Authorization: Bearer <token>" http://IP:8080/api/status`.

**`cms_config.json`** (opsional, di samping `server.py`; semua kunci boleh dihilangkan):

| Kunci | Bawaan | Arti |
|---|---|---|
| `require_auth` | `true` | Wajib token di semua `/api/*` |
| `allowed_origins` | `[]` | Origin dashboard lain yang boleh memanggil API ini lewat browser, mis. `["http://192.168.8.10:8080"]`. Origin halaman sendiri selalu diizinkan |
| `legacy_players` | `false` | `true` hanya untuk pemutar lama layar1/layar2 (playlist.txt, `loadlist`, stop `layar*.service`). Pemutar Pi 5 membaca `playlists.json` sendiri, jadi biarkan `false` |
| `max_upload_mb` | `8192` | Ukuran upload maksimum |
| `min_free_mb` | `1024` | Sisa disk minimum setelah upload |
| `allowed_codecs` | `["hevc"]` | Codec yang boleh diunggah (Pi 5 hanya punya decoder hardware HEVC) |

**Upload.** Hanya `.mp4`, `.mkv`, `.mov`; ekstensi harus cocok dengan isi file; codec dicek dari header container (tanpa ffprobe). File H.264 ditolak dengan petunjuk konversi:

```bash
ffmpeg -i input.mp4 -c:v libx265 -preset medium -crf 20 -tag:v hvc1 -an output.mp4
```

**Berkas data** (`playlists.json`, `schedules.json`, `network_config.json`, `audio_config.json`, ...) tidak lagi disajikan lewat HTTP; hanya lewat API (dengan token). Semuanya ditulis secara atomik, jadi pemutar tidak pernah membaca berkas separuh jadi.

**Hak sudo.** CMS memakai `sudo -n` untuk `systemctl start/stop/restart pi5-signage`, `ip link set`, dan `shutdown`. Pi OS memberi user `pi` sudo tanpa password penuh; untuk membatasinya, salin `cms-signage.sudoers` ke `/etc/sudoers.d/` (periksa dengan `sudo visudo -cf` dulu) dan hapus `/etc/sudoers.d/010_pi-nopasswd` hanya jika kamu yakin tidak membutuhkan sudo penuh.

## Pasang CMS di Pi 5 baru (`install-cms.sh`)

Player (repo `capibarra-lite`) dan CMS (repo ini, branch `claude/cms-hardening`) dipasang terpisah. Urutannya:

1. Di Pi baru, pasang player lebih dulu dengan `sudo python3 install-fresh.py` (lihat `MANUAL-INSTALASI.md` di branch player).
2. Clone repo CMS dan jalankan sebagai user `pi`, bukan root:

```bash
git clone --branch claude/cms-hardening --single-branch https://github.com/whsyph/piEdge.git ~/capibarra-cms
cd ~/capibarra-cms
bash install-cms.sh --allow 192.168.8.0/24
```

`--allow` menentukan siapa yang boleh membuka port 8080 (IP atau CIDR, pisahkan dengan koma). Selain itu port di-drop. Skrip menolak jalan jika CMS sudah ada.

Skrip menyalin CMS ke `/home/pi/museum_signage`, mengarahkan `/etc/pi5-signage.json` ke file CMS (backup dibuat), memasang service `cms-signage` dan `capibarra-firewall`, lalu mengecek bahwa CMS menjawab dan `/api/status` menolak permintaan tanpa token. Token dibuat otomatis di `/home/pi/museum_signage/.cms_token`.

Update kode kemudian, tanpa menyentuh playlist, jadwal, token, atau media:

```bash
cd ~/capibarra-cms && git pull && bash install-cms.sh --update
```
