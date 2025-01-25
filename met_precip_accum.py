#!/usr/bin/env python

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone, time
from glob import glob

import dateutil
import metview as mv
import requests

import util.colormap
from util import bunny

apiKey = os.getenv("MET_ATMOSPHERIC_API_KEY")

order = "plantopo-scotland-precip-accum"

# per nws definitions (https://www.weather.gov/bgm/forecast_terms)
day_start_hour = 6
day_end_hour = 18

# See <https://datahub.metoffice.gov.uk/support/model-run-availability> for when to run this program
expected_run_ts = datetime.combine(datetime.today(), time(hour=3), timezone.utc)


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


def accumulate_daytime(data_dir: str, out_dir: str) -> tuple[datetime, dict[datetime.date, str]]:
    all_fs = mv.Fieldset(path=data_dir + "/*")

    steps_by_date = {}
    latest_base_ts = None
    for (i, row) in all_fs.ls(no_print=True, extra_keys=["startStep", "endStep"]).iterrows():
        start_step = int(row["startStep"])
        end_step = int(row["endStep"])

        base_ts = datetime.strptime(f"{str(row['dataDate']).zfill(8)} {str(row['dataTime']).zfill(4)} UTC",
                                    "%Y%m%d %H%M %Z")
        start_ts = base_ts + timedelta(hours=start_step)
        end_ts = base_ts + timedelta(hours=end_step)

        if latest_base_ts is None or base_ts > latest_base_ts:
            latest_base_ts = base_ts

        if start_ts.hour >= day_start_hour and end_ts.hour <= day_end_hour and start_ts.date() == end_ts.date():
            if start_ts.date() not in steps_by_date:
                steps_by_date[start_ts.date()] = []
            steps_by_date[start_ts.date()].append(row)

    out = {}
    for (date, steps) in steps_by_date.items():
        fs = all_fs.select(startStep=[s["startStep"] for s in steps]).sum() / (day_end_hour - day_start_hour)
        out_path = os.path.join(out_dir, f"{date.strftime('%Y-%m-%d')}.grib")
        mv.write(out_path, fs)
        out[date] = out_path
    return latest_base_ts, out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        out_dir = "/out"
    else:
        out_dir = sys.argv[1]
    util.ensure_empty_dir(out_dir)

    with tempfile.TemporaryDirectory() as scratch_dir:
        download_dir = os.path.join(scratch_dir, "download")
        daytime_dir = os.path.join(scratch_dir, "daytime")
        colorized_dir = os.path.join(scratch_dir, "colorized")

        for d in [download_dir, daytime_dir, colorized_dir, out_dir]:
            os.makedirs(d, exist_ok=True)

        download(download_dir)

        (base_ts, daytime_files) = accumulate_daytime(download_dir, daytime_dir)

        dates = []
        for date, daytime_grib in sorted(daytime_files.items(), key=lambda v: v[0]):
            date_out_dir = os.path.join(out_dir, date.strftime("%Y%m%d"))
            os.makedirs(date_out_dir, exist_ok=True)

            colorized_tif = os.path.join(colorized_dir, f"{date.strftime('%Y%m%d')}.tif")
            util.gdaldem("color-relief", "-alpha", daytime_grib, "colormap_mm_precipitation.txt", colorized_tif)

            util.gdal2tiles("--zoom=1-8", "--tilesize=512", "--xyz", "--webviewer=none", colorized_tif, date_out_dir)

            tilejson = {
                "tiles": [
                    f"https://plantopo-weather.b-cdn.net/met_scotland_daytime_average_precipitation_accumulation/" +
                    base_ts.strftime('%Y%m%d') + "/" + date.strftime('%Y%m%d') + "/{z}/{x}/{y}.png"],
                "minzoom": 1,
                "maxzoom": 8,
                "bounds": [-6.92, 54.51, -1.65, 58.78],
                "attribution": "<a href=\"https://datahub.metoffice.gov.uk/\" target=\"_blank\">Met Office</a>",
            }
            with open(os.path.join(date_out_dir, "tilejson.json"), "w+") as f:
                f.write(json.dumps(tilejson, indent=2))

            dates.append({
                "date": date.isoformat(),
                "tilejson": "https://plantopo-weather.b-cdn.net/met_scotland_daytime_average_precipitation_accumulation/" +
                            base_ts.strftime('%Y%m%d') + "/" + date.strftime('%Y%m%d') + "/tilejson.json",
            })

        versionMessage = f"Updated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC to the {base_ts.strftime('%Y-%m-%d %H:%M')} UTC model run"
        with open(os.path.join(out_dir, "meta.json"), "w+") as f:
            f.write(json.dumps({
                "modelRun": base_ts.isoformat() + "Z",
                "dates": dates,
                "versionMessage": versionMessage,
            }, indent=2))

    legend_path = os.path.join(out_dir, "legend.html")
    with open(legend_path, "w+") as f:
        f.write(util.colormap.html_legend("colormap_mm_precipitation.txt"))

    for local_path in glob(f"{out_dir}/**/*", recursive=True):
        if local_path.endswith("/meta.json") or local_path.endswith("/legend.html") or not os.path.isfile(local_path):
            continue
        remote_path = local_path.replace(out_dir, "").strip("/")
        bunny.weather_storage_upload(
            local_path,
            "met_scotland_daytime_average_precipitation_accumulation/" + base_ts.strftime('%Y%m%d') + "/" + remote_path)

    bunny.weather_storage_upload(os.path.join(out_dir, "meta.json"),
                                 "met_scotland_daytime_average_precipitation_accumulation/meta.json")
    bunny.purge("https://plantopo-weather.b-cdn.net/met_scotland_daytime_average_precipitation_accumulation/meta.json")

    bunny.weather_storage_upload(os.path.join(out_dir, "legend.html"),
                                 "met_scotland_daytime_average_precipitation_accumulation/legend.html")
    bunny.purge(
        "https://plantopo-weather.b-cdn.net/met_scotland_daytime_average_precipitation_accumulation/legend.html")

    bunny.weather_storage_delete_old("met_scotland_daytime_average_precipitation_accumulation/")

    print("All done!")
