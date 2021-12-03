#!/bin/bash

echo "Building docker image..."
IMAGE_ID=`docker build -q .`
echo "Image hash: $IMAGE_ID"

source ./hive/h-manifest.conf
PACKAGE_DIR="whales-miner-${CUSTOM_VERSION}"
mkdir -p hive-dist/${PACKAGE_DIR}
docker cp `docker create --rm $IMAGE_ID /bin/bash`:/app/dist/danila-miner hive-dist/${PACKAGE_DIR}/whales-miner
cp ./hive/* ./hive-dist/${PACKAGE_DIR}
docker rmi -f $IMAGE_ID
cd hive-dist/
tar cvzf whales-miner-${CUSTOM_VERSION}-hive.tar.gz ${PACKAGE_DIR}/*