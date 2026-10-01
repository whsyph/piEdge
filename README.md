# Pi 5 signage 4K60

Pemutar signage satu layar untuk Raspberry Pi 5 1 GB. Menggunakan Raspberry Pi OS Lite 64-bit, labwc/Wayland dengan mpv hardware decode, dan Python standard library sebagai pengawas jadwal. Tidak memakai browser. Video disimpan lokal dan diputar berulang selama 24 jam.

Ini proyek baru yang mengambil kebutuhan dasar dari [piEdge](https://github.com/whsyph/piEdge), bukan migrasi CMS dua layar beserta API-nya. Pada Pi 5, jalur yang ditargetkan adalah video **HEVC/H.265 3840×2160 60 fps**; codec lain tidak dijanjikan lancar pada 4K60. Raspberry Pi menyatakan Pi 5 mempunyai decoder HEVC 4K60 dan output HDMI 4K60. Kemampuan aktual tetap harus diuji pada layar, kabel, file, dan versi OS yang digunakan.

## Konfigurasi bawaan

- Aktif 24 jam, dari **00:00–23:59** menurut waktu lokal Pi (`Asia/Jakarta` bila dikonfigurasi demikian).
- Satu layar di `HDMI-A-1` (port HDMI0, port dekat USB-C daya).
- Audio dimatikan; bisa diaktifkan lewat `config.json`.
- Playlist CMS yang ditugaskan ke `screen1` dibaca dari `public/playlists.json`; perubahan playlist diterapkan pada putaran video berikutnya.
- Jika mpv keluar atau gagal, pengawas mencoba file berikutnya dengan jeda. `systemd` menghidupkan kembali pengawas setelah crash/reboot.
- Saat boot atau restart service, splash screen caPIbarra tampil selama sekitar 5 detik sebelum mpv signage mengambil alih layar.

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

## Instalasi

Salin proyek ini ke Pi, lalu dari folder proyek:

```bash
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

`ffprobe` tersedia dari paket `ffmpeg` bila ingin dipasang untuk diagnostik. Pastikan layar menegosiasikan 3840×2160 pada 60 Hz, file berisi HEVC 60 fps, dan log VLC tidak menunjukkan kegagalan decoder/DRM. Lakukan uji tayang penuh minimal 12 jam dengan file produksi sebelum dipakai tanpa pengawasan. Service memakai `tty1`; login lokal masih dapat dilakukan pada terminal virtual lain atau lewat SSH.

## Jaringan perangkat yang disebutkan

API piEdge pada perangkat mengembalikan `eth0 = 192.168.88.145` dan `wlan0 = 192.168.88.132` pada saat diperiksa. DHCP bisa mengubahnya. Akses SSH belum tersedia dari lingkungan pengembangan ini, jadi proyek ini belum dipasang ke Pi.

## Referensi

- [Spesifikasi decoder dan output Pi 5](https://www.raspberrypi.com/documentation/computers/processors.html)
- [VLC pada Raspberry Pi OS Lite, termasuk opsi output DRM](https://www.raspberrypi.com/documentation/computers/os.html#play-audio-and-video-on-raspberry-pi-os-lite)
