@echo off
echo Mengirim file ke Raspberry Pi (192.168.88.46)...
echo Anda akan diminta memasukkan password 'pi' beberapa kali.
echo.

scp server.py pi@192.168.88.46:/home/pi/museum_signage/
scp public/index.html public/app.js public/app.css public/playlists.json public/schedules.json public/network_config.json pi@192.168.88.46:/home/pi/museum_signage/public/

echo.
echo Pengiriman selesai!
echo Merestart service di Raspberry Pi...
ssh pi@192.168.88.46 "sudo systemctl restart layar-gabungan.service"

echo.
echo Deploy berhasil! Silakan refresh browser Anda.
pause
