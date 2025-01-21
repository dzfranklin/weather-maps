import os

import requests

apiKey = os.getenv("MET_ATMOSPHERIC_API_KEY")

order = "o200538428796"


def download(dir: str):
    resp = requests.get(
        f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{order}/latest?detail=minimal",
        headers={"apikey": apiKey},
        allow_redirects=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"got status {resp.status_code} requesting order data")
    data = resp.json()

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

        with open(os.path.join(dir, file_id), "wb") as f:
            f.write(resp.content)

    print(f"Downloaded {len(to_download)} files")


if __name__ == "__main__":
    # download("/tmp/data")
