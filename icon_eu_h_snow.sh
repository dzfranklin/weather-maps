#!/usr/bin/env bash
set -euox pipefail

rm -rf /prepare_icon_eu_h_snow && mkdir -p /prepare_icon_eu_h_snow && cd /prepare_icon_eu_h_snow

mkdir -p out

mkdir -p data
downloader_dwd \
    --directory ./data --grid regular-lat-lon \
    --model icon-eu --single-level-fields h_snow \
    --timestamp "$(date -u '+%Y-%m-%d')T00:00:00"\
    --min-time-step 0 --max-time-step 120 --time-step-interval 24

ls ./data >out/__input_files.txt

run=$(find data -name '*_000_H_SNOW.grib2' -printf '%f\n' | \
            sed -r 's/icon-eu_europe_regular-lat-lon_single-level_([0-9]{10})_000_H_SNOW.grib2/\1/')

runTimestamp=$(printf '%s\n' "$run" | sed -r 's/([0-9]{4})([0-9]{2})([0-9]{2})([0-9]{2})/\1-\2-\3T\4:00:00Z/' | xargs date +%s --date)
printf 'Updated at %(%c %Z)T to the %(%c %Z)T model run\n' "$(date +%s)" "$runTimestamp" >out/version_message.txt

mkdir -p out/tiles
for f in ./data/*; do
  [ -e "$f" ] || continue

  hour=$(basename -- "$f" | sed -r "s/icon-eu_europe_regular-lat-lon_single-level_[0-9]+_([0-9]{3})_H_SNOW.grib2/\1h/")

  echo "Processing $run/$hour"

  colorized_file="${run}_${hour}_colorized.tif"
  gdaldem color-relief -alpha "$f" /weather-maps/h_snow_colormap.txt "$colorized_file"

  gdal2tiles --zoom=1-5 --tilesize=512 --xyz --webviewer=none "$colorized_file" "out/tiles/${run}_${hour}"

cat <<EOF >"out/${hour}.json"
{
  "tiles": ["https://plantopo-weather.b-cdn.net/icon_eu_h_snow/tiles/${run}_${hour}/{z}/{x}/{y}.png"],
  "minzoom": 1,
  "maxzoom": 5,
  "attribution": "<a href=\"https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html\" target=\"_blank\">Deutscher Wetterdienst</a>"
}
EOF

done

# Upload tiles

for f in $(find out/tiles -type f -printf "%P\n" | sort); do
  curl -X PUT -sSf -o /dev/null -H "AccessKey: $BUNNY_WEATHER_STORAGE_KEY" \
    "https://uk.storage.bunnycdn.com/plantopo-weather/icon_eu_h_snow/tiles/$f" \
    --data-binary "@out/tiles/$f"
done

# Upload and purge metadata files

for f in $(find out -maxdepth 1 -type f -printf "%P\n" | sort); do
  curl -X PUT -sSf -o /dev/null -H "AccessKey: $BUNNY_WEATHER_STORAGE_KEY" \
    "https://uk.storage.bunnycdn.com/plantopo-weather/icon_eu_h_snow/$f" \
    --data-binary "@out/$f"

  curl --get -sSf -o /dev/null -H "AccessKey: $BUNNY_KEY" "https://api.bunny.net/purge" \
    -d "url=https://plantopo-weather.b-cdn.net/icon_eu_h_snow/$f"
done

# Delete old tiles

outdatedTileCutoff=$(date +%Y-%m-%d'T'%H:%M'Z' -d "1 week ago")
outdatedTileFolders=$(curl -H "AccessKey: $BUNNY_WEATHER_STORAGE_KEY" https://uk.storage.bunnycdn.com/plantopo-weather/icon_eu_h_snow/tiles/ \
  | jq -r --arg cutoff "$outdatedTileCutoff" '.[] | select(.DateCreated < $cutoff) | .Path+.ObjectName+"/" | gsub("^/"; "")')
for path in $outdatedTileFolders; do
  curl -X DELETE -sSf -o /dev/null -H "AccessKey: $BUNNY_WEATHER_STORAGE_KEY" \
    "https://uk.storage.bunnycdn.com/$path"
done

echo "All done"
