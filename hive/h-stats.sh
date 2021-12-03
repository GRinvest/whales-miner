#!/usr/bin/env bash

CUSTOM_DIR=$(dirname "$BASH_SOURCE")

. $CUSTOM_DIR/h-manifest.conf

# Read gpu stats
temp=$(jq '.temp' <<< $gpu_stats)
fan=$(jq '.fan' <<< $gpu_stats)
[[ $cpu_indexes_array != '[]' ]] && #remove Internal Gpus
    temp=$(jq -c "del(.$cpu_indexes_array)" <<< $temp) &&
    fan=$(jq -c "del(.$cpu_indexes_array)" <<< $fan)

# Read miner stats
hs="[]"
uptime=0
if [ -f "${CUSTOM_DIR}/stats.json" ]; then
  khs=`jq .total ${CUSTOM_DIR}/stats.json`
  hs=`jq .rates ${CUSTOM_DIR}/stats.json`
  uptime=`jq .uptime ${CUSTOM_DIR}/stats.json`
else
  echo "No stats found"
  khs=0
fi

# Uptime
ver=$CUSTOM_VERSION
hs_units="mhs"

# Performance
stats=$(jq -nc \
        --argjson hs "${hs}" \
        --arg total_khs "$khs" \
        --arg hs_units "$hs_units" \
        --argjson temp "$temp" \
        --argjson fan "$fan" \
        --arg uptime "$uptime" \
        --arg ver "$ver" \
        '{$total_khs, $hs, $hs_units, $temp, $fan, $uptime, $ver}')
