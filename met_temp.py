#!/usr/bin/env python

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone, time

import dateutil
import metview as mv
import requests

import util.colormap
from util import bunny

apiKey = os.getenv("MET_ATMOSPHERIC_API_KEY")

order = "plantopo-scotland-temp-150cm"

# per nws definitions (https://www.weather.gov/bgm/forecast_terms)
day_start_hour = 6
day_end_hour = 18
day_hour_times = [h * 100 for h in range(day_start_hour, day_end_hour + 1)]

# See <https://datahub.metoffice.gov.uk/support/model-run-availability> for when to run this program
expected_run_ts = datetime.combine(datetime.today(), time(hour=3), timezone.utc)
daytime_validity_dates = [expected_run_ts.date() + timedelta(days=d) for d in range(0, 5)]
nighttime_validity_dates = [expected_run_ts.date() + timedelta(days=d) for d in range(0, 4)]


def download(out: str):
    resp = requests.get(
        f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{order}/latest?detail=minimal",
        headers={"apikey": apiKey},
        allow_redirects=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"got status {resp.status_code} requesting order data")
    data = resp.json()

    for file in data["orderDetails"]["files"]:
        raw_run_ts = file["runDateTime"]
        run_ts = dateutil.parser.isoparse(raw_run_ts)
        if run_ts != expected_run_ts:
            raise RuntimeError(f"expected run not available: got {raw_run_ts}, expected {expected_run_ts}")

    to_download: list[str] = []
    for file in data["orderDetails"]["files"]:
        file_id: str = file["fileId"]

        if "+" not in file_id:
            #  The order contains the same file in the relative and absolute naming format, so I only include absolute
            to_download.append(file_id)

    for (i, file_id) in enumerate(to_download):
        print(f"Downloading {file_id} ({i + 1}/{len(to_download)})")
        resp = requests.get(
            f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{order}/latest/{file_id}/data",
            headers={"apikey": apiKey},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"got status {resp.status_code} downloading {file_id}")

        with open(os.path.join(out, file_id), "wb") as f:
            f.write(resp.content)

    print(f"Downloaded {len(to_download)} files")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        out_dir = "/out"
    else:
        out_dir = sys.argv[1]
    util.ensure_empty_dir(out_dir)

    with tempfile.TemporaryDirectory() as scratch_dir:
        download_dir = os.path.join(scratch_dir, "download")
        grib_dir = os.path.join(scratch_dir, "grib")
        colorized_dir = os.path.join(scratch_dir, "colorized")

        for d in [download_dir, grib_dir, colorized_dir, out_dir]:
            os.makedirs(d, exist_ok=True)

        download(download_dir)

        all_fs = mv.Fieldset(path=f"{download_dir}/*")
        data_ts = util.fieldset_data_datetime(all_fs)

        run_name = data_ts.strftime("%Y%m%d")
        run_dir = os.path.join(out_dir, run_name)

        for d in daytime_validity_dates:
            date_name = d.strftime("%Y%m%d")
            date_out_dir = os.path.join(run_dir, date_name)

            select_times = [h * 100 for h in range(day_start_hour, day_end_hour + 1)]
            daytime_fs = all_fs.select(validityDate=d, validityTime=select_times)
            print(f"selected fieldset where date={d}, time={select_times}")
            daytime_fs.ls(extra_keys=["validityDate", "validityTime"])

            for (name, fs) in [("daytime_max", daytime_fs.max()), ("daytime_min", daytime_fs.min())]:
                name_out_dir = os.path.join(date_out_dir, name)
                os.makedirs(name_out_dir, exist_ok=True)

                grib_file = os.path.join(grib_dir, f"{date_name}_{name}.grib")
                mv.write(grib_file, fs)

                colorized_tif = os.path.join(colorized_dir, f"{date_name}_{name}.tif")
                util.colorize(grib_file, "colormaps/temp_c.txt", colorized_tif)

                util.gdal2tiles("--zoom=1-8", "--tilesize=512", "--xyz", "--webviewer=none", colorized_tif,
                                name_out_dir)

                tilejson = {
                    "tiles": [
                        f"https://plantopo-weather.b-cdn.net/met_scotland_temperature/" + run_name + "/" + date_name +
                        "/" + name + "/{z}/{x}/{y}.png"],
                    "minzoom": 1,
                    "maxzoom": 8,
                    "bounds": [-6.92, 54.51, -1.65, 58.78],
                    "attribution": "<a href=\"https://datahub.metoffice.gov.uk/\" target=\"_blank\">Met Office</a>",
                }
                with open(os.path.join(name_out_dir, "tilejson.json"), "w+") as f:
                    f.write(json.dumps(tilejson, indent=2))

        for d in nighttime_validity_dates:
            date_name = d.strftime("%Y%m%d")
            date_out_dir = os.path.join(run_dir, date_name)

            fs1_date = d
            fs1_select_times = [h * 100 for h in range(day_end_hour + 1, 24)]

            fs2_date = d + timedelta(days=1)
            fs2_select_times = [h * 100 for h in range(0, day_start_hour)]

            nighttime_fs = mv.merge(all_fs.select(validityDate=fs1_date, validityTime=fs1_select_times),
                                    all_fs.select(validityDate=fs2_date, validityTime=fs2_select_times))
            print(f"selected fieldset where date={fs1_date} and time={fs1_select_times} " +
                  f"or date={fs2_date} and time={fs2_select_times}")
            nighttime_fs.ls(extra_keys=["validityDate", "validityTime"])

            for (name, fs) in [("nighttime_max", nighttime_fs.max()), ("nighttime_min", nighttime_fs.min())]:
                name_out_dir = os.path.join(date_out_dir, name)
                os.makedirs(name_out_dir, exist_ok=True)

                grib_file = os.path.join(grib_dir, f"{date_name}_{name}.grib")
                mv.write(grib_file, fs)

                colorized_tif = os.path.join(colorized_dir, f"{date_name}_{name}.tif")
                util.colorize(grib_file, "colormaps/temp_c.txt", colorized_tif)

                util.gdal2tiles("--zoom=1-8", "--tilesize=512", "--xyz", "--webviewer=none", colorized_tif,
                                name_out_dir)

                tilejson = {
                    "tiles": [
                        f"https://plantopo-weather.b-cdn.net/met_scotland_temperature/" + run_name + "/" + date_name +
                        "/" + name + "/{z}/{x}/{y}.png"],
                    "minzoom": 1,
                    "maxzoom": 8,
                    "bounds": [-6.92, 54.51, -1.65, 58.78],
                    "attribution": "<a href=\"https://datahub.metoffice.gov.uk/\" target=\"_blank\">Met Office</a>",
                }
                with open(os.path.join(name_out_dir, "tilejson.json"), "w+") as f:
                    f.write(json.dumps(tilejson, indent=2))

    # nighttime dates are a subset of daytime dates
    dates = []
    for d in daytime_validity_dates:
        date_url = "https://plantopo-weather.b-cdn.net/met_scotland_temperature/" + run_name + "/" + \
                   d.strftime('%Y%m%d')

        date_meta = {
            "date": d.isoformat(),
            "daytime_min_tilejson": date_url + "/daytime_min/tilejson.json",
            "daytime_max_tilejson": date_url + "/daytime_max/tilejson.json",
        }

        if d in nighttime_validity_dates:
            date_meta["nighttime_min_tilejson"] = date_url + "/nighttime_min/tilejson.json"
            date_meta["nighttime_max_tilejson"] = date_url + "/nighttime_max/tilejson.json"

        dates.append(date_meta)

    versionMessage = f"Updated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC to the {data_ts.strftime('%Y-%m-%d %H:%M')} UTC model run"
    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w+") as f:
        f.write(json.dumps({
            "modelRun": data_ts.isoformat() + "Z",
            "dates": dates,
            "versionMessage": versionMessage,
        }, indent=2))

    legend_path = os.path.join(out_dir, "legend.html")
    with open(legend_path, "w+") as f:
        f.write(util.colormap.html_legend("colormaps/temp_c.txt"))

    for root, _dirs, files in os.walk(run_dir):
        for fname in files:
            local_path = str(os.path.join(root, fname))
            remote_path = local_path.replace(out_dir, "").strip("/")
            bunny.weather_storage_upload(local_path, "met_scotland_temperature/" + remote_path)

    for entry in os.scandir(out_dir):
        if entry.is_file():
            bunny.weather_storage_upload(entry.path, "met_scotland_temperature/" + entry.name)
            bunny.purge("https://plantopo-weather.b-cdn.net/met_scotland_temperature/" + entry.name)

    bunny.weather_storage_delete_old("met_scotland_temperature/")

    print("All done!")
