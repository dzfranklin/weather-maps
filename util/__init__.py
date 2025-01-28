import datetime
import os
import shutil
import subprocess
import tempfile

import metview as mv

from util.colormap import Colormap

# 23.5°W–45.0°E, 29.5°N–70.5°N (https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html)
# left, bottom, right, top
icon_eu_tilejson_bounds = [-23.5, 29.5, 45.0, 70.5]


def colorize(source_path: str, colormap_path: str, output_path: str):
    cmap = Colormap.read(colormap_path)

    with tempfile.NamedTemporaryFile() as colormap_scratch:
        colormap_scratch.write(cmap.gdal_format().encode("utf8"))
        colormap_scratch.flush()

        subprocess.run([
            "gdaldem",
            "color-relief",
            "-alpha",
            "-nearest_color_entry",
            source_path,
            colormap_scratch.name,
            output_path,
        ])


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


def fieldset_data_datetime(fs: mv.Fieldset) -> datetime.datetime:
    l = fs.ls(no_print=True)
    dates = l.dataDate
    times = l.dataTime
    assert len(dates) == len(times)
    assert len(dates) > 0
    for d in dates:
        assert d == dates[0]
    for t in times:
        assert t == times[0]
    return parse_numerical_timestamp(int(dates[0]), int(times[0]))


def parse_numerical_timestamp(date: int, time: int) -> datetime.datetime:
    year = date // 10 ** 4
    month = (date - year * 10 ** 4) // 10 ** 2
    day = date - year * 10 ** 4 - month * 10 ** 2
    hour = time // 10 ** 2
    minute = time - hour * 10 ** 2
    return datetime.datetime(year, month, day, hour, minute)
