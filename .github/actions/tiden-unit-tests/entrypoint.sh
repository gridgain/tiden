#!/bin/bash

set -e

echo "#########################################"
echo "Starting ${GITHUB_WORKFLOW}:${GITHUB_ACTION}"
echo "Args: $*"
echo "Working directory: "
pwd
ls -la 
echo "Env: "
set

pip3.7 install -r requirements.txt

py.test tests
