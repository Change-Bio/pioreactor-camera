#!/bin/bash
set -euo pipefail

# Create image directory
mkdir -p /home/pioreactor/camera_images
chown pioreactor:www-data /home/pioreactor/camera_images
chmod 775 /home/pioreactor/camera_images

# Install camera server systemd service
cat > /etc/systemd/system/pioreactor-camera-server.service << 'EOF'
[Unit]
Description=Pioreactor Camera Gallery Server
After=network.target

[Service]
Type=simple
User=pioreactor
Group=www-data
ExecStart=/opt/pioreactor/venv/bin/python -m pioreactor_camera.camera_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pioreactor-camera-server.service
systemctl restart pioreactor-camera-server.service

# Add lighttpd proxy config for /camera
cat > /etc/lighttpd/conf-enabled/52-camera.conf << 'LCONF'
server.modules += ("mod_proxy")

$HTTP["url"] =~ "^/camera($|/)" {
  proxy.server = ("" => (("host" => "127.0.0.1", "port" => 8190)))
  proxy.header = ("map-urlpath" => ("/camera" => ""))
}
LCONF

# Reload lighttpd
systemctl reload lighttpd || systemctl restart lighttpd

echo "Camera plugin installed successfully"
echo "Gallery available at http://$(hostname).local/camera"
