#!/usr/bin/env bash

CUSTOM_DIR=$(dirname "$BASH_SOURCE")

# Read gpu stats
local temp=$(jq '.temp' <<< $gpu_stats)
local fan=$(jq '.fan' <<< $gpu_stats)
[[ $cpu_indexes_array != '[]' ]] && #remove Internal Gpus
    temp=$(jq -c "del(.$cpu_indexes_array)" <<< $temp) &&
    fan=$(jq -c "del(.$cpu_indexes_array)" <<< $fan)

# Read miner stats
local hs="[]"
local uptime=0
if [ -f "${CUSTOM_DIR}/stats.json" ]; then
  khs=`jq .total ${CUSTOM_DIR}/stats.json`
  hs=`jq .rates ${CUSTOM_DIR}/stats.json`
  uptime=`jq .uptime ${CUSTOM_DIR}/stats.json`
else
  echo "No stats found"
  khs=0
fi

# Uptime
local ver=0.0.46
local hs_units="mhs"

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
