#!/bin/sh
# Finite direct-DRM splash; never prevents the supervisor starting.
/usr/bin/python3 /opt/pi5-signage/drm_splash.py --config /etc/pi5-signage.json
exit 0
