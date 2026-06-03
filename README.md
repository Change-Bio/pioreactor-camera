# pioreactor-camera

A USB-webcam plugin for [Pioreactor](https://pioreactor.com). Captures JPEGs from `/dev/video0` on a schedule and exposes a small web gallery + a manual "Take photo" button at `https://<your-pioreactor>/camera/`.

## What it does

- **Background job (`camera_capture`)** — a `BackgroundJobContrib` that runs on the leader. Every `minutes_between_captures` it calls `ffmpeg -f v4l2 -i /dev/video0` and writes the JPEG to `image_directory`.
- **Web gallery server** — a stdlib `http.server` listening on `127.0.0.1:<server_port>`, fronted by lighttpd at `/camera/`. Lists captured images and serves them. Has a `POST /api/capture` endpoint the gallery's "Take photo" button calls for an on-demand snap.

## What it does *not* do

- **No support for the Pi CSI camera ribbon.** This is a USB webcam plugin — it talks to v4l2 via `/dev/video0`. If you have a Raspberry Pi camera module, you'd want a different capture backend (libcamera / `rpicam-still`).

## Requirements

- A USB webcam reachable as `/dev/video0` on the leader Pioreactor.
- `ffmpeg` (already installed on stock Pioreactor images).
- lighttpd (installed on stock Pioreactor images) — used to proxy `/camera/` → the local server.

## Installation

From a release zip:

```bash
pio plugins install pioreactor-camera \
  --source https://github.com/Change-Bio/pioreactor-camera/archive/main.zip
```

`pio plugins install` will:

1. `pip install` the wheel into the Pioreactor venv.
2. Merge `additional_config.ini` into `~/.pioreactor/config.ini`.
3. Copy the UI YAML to `~/.pioreactor/plugins/ui/contrib/`.
4. Run `post_install.sh`, which writes `/etc/systemd/system/pioreactor-camera-server.service` and `/etc/lighttpd/conf-enabled/52-camera.conf` and enables the systemd unit. **These writes need root** — the `pioreactor` user has NOPASSWD sudo for those paths on standard Pioreactor images. If your environment doesn't, you'll need to drop those files manually.

After install: `sudo systemctl status pioreactor-camera-server` and visit `/camera/` in the UI.

## Configuration

Set in `[camera_capture.config]` in `~/.pioreactor/config.ini`:

| Key | Default | Meaning |
|---|---|---|
| `image_directory` | `/home/pioreactor/camera_images` | Where captured JPEGs are written |
| `minutes_between_captures` | `5.0` | Background-job capture interval |
| `resolution_width` | `640` | ffmpeg `-video_size` width |
| `resolution_height` | `480` | ffmpeg `-video_size` height |
| `server_port` | `8190` | Local port the gallery server binds to (must match the proxy in `52-camera.conf`) |
| `upload_to_gcs` | `0` | If `1`, each captured image is uploaded to GCS |
| `gcs_bucket` | (empty) | Target bucket, e.g. `gs://my-bucket/snaps` — `YYYY/MM/DD/` is appended automatically |
| `gcs_project` | (empty) | Optional GCP project for the `--project` flag passed to gcloud |

The capture interval, resolution, "upload to GCS", and "capture now" can also be changed live through the Pioreactor UI — they're exposed as published settings on the `camera_capture` job.

### GCS upload

Optional. When `upload_to_gcs=1` and `gcs_bucket` is set, every successful capture is uploaded by shelling out to `gcloud storage cp`. Requirements:

- `gcloud` must be on PATH for the `pioreactor` user.
- `gcloud` must be authenticated — either `gcloud auth login` interactively, or `gcloud auth activate-service-account` with a JSON key.
- The destination object is `<gcs_bucket>/<YYYY>/<MM>/<DD>/<filename>`. Upload failures are logged and skipped; captures themselves are not aborted by a failed upload.

If you'd rather batch uploads out-of-process (e.g. an `rclone` cron sweeping `image_directory`), leave `upload_to_gcs=0` and run your own sidecar.

## Architecture

```
┌──────────────────────────────┐         ┌────────────────────┐
│  camera_capture (pio job)    │         │  user's browser    │
│   - RepeatedTimer fires      │         │     │ visits        │
│   - ffmpeg → image_directory │         │     ▼ /camera/      │
└──────────────────────────────┘         │ lighttpd :80        │
                                         │     │ proxy         │
                                         │     ▼ /             │
                                         │ camera_server :8190 │
                                         │   - lists image_dir │
                                         │   - POST /api/capt. │
                                         │     → ffmpeg snap   │
                                         └────────────────────┘
```

The two paths to a capture (scheduled job vs. "Take photo" button) both end in the same `capture_image()` function in `pioreactor_camera.camera_capture`.

## Files

```
pioreactor_camera/
├── camera_capture.py        # BackgroundJobContrib + capture_image()
├── camera_server.py         # http.server-based gallery + /api/capture
├── additional_config.ini    # merged into ~/.pioreactor/config.ini on install
├── post_install.sh          # writes systemd unit + lighttpd conf
├── pre_uninstall.sh         # tears them down
├── static/                  # gallery JS / CSS / index.html
└── ui/contrib/jobs/
    └── camera_capture.yaml  # exposes the job in the Pioreactor UI
```

## Troubleshooting

- **`/camera/` button "Take photo" returns "Capture failed: network error"**
  Check `journalctl -u pioreactor-camera-server`. Most failures here are ImportErrors or ffmpeg not finding `/dev/video0`.
- **No images appearing in the gallery**
  Verify the `camera_capture` job is running (UI → unit settings, or `pio kill --list-jobs`). The gallery only shows what's on disk in `image_directory`.
- **`ffmpeg: /dev/video0: No such file or directory`**
  USB camera not plugged in / `pioreactor` user not in `video` group. `ls -l /dev/video0` and `groups pioreactor`.
- **lighttpd 502 on `/camera/`**
  Server isn't listening on `server_port`. `sudo systemctl restart pioreactor-camera-server`.

## License

MIT.
