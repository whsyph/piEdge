# Manual instalasi perangkat baru — caPIbarra Pi5

Status: fresh installer v1 sudah lolos test lokal; belum merupakan bukti penerimaan hardware baru. Manual ini hanya untuk Raspberry Pi 5 Model B baru/kosong. Jangan gunakan pada Pi yang sudah mempunyai CMS, media, atau service signage.

## 1. Persiapan fisik dan image

1. Gunakan Raspberry Pi 5 Model B, catu daya yang memadai, pendinginan aktif, serta layar/kabel yang sesuai target konten. HDMI-A-1 adalah HDMI0 (port dekat USB-C).
2. Dengan Raspberry Pi Imager, flash Raspberry Pi OS Lite Bookworm 64-bit.
3. Pada Imager, buat user bernama `pi` dengan UID 1000, aktifkan SSH bila diperlukan, dan siapkan koneksi jaringan. Installer tidak membuat akun atau mengelola password.
4. Boot perangkat, login sebagai `pi`, lalu pastikan waktu benar:

```bash
sudo timedatectl set-timezone Asia/Jakarta
timedatectl status
cat /proc/device-tree/model
getent passwd pi
uname -m
dpkg --print-architecture
```

Hasil yang diperlukan: model Pi 5, user `pi` UID 1000, `aarch64`, dan `arm64`.

## 2. Ambil source Pi5 yang tepat

Jalankan sebagai user biasa (`pi`), bukan root:

```bash
sudo apt-get update
sudo apt-get install -y git
cd ~
git clone --branch capibarra-lite --single-branch https://github.com/whsyph/piEdge.git capibarra-lite-pi5
cd ~/capibarra-lite-pi5
git rev-parse HEAD
```

Jangan memakai branch `capibarra-lite-pi4` pada Pi5. Catat SHA yang tampil agar instalasi dapat ditelusuri.

## 3. Preflight tanpa perubahan

```bash
python3 install-fresh.py --check
```

Preflight harus menampilkan `Fresh-install preflight passed; no changes made.` Ia menolak OS/model yang tidak cocok, Pi yang sudah pernah dipasang, CMS/service display yang aktif, dan proses display yang berjalan. Jangan bypass guard tersebut.

Jika preflight menolak karena perangkat memang sudah memiliki deployment, hentikan di sini. Jalur ini bukan migrasi atau upgrade in-place.

## 4. Instalasi fresh

```bash
sudo python3 install-fresh.py
```

Installer memasang dependensi dan membuat:

```text
/opt/pi5-signage
/etc/pi5-signage.json
/var/lib/pi5-signage/videos
/etc/systemd/system/pi5-signage.service
/etc/systemd/system/labwc.service
/etc/systemd/system/seatd.service.d/capibarra.conf
```

Installer tidak menjalankan atau enable pemutar. Reboot setelah langkah ini tidak akan memulai playback.

## 5. Tambahkan media dan periksa konfigurasi

Salin media dari komputer operator (contoh dari komputer lain):

```bash
scp /path/ke/video.mp4 pi@ALAMAT_PI:/var/lib/pi5-signage/videos/
```

Atau dari Pi sendiri:

```bash
cp /path/ke/video.mp4 /var/lib/pi5-signage/videos/
chmod 644 /var/lib/pi5-signage/videos/video.mp4
ls -lah /var/lib/pi5-signage/videos
sudo cat /etc/pi5-signage.json
```

Untuk target 4K60, gunakan HEVC/H.265 3840×2160 60 fps yang sudah diuji. Jangan menganggap codec, layar, kabel, atau mode lain akan setara tanpa uji fisik.

## 6. Uji terkontrol

```bash
sudo systemctl start pi5-signage.service
sudo systemctl status pi5-signage.service --no-pager
journalctl -u pi5-signage.service -b --no-pager
```

Periksa pada layar bahwa output tampil di HDMI0/`HDMI-A-1`, audio sesuai konfigurasi, loop berjalan, dan log tidak menunjukkan kegagalan decoder/DRM/Wayland. Untuk diagnostik media bila diperlukan:

```bash
sudo apt-get install -y ffmpeg
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,avg_frame_rate -of default=noprint_wrappers=1 /var/lib/pi5-signage/videos/video.mp4
```

Lakukan soak test dengan media produksi sebelum perangkat dipasang tanpa pengawasan.

## 7. Autostart setelah penerimaan hardware

Hanya setelah langkah 6 diterima:

```bash
sudo systemctl enable pi5-signage.service
sudo reboot
```

Setelah boot, verifikasi lagi:

```bash
systemctl is-enabled pi5-signage.service
systemctl status pi5-signage.service --no-pager
journalctl -u pi5-signage.service -b --no-pager
```

## 8. Menghentikan dan batas pemulihan

Untuk menghentikan playback atau mencegah autostart:

```bash
sudo systemctl disable --now pi5-signage.service
```

Fresh installer sengaja menolak instalasi ulang bila direktori/konfigurasi/service target sudah ada. Jangan hapus data atau unit secara membabi buta untuk memaksanya berjalan. Ambil backup `/etc/pi5-signage.json` dan media, catat error, lalu lakukan pemulihan terencana.
