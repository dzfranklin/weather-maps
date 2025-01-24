import os
import shutil
import subprocess


# 23.5°W–45.0°E, 29.5°N–70.5°N (https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html)
# left, bottom, right, top
icon_eu_tilejson_bounds = [-23.5, 29.5, 45.0, 70.5]


def gdaldem(*args):
    subprocess.run(["gdaldem", *args], check=True)


def gdal2tiles(*args):
    subprocess.run(["gdal2tiles.py", *args], check=True)


def downloader_dwd(*args):
    subprocess.run(["downloader_dwd", *args], check=True)


def ensure_empty_dir(d: str):
    os.makedirs(d, exist_ok=True)
    remove_all_in(d)


def remove_all_in(d: str):
    for entry in os.scandir(d):
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            os.remove(entry)
