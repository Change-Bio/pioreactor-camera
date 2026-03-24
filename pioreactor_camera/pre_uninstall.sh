#!/bin/bash
set -euo pipefail

# Stop and disable camera server
systemctl stop pioreactor-camera-server.service 2>/dev/null || true
systemctl disable pioreactor-camera-server.service 2>/dev/null || true
rm -f /etc/systemd/system/pioreactor-camera-server.service
systemctl daemon-reload

# Remove lighttpd config
rm -f /etc/lighttpd/conf-enabled/52-camera.conf
systemctl reload lighttpd 2>/dev/null || true

echo "Camera plugin uninstalled"
