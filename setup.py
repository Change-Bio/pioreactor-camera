# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="pioreactor_camera",
    version="0.1.0",
    license_files=("LICENSE.txt",),
    description="Camera capture plugin with web gallery viewer for Pioreactor",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author_email="noahsprent@gmail.com",
    author="Noah Sprent",
    url="https://github.com/noahsprent/pioreactor-camera",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "pioreactor_camera": [
            "additional_config.ini",
            "ui/contrib/jobs/*.yaml",
            "static/**/*",
            "static/*",
        ],
    },
    install_requires=[],
    entry_points={
        "pioreactor.plugins": "pioreactor_camera = pioreactor_camera"
    },
)
