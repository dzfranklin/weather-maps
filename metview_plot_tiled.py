import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import mercantile
import metview as mv
from PIL import Image


# TODO: render a buffer around each tile to crop out. That would avoid the various one pixel line issues.

if __name__ == "__main__":
    data = mv.gallery.load_dataset("2m_temperature.grib")
    contours = mv.mcont(contour_automatic_setting="ecchart")

    metview_plot_tiled.plot(
        "./sample",
        (data, contours),
        max_zoom=8,
        bbox=mercantile.LngLatBbox(-8, 55, 0, 60),
    )


def plot(
        out_dir: str,
        args: tuple[Any, ...],
        min_zoom: int = 0,
        max_zoom: int = 5,
        base_url: str = "",
        attribution: str | None = "",
        bbox: mercantile.LngLatBbox | None = None,
):
    if base_url != "" and not base_url.endswith("/"):
        base_url += "/"

    out = Path(out_dir)

    if os.path.exists(out):
        for f in os.listdir(out):
            p = out / f
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    else:
        os.makedirs(out)

    tile_pattern = "{z}/{x}/{y}.png"
    tile_url = base_url + tile_pattern
    tilejson = {
        "tiles": [tile_url],
        "minzoom": min_zoom,
        "maxzoom": max_zoom,
    }
    if attribution is not None:
        tilejson["attribution"] = attribution

    with open(out / "tilejson.json", "w+") as f:
        f.write(json.dumps(tilejson, indent=2))

    with open(out / "leaflet.html", "w+") as f:
        f.write(leaflet_html.format(
            out_dir=str(out),
            tile_url=tile_pattern,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            attribution=attribution if attribution is not None else "",
        ))

    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)

        for z in range(min_zoom, max_zoom + 1):
            level_start_time = time.time()

            if bbox is not None:
                tiles = list(mercantile.tiles(bbox.west, bbox.south, bbox.east, bbox.north, z, truncate=True))
            else:
                tiles = [mercantile.Tile(z=z, x=x, y=y) for x in range(0, 2 ** z) for y in range(0, 2 ** z)]

            count_width = len(str(len(tiles)))
            for (i, tile) in enumerate(tiles):
                _plot_tile(scratch, out, tile, bbox, args)
                sys.stdout.write(f"\rGenerating zoom level {z}: {str(i + 1).rjust(count_width)} / {len(tiles)}")
                sys.stdout.flush()
            sys.stdout.write("\n")

            level_dur = time.time() - level_start_time
            print(f"Generated zoom level {z} in {level_dur:.2f}s ({level_dur / len(tiles):.2f}s per tile on average)")


def _plot_tile(
        scratch: Path,
        out: Path,
        tile: mercantile.Tile,
        map_bbox: mercantile.LngLatBbox | None,
        args: tuple[Any, ...]
):
    tile_size = 512

    out_path = out / f"{tile.z}/{tile.x}/{tile.y}.png"
    os.makedirs(out_path.parent, exist_ok=True)

    os.makedirs(scratch, exist_ok=True)

    bounds = mercantile.bounds(tile)

    view = mv.geoview(
        map_projection="mercator",
        coastlines=mv.mcoast(
            map_coastline="off",
            map_grid="off",
            map_label="off"
        ),
        subpage_frame="off",
        subpage_clipping="on",
        subpage_x_position="0",
        subpage_y_position="0",
        subpage_x_length="100",
        subpage_y_length="100",
        map_area_definition="corners",
        area=[bounds.south, bounds.west, bounds.north, bounds.east],
    )

    mv.setoutput(mv.png_output(
        output_name=str(out_path.parent / out_path.stem),
        output_name_first_page_number="off",
        output_cairo_transparent_background="on",
        output_font_scale="1.0",
        output_width=str(tile_size),
    ))

    size_in_nominal_inches = str(round(tile_size / 96, 5))
    dw = mv.plot_superpage(
        layout_size="custom",
        layout_orientation="landscape",
        custom_width=size_in_nominal_inches,
        custom_height=size_in_nominal_inches,
        pages=[mv.plot_page(view=view)]
    )

    mv.plot(dw[0], *args)

    im = Image.open(out_path)
    if im.width != tile_size or im.height != tile_size:
        raise RuntimeError(f"expected {tile_size}x{tile_size} image, got {im.width}x{im.height}")


leaflet_html = """<!DOCTYPE html>
<html lang="en">
    <head>
        <title>{out_dir} | metview_plot_tiled sample</title>
        
         <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
            integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
         <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
             integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
             crossorigin=""></script>
             
         <style>
         body, #map {{
            width: 100vw;
            height: 100vh;
            padding: 0;
            margin: 0;
            border: 0;
        }}
        </style>
    </head>
    
    <div id="map"></div>
    
    <script>
    const map = L.map("map").setView([51, 0], {min_zoom});
    
    L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }}).addTo(map);

    L.tileLayer("{tile_url}", {{
        minNativeZoom: {min_zoom},
        maxNativeZoom: {max_zoom},
        attribution: "{attribution}",
        opacity: 0.5,
    }}).addTo(map);
    </script>
</html>
"""
