# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

import click
from pioreactor.background_jobs.base import BackgroundJobContrib
from pioreactor.config import config
from pioreactor.utils.timing import RepeatedTimer
from pioreactor.whoami import get_unit_name
from pioreactor.whoami import UNIVERSAL_EXPERIMENT

__plugin_summary__ = "Captures images from a USB webcam at configurable intervals"
__plugin_version__ = "0.1.0"
__plugin_name__ = "Camera Capture"
__plugin_author__ = "Noah Sprent"
__plugin_homepage__ = "https://github.com/Change-Bio/pioreactor-camera"


def __dir__():
    return ["click_camera_capture"]


IMAGE_DIR = Path(config.get("camera_capture.config", "image_directory", fallback="/home/pioreactor/camera_images"))


def capture_image(
    image_dir: Path,
    resolution_width: int = 640,
    resolution_height: int = 480,
) -> str | None:
    """Capture a single image from the webcam. Returns the filename or None on failure."""
    image_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"webcam_snap_{timestamp}.jpg"
    filepath = image_dir / filename

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-f", "v4l2",
                "-input_format", "mjpeg",
                "-video_size", f"{resolution_width}x{resolution_height}",
                "-i", "/dev/video0",
                "-frames:v", "1",
                "-q:v", "2",
                "-f", "image2",
                "-y",
                str(filepath),
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        return filename
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def upload_to_gcs(filepath: Path, bucket: str, project: str) -> bool:
    """Upload an image to Google Cloud Storage."""
    date_path = datetime.now().strftime("%Y/%m/%d")
    upload_path = f"{bucket}/{date_path}/"
    try:
        subprocess.run(
            [
                "/home/pioreactor/google-cloud-sdk/bin/gcloud",
                "storage", "cp",
                str(filepath),
                upload_path,
                f"--project={project}",
            ],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


class CameraCapture(BackgroundJobContrib):

    job_name = "camera_capture"
    published_settings = {
        "minutes_between_captures": {"datatype": "float", "settable": True, "unit": "min"},
        "resolution_width": {"datatype": "int", "settable": True, "unit": "px"},
        "resolution_height": {"datatype": "int", "settable": True, "unit": "px"},
        "upload_to_gcs": {"datatype": "boolean", "settable": True},
        "capture_now": {"datatype": "boolean", "settable": True},
    }

    def __init__(self, unit: str, experiment: str, **kwargs):
        self.minutes_between_captures = float(
            config.get("camera_capture.config", "minutes_between_captures", fallback="5.0")
        )
        self.resolution_width = int(
            config.get("camera_capture.config", "resolution_width", fallback="640")
        )
        self.resolution_height = int(
            config.get("camera_capture.config", "resolution_height", fallback="480")
        )
        self.upload_to_gcs = config.getboolean(
            "camera_capture.config", "upload_to_gcs", fallback=True
        )
        self.gcs_bucket = config.get(
            "camera_capture.config", "gcs_bucket",
            fallback="gs://pioreactor-webcam-snaps-1768947561/webcam_snaps"
        )
        self.gcs_project = config.get(
            "camera_capture.config", "gcs_project", fallback="changebio-tech"
        )
        self.image_dir = IMAGE_DIR

        self._capture_timer = None

        super().__init__(unit=unit, experiment=experiment, plugin_name="pioreactor_camera")

    def on_init_to_ready(self):
        self._start_capture_timer()
        self.logger.info(
            f"Camera capture started: interval={self.minutes_between_captures}min, "
            f"resolution={self.resolution_width}x{self.resolution_height}, "
            f"upload_to_gcs={self.upload_to_gcs}"
        )

    def on_ready_to_sleeping(self):
        if self._capture_timer:
            self._capture_timer.cancel()

    def on_sleeping_to_ready(self):
        self._start_capture_timer()

    def on_disconnected(self):
        if self._capture_timer:
            self._capture_timer.cancel()

    def _start_capture_timer(self):
        if self._capture_timer:
            self._capture_timer.cancel()
        self._capture_timer = RepeatedTimer(
            self.minutes_between_captures * 60,
            self._do_capture,
            job_name=self.job_name,
            run_immediately=True,
        ).start()

    def _do_capture(self):
        filename = capture_image(
            self.image_dir,
            self.resolution_width,
            self.resolution_height,
        )
        if filename:
            self.logger.debug(f"Captured {filename}")
            if self.upload_to_gcs:
                filepath = self.image_dir / filename
                if upload_to_gcs(filepath, self.gcs_bucket, self.gcs_project):
                    self.logger.debug(f"Uploaded {filename} to GCS")
                else:
                    self.logger.warning(f"Failed to upload {filename} to GCS")
        else:
            self.logger.warning("Image capture failed")

    def set_minutes_between_captures(self, value):
        self.minutes_between_captures = float(value)
        if self.state == self.READY:
            self._start_capture_timer()

    def set_resolution_width(self, value):
        self.resolution_width = int(value)

    def set_resolution_height(self, value):
        self.resolution_height = int(value)

    def set_upload_to_gcs(self, value):
        self.upload_to_gcs = bool(int(value))

    @property
    def capture_now(self):
        return False

    @capture_now.setter
    def capture_now(self, value):
        if bool(int(value)):
            self.logger.info("Manual capture triggered")
            self._do_capture()


@click.command(name="camera_capture", help=__plugin_summary__)
def click_camera_capture():
    unit = get_unit_name()
    experiment = UNIVERSAL_EXPERIMENT
    job = CameraCapture(unit=unit, experiment=experiment)
    job.block_until_disconnected()
