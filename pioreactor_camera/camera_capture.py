# -*- coding: utf-8 -*-
from __future__ import annotations

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
__plugin_version__ = "0.1.1"
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


class CameraCapture(BackgroundJobContrib):

    job_name = "camera_capture"
    published_settings = {
        "minutes_between_captures": {"datatype": "float", "settable": True, "unit": "min"},
        "resolution_width": {"datatype": "int", "settable": True, "unit": "px"},
        "resolution_height": {"datatype": "int", "settable": True, "unit": "px"},
        "capture_now": {"datatype": "boolean", "settable": True},
    }

    def __init__(self, unit: str, experiment: str, **kwargs):
        self._capture_timer = None
        self.image_dir = IMAGE_DIR

        super().__init__(unit=unit, experiment=experiment, plugin_name="pioreactor_camera")

        self.minutes_between_captures = float(
            config.get("camera_capture.config", "minutes_between_captures", fallback="5.0")
        )
        self.resolution_width = int(
            config.get("camera_capture.config", "resolution_width", fallback="640")
        )
        self.resolution_height = int(
            config.get("camera_capture.config", "resolution_height", fallback="480")
        )

    def on_init_to_ready(self):
        self._start_capture_timer()
        self.logger.info(
            f"Camera capture started: interval={self.minutes_between_captures}min, "
            f"resolution={self.resolution_width}x{self.resolution_height}"
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
