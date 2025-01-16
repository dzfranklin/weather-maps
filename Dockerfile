# syntax=docker/dockerfile:1
FROM ghcr.io/osgeo/gdal:ubuntu-full-3.10.1

RUN apt update \
    && apt install -y git pipx jq \
    && apt clean

RUN PIPX_BIN_DIR=/usr/bin pipx install --suffix _dwd git+https://github.com/DeutscherWetterdienst/downloader.git@392676084621282d4b2cb2f5a0e5ba5944ce69d0

COPY . /weather-maps
