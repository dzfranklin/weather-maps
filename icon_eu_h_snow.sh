#!/usr/bin/env bash
set -euox pipefail

rm -rf /prepare_icon_eu_h_snow && mkdir -p /prepare_icon_eu_h_snow && cd /prepare_icon_eu_h_snow

mkdir -p data
mkdir -p out

downloader_dwd \
    --directory ./data --grid regular-lat-lon \
    --model icon-eu --single-level-fields h_snow \
    --timestamp "$(date -u '+%Y-%m-%d')T00:00:00"\
    --min-time-step 0 --max-time-step 120 --time-step-interval 24

ls ./data >out/sources.txt

find data -name '*000_H_SNOW.grib2' -printf '%f\n' | \
  sed -r 's/icon-eu_europe_regular-lat-lon_single-level_([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})_000_H_SNOW.grib2/Forecast updated at \1-\2-\3 \4:00:00/' \
  >out/version_message.txt

for f in ./data/*; do
  [ -e "$f" ] || continue

  name=$(basename -- "$f" | sed -r "s/icon-eu_europe_regular-lat-lon_single-level_[0-9]+_([0-9]{3})_H_SNOW.grib2/\1h/")

  echo "Processing $name"

  gdaldem color-relief -alpha "$f" /weather-maps/h_snow_colormap.txt "${name}_color.tif"

  gdal2tiles --zoom=1-5 --tilesize=512 --xyz "${name}_color.tif" "out/${name}"

cat <<EOF >"out/${name}/source.json"
{
  "tiles": ["https://plantopo-storage.b-cdn.net/weather-maps/icon_eu_h_snow/${name}/{z}/{x}/{y}.png"],
  "minzoom": 1,
  "maxzoom": 5,
  "attribution": "<a href=\"https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html\" target=\"_blank\">Deutscher Wetterdienst</a>"
}
EOF

done

for f in $(find out -type f -printf "%P\n" | sort); do
  curl -X PUT -H "AccessKey: $BUNNY_STORAGE_KEY" --fail-with-body \
    "https://uk.storage.bunnycdn.com/plantopo/weather-maps/icon_eu_h_snow/$f" \
    --data-binary "@out/$f"
done

for f in $(find out -type f -printf "%P\n" | sort); do
  curl --get -H "AccessKey: $BUNNY_KEY" --fail-with-body "https://api.bunny.net/purge" \
    -d "url=https://plantopo-storage.b-cdn.net/weather-maps/icon_eu_h_snow/$f"
done

echo "All done"
