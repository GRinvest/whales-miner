venv: requirements.txt
	python3.9 -m venv .env
	./.env/bin/pip install -r requirements.txt

test: venv
	./.env/bin/python -m pytest --capture=tee-sys .

package: venv
	./.env/bin/pyinstaller --add-data "src/opencl_sha256.cl:./" -F src/miner.py -n whales-miner


docker-package:
	./scripts/build-docker.sh

