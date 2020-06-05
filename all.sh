#!/bin/bash

set -e

SCRIPT_PATH="$(cd "$(dirname "$0")"; "pwd")"; # "
pushd $SCRIPT_PATH >/dev/null

./build.sh
./install.sh
./tests.sh
./uninstall.sh
./clean.sh

popd >/dev/null
