@echo off
echo Mengirim file ke Raspberry Pi (100.67.29.36)...
echo Anda akan diminta memasukkan password 'pi' beberapa kali.
echo.

scp server.py pi@100.67.29.36:/home/pi/museum_signage/
scp public/index.html public/app.js public/app.css public/playlists.json public/schedules.json public/network_config.json pi@100.67.29.36:/home/pi/museum_signage/public/

echo.
echo Pengiriman selesai!
echo Merestart service di Raspberry Pi...
ssh pi@100.67.29.36 "echo pi | sudo -S systemctl restart cms-signage.service && echo pi | sudo -S systemctl restart layar-gabungan.service"

echo.
echo Deploy berhasil! Silakan refresh browser Anda.
pause
