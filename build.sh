#!/bin/bash

SCRIPT_PATH="$(cd "$(dirname "$0")"; "pwd")"; # "
pushd $SCRIPT_PATH >/dev/null

sudo -H pip3.7 uninstall -y keyring keyrings.alt twine
sudo -H pip3.7 install setuptools wheel tox pytest  --upgrade
sudo -H pip3.7 install "keyring<19" twine --upgrade

python3.7 setup.py sdist
python3.7 setup.py bdist_wheel

popd >/dev/null
