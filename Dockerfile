# syntax=docker/dockerfile:1
FROM ghcr.io/dzfranklin/metview:5.23.1-gdal

RUN apt update \
    && apt install --yes --no-install-suggests --no-install-recommends \
    pipx \
    python3-virtualenv \
    && rm -rf /var/lib/apt/lists/*

RUN PIPX_BIN_DIR=/usr/bin pipx install --suffix _dwd git+https://github.com/DeutscherWetterdienst/downloader.git@392676084621282d4b2cb2f5a0e5ba5944ce69d0

RUN virtualenv --system-site-packages /venv

COPY requirements.txt /weather-maps/requirements.txt
RUN /venv/bin/pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    --no-python-version-warning \
    -r /weather-maps/requirements.txt

COPY . /weather-maps

WORKDIR /weather-maps
ENTRYPOINT ["./entrypoint.sh"]
