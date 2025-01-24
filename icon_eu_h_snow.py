#!/usr/bin/env python

import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

import util.colormap
from util import icon_eu_tilejson_bounds, bunny

if __name__ == "__main__":
    if len(sys.argv) < 2:
        out_dir = "/out"
    else:
        out_dir = sys.argv[1]
    util.ensure_empty_dir(out_dir)

    data_dir = tempfile.mkdtemp()
    util.downloader_dwd(
        "--directory", data_dir,
        "--grid", "regular-lat-lon",
        "--model", "icon-eu",
        "--single-level-fields", "h_snow",
        "--timestamp", datetime.now().date().strftime("%Y-%m-%d"),
        "--min-time-step", "0",
        "--max-time-step", "120",
        "--time-step-interval", "12",
    )
    data_files = os.listdir(data_dir)
    print("Downloaded", data_files)

    zero_file = next(f for f in data_files if f.endswith("_000_H_SNOW.grib2"))
    run = re.match("icon-eu_europe_regular-lat-lon_single-level_([0-9]{10})_000_H_SNOW.grib2", zero_file).group(1)
    run_timestamp = datetime.strptime(run, "%Y%m%d%H")
    version_message = f"Updated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC to the {run_timestamp.strftime('%Y-%m-%d %H:%M')} UTC model run"
    print("Parsed version message:", version_message)

    run_dir = os.path.join(out_dir, run)
    os.makedirs(run_dir, exist_ok=True)

    hours = []
    for fname in data_files:
        hour = re.match("icon-eu_europe_regular-lat-lon_single-level_[0-9]+_([0-9]{3})_H_SNOW.grib2", fname).group(1)
        print(f"Processing {run}/{hour}")

        hour_dir = os.path.join(run_dir, hour)
        os.makedirs(hour_dir, exist_ok=True)

        colorized_file = f"{hour}_colorized.tif"
        util.gdaldem(
            "color-relief",
            "-alpha",
            os.path.join(data_dir, fname),
            "colormap_meters_snow.txt",
            colorized_file,
        )

        util.gdal2tiles(
            "--zoom=1-5",
            "--tilesize=512",
            "--xyz",
            "--webviewer=none",
            colorized_file,
            hour_dir,
        )

        tilejson = {
            "tiles": ["https://plantopo-weather.b-cdn.net/icon_eu_h_snow/" + run + "/" + hour + "/{z}/{x}/{y}.png"],
            "minzoom": 1,
            "maxzoom": 5,
            "bounds": icon_eu_tilejson_bounds,
            "attribution": "<a href=\"https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html\" target=\"_blank\">Deutscher Wetterdienst</a>",
        }
        with open(os.path.join(hour_dir, "tilejson.json"), "w+") as f:
            f.write(json.dumps(tilejson, indent=2))

        hours.append({
            "hour": int(hour),
            "tilejson": "https://plantopo-weather.b-cdn.net/icon_eu_h_snow/" + run + "/" + hour + "/tilejson.json",
        })

    shutil.rmtree(data_dir)

    meta = {
        "modelRun": run_timestamp.isoformat() + "Z",
        "versionMessage": version_message,
        "hours": hours,
    }
    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w+") as f:
        f.write(json.dumps(meta, indent=2))

    legend_path = os.path.join(out_dir, "legend.html")
    with open(legend_path, "w+") as f:
        f.write(util.colormap.html_legend("colormap_meters_snow.txt"))

    for root, _dirs, files in os.walk(run_dir):
        for fname in files:
            local_path = str(os.path.join(root, fname))
            remote_path = local_path.replace(out_dir, "").strip("/")
            bunny.weather_storage_upload(local_path, "icon_eu_h_snow/" + remote_path)

    bunny.weather_storage_upload(meta_path, "icon_eu_h_snow/meta.json")
    bunny.purge("https://plantopo-weather.b-cdn.net/icon_eu_h_snow/meta.json")

    bunny.weather_storage_upload(legend_path, "icon_eu_h_snow/legend.html")
    bunny.purge("https://plantopo-weather.b-cdn.net/icon_eu_h_snow/legend.html")

    bunny.weather_storage_delete_old("icon_eu_h_snow/")

    print("All done!")
