# Manual instalasi perangkat baru — caPIbarra Pi4

Status: fresh installer v1 lolos test lokal, tetapi belum merupakan penerimaan hardware baru. Manual ini hanya untuk Raspberry Pi 4 Model B baru/kosong. Jangan gunakan pada Pi yang sudah mempunyai CMS, media, atau service signage.

## 1. Persiapan fisik dan image

1. Gunakan Raspberry Pi 4 Model B, layar/kabel HDMI, pendinginan, dan catu daya yang memadai.
2. Dengan Raspberry Pi Imager, flash Raspberry Pi OS Lite Bookworm 64-bit.
3. Pada Imager, buat user `pi` dengan UID 1000, aktifkan SSH bila diperlukan, dan siapkan jaringan. Installer tidak mengelola password.
4. Boot perangkat dan login sebagai `pi`, lalu periksa:

```bash
sudo timedatectl set-timezone Asia/Jakarta
timedatectl status
cat /proc/device-tree/model
getent passwd pi
uname -m
dpkg --print-architecture
```

Hasil yang diperlukan: Raspberry Pi 4 Model B, user `pi` UID 1000, `aarch64`, dan `arm64`.

## 2. Ambil source Pi4 yang tepat

Jalankan sebagai user biasa (`pi`), bukan root:

```bash
sudo apt-get update
sudo apt-get install -y git
cd ~
git clone --branch capibarra-lite-pi4 --single-branch https://github.com/whsyph/piEdge.git capibarra-lite-pi4
cd ~/capibarra-lite-pi4
git rev-parse HEAD
```

Jangan gunakan branch `capibarra-lite` pada Pi4. Catat SHA yang tampil agar instalasi dapat ditelusuri.

## 3. Preflight tanpa perubahan

```bash
python3 install-fresh.py --check
```

Preflight harus menampilkan `Fresh-install preflight passed; no changes made.` Ia menolak model/OS yang tidak cocok, deployment lama, CMS/service display aktif, proses display berjalan, serta payload yang hash-nya tidak cocok. Jangan bypass guard tersebut.

Jika preflight menolak karena perangkat sudah memiliki deployment, hentikan. Jalur ini bukan migrasi atau upgrade in-place.

## 4. Instalasi fresh

```bash
sudo python3 install-fresh.py
```

Installer memasang dependensi, membuat player direct DRM, dan membuat:

```text
/opt/pi5-signage
/etc/pi5-signage.json
/var/lib/pi5-signage/videos
/etc/systemd/system/pi5-signage.service
```

Nama service `pi5-signage.service` adalah kontrak kompatibilitas historis; installer tetap menolak Pi selain Pi4. Ia tidak menjalankan atau enable pemutar, sehingga reboot setelah langkah ini tidak memulai playback.

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

Konfigurasi fresh saat ini memakai direct DRM di `card1`, konektor `HDMI-A-1`, dan mode `1920x1080@60`. Kontrak media Pi4 yang sudah ada adalah HEVC Main10; konten/konektor/card lain tidak boleh dianggap kompatibel tanpa uji fisik.

## 6. Uji terkontrol

```bash
sudo systemctl start pi5-signage.service
sudo systemctl status pi5-signage.service --no-pager
journalctl -u pi5-signage.service -b --no-pager
```

Periksa layar secara fisik: output pada konektor yang benar, mode 1080p60, audio sesuai konfigurasi, loop stabil, serta log tanpa kegagalan DRM/decoder. Untuk diagnostik media:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,width,height,avg_frame_rate -of default=noprint_wrappers=1 /var/lib/pi5-signage/videos/video.mp4
```

Lakukan soak test dengan media produksi sebelum perangkat dipasang tanpa pengawasan.

## 7. Autostart setelah penerimaan hardware

Hanya sesudah langkah 6 diterima:

```bash
sudo systemctl enable pi5-signage.service
sudo reboot
```

Sesudah boot, verifikasi lagi:

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

Fresh installer sengaja menolak instalasi ulang bila path target sudah ada. Jangan menghapus data/service untuk memaksakannya berjalan. Ambil backup `/etc/pi5-signage.json` dan media, catat error, lalu lakukan pemulihan terencana.
