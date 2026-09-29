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
