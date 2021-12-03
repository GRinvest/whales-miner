#!/usr/bin/env bash
# This code is included in /hive/bin/custom function

CUSTOM_DIR=$(dirname "$BASH_SOURCE")

. $CUSTOM_DIR/h-manifest.conf

[[ -z $CUSTOM_TEMPLATE ]] && echo -e "${YELLOW}CUSTOM_TEMPLATE is empty${NOCOLOR}" && return 1
[[ -z $CUSTOM_URL ]] && echo -e "${YELLOW}CUSTOM_URL is empty${NOCOLOR}" && return 2


echo "$CUSTOM_TEMPLATE $CUSTOM_URL" > $CUSTOM_CONFIG_FILENAME
