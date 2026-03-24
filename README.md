# Pioreactor Camera Plugin

Captures images from a USB webcam at configurable intervals and provides a web gallery for viewing them.

## Features

- Background job for periodic image capture (controllable via Pioreactor UI)
- Configurable capture interval, resolution, and GCS upload
- Web gallery at port 8190 (proxied to `/camera` via lighttpd)
- Browse images chronologically with timestamps
- Take on-demand photos from the web interface

## Installation

```bash
pio plugins install pioreactor-camera --source /path/to/pioreactor-camera
```
