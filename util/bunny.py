import os
import urllib
from datetime import datetime, timedelta

import dateutil
import requests

bunnyStorageKey = os.getenv("BUNNY_WEATHER_STORAGE_KEY")
bunnyKey = os.getenv("BUNNY_KEY")

if bunnyStorageKey is None:
    raise Exception("BUNNY_WEATHER_STORAGE_KEY environment variable is not set")
if bunnyKey is None:
    raise Exception("BUNNY_KEY environment variable is not set")


def weather_storage_upload(local_path: str, remote_path: str):
    print(f"Uploading {remote_path}")
    if remote_path.startswith("/"):
        remote_path = remote_path[1:]

    with open(local_path, "rb") as f:
        resp = requests.put(
            "https://storage.bunnycdn.com/pt-weather/" + remote_path,
            headers={"AccessKey": bunnyStorageKey},
            data=f,
            )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise RuntimeError(f"got status {resp.status_code} from {resp.url}")


def purge(url: str):
    print(f"Purging {url}")
    requests.get(
        "https://api.bunny.net/purge?" + urllib.parse.urlencode({"url": url}),
        headers={"AccessKey": bunnyKey},
        )


def weather_storage_delete_old(dir_path: str):
    if dir_path.startswith("/"):
        dir_path = dir_path[1:]
    if not dir_path.endswith("/"):
        dir_path = dir_path + "/"

    cutoff = datetime.now() - timedelta(weeks=1)

    listing_resp = requests.get("https://storage.bunnycdn.com/pt-weather/" + dir_path,
                                headers={"AccessKey": bunnyStorageKey})
    if listing_resp.status_code != 200:
        raise RuntimeError(f"got status {listing_resp.status_code} listing {dir_path}")

    for obj in listing_resp.json():
        last_changed = dateutil.parser.isoparse(obj["LastChanged"])
        if last_changed < cutoff:
            path_to_delete = obj["Path"].lstrip("/") + obj["ObjectName"]
            requests.delete("https://storage.bunnycdn.com/" + path_to_delete, headers={"AccessKey": bunnyStorageKey})
            print(f"Deleted {path_to_delete}")
