#!/usr/bin/env bash

cd `dirname $0`

export LD_LIBRARY_PATH=.

. colors

CUSTOM_DIR=$(dirname "$BASH_SOURCE")

. $CUSTOM_DIR/h-manifest.conf

[[ -z $CUSTOM_LOG_BASEDIR ]] && echo -e "${RED}No CUSTOM_LOG_BASEDIR is set${NOCOLOR}" && exit 1
[[ -z $CUSTOM_CONFIG_FILENAME ]] && echo -e "${RED}No CUSTOM_CONFIG_FILENAME is set${NOCOLOR}" && exit 1
[[ ! -f $CUSTOM_CONFIG_FILENAME ]] && echo -e "${RED}Custom config ${YELLOW}$CUSTOM_CONFIG_FILENAME${RED} is not found${NOCOLOR}" && exit 1

mkdir -p $CUSTOM_LOG_BASEDIR
touch $CUSTOM_LOG_BASENAME.log

# remove tmp dirs
while read -r d; do
	[[ "$d" =~ (\/tmp\/[^\\]+)\/solvers ]] && echo "Removing ${BASH_REMATCH[1]}" && rm -r "${BASH_REMATCH[1]}"
done < <( realpath /tmp/*/solvers 2>/dev/null )

./whales-miner $(< $CUSTOM_CONFIG_FILENAME ) 2>&1 | tee --append $CUSTOM_LOG_BASENAME.log

